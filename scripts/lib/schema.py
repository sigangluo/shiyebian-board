"""所有地区统一的岗位格式：抓取脚本产出、CSV 读写、校验都在这里。

一个岗位就是一个 dict，用 make_job() 创建。各地岗位表多出来的列放进 extra，会写进 CSV，但不参与筛选。
字段尽量保留岗位表的原文：解析（学历、专业代码、年龄、经历）由 match.py 在合并时做，
这样改规则不用重新抓取。
"""
import re

import pandas as pd

# (字段, CSV 列名)
STANDARD = [
    ("id", "岗位代码"), ("batch", "批次"), ("city", "城市"), ("unit", "招聘单位"), ("dept", "工作部门"),
    ("duty", "岗位职责"), ("grade", "岗位等级"), ("headcount", "招聘人数"), ("fresh", "考生类别"),
    ("education", "学历要求"), ("degree", "学位要求"),
    ("major_college", "专业要求(大专)"), ("major_bachelor", "专业要求(本科)"), ("major_graduate", "专业要求(研究生)"),
    ("age", "年龄"), ("age_relaxed", "放宽年龄(硕士)"), ("experience", "工作经历"),
    ("certs", "资格证书"), ("title_req", "职称要求"), ("politics", "政治面貌"),
    ("exam", "考试方式"), ("special", "专项招聘对象"), ("hukou", "户籍要求"), ("other", "其他条件"),
    ("url", "链接"),
]
FIELDS = [f for f, _ in STANDARD]


def make_job(*, id, batch, unit, city="", dept="", duty="", grade="", headcount="", fresh="",
             education="", degree="", major_college="", major_bachelor="", major_graduate="",
             age="", age_relaxed="", experience="", certs="", title_req="", politics="",
             exam="", special="", hukou="", other="", url="", extra=None):
    """创建一个标准岗位。除 extra 外全是字符串，保留岗位表原文；没有的留空。

    id:      批次内唯一的岗位代码
    batch:   批次 key，必须在 META["batches"] 里
    city:    岗位所在城市（考区），如 "广州"
    fresh:   考生类别原文，如 "应届毕业生" / "不限"
    exam:    考试方式，如 "笔试+面试" / "面试" / "直接业务考核"
    url:     岗位或公告页面，必须是 https://；没有就留空（看板会指向批次的公告页）
    extra:   岗位表里其他的列 {列名: 值}，只进 CSV
    """
    def s(v):
        if v is None:
            return ""
        if isinstance(v, float) and v == int(v):    # Excel 里的 1.0 -> "1"
            return str(int(v))
        return str(v).strip()

    vals = dict(id=id, batch=batch, unit=unit, city=city, dept=dept, duty=duty, grade=grade, headcount=headcount,
                fresh=fresh, education=education, degree=degree, major_college=major_college,
                major_bachelor=major_bachelor, major_graduate=major_graduate, age=age, age_relaxed=age_relaxed,
                experience=experience, certs=certs, title_req=title_req, politics=politics, exam=exam,
                special=special, hukou=hukou, other=other, url=url)
    job = {k: s(v) for k, v in vals.items()}
    job["extra"] = {k: s(v) for k, v in (extra or {}).items() if s(v)}
    return job


def validate(jobs, meta):
    """检查抓取结果，有问题就抛 ValueError（信息里带上下文，方便判断是岗位表变了还是脚本写错了）。"""
    if not jobs:
        raise ValueError("fetch() 返回了 0 个岗位")
    batches = meta["batches"]
    seen, bad = set(), []
    for j in jobs:
        key = (j["batch"], j["id"])
        if not j["id"] or not j["unit"]:
            bad.append(f"缺少岗位代码或招聘单位: {j['id']!r} {j['unit']!r}")
        elif j["batch"] not in batches:
            bad.append(f"批次 {j['batch']!r} 不在 META['batches'] 里: {j['id']}")
        elif key in seen:
            bad.append(f"岗位代码重复: {j['batch']}/{j['id']}")
        elif j["headcount"] and not j["headcount"].isdigit():
            bad.append(f"招聘人数不是整数: {j['id']} -> {j['headcount']!r}")
        elif j["url"] and not j["url"].startswith("https://"):
            bad.append(f"链接必须是 https://: {j['id']} -> {j['url']!r}")
        seen.add(key)
    if bad:
        raise ValueError(f"{len(bad)} 处问题，前 5 条:\n  " + "\n  ".join(bad[:5]))
    empty = [b for b in batches if not any(j["batch"] == b for j in jobs)]
    if empty:
        raise ValueError(f"批次 {empty} 一个岗位都没抓到，可能是岗位表的格式变了")
    return jobs


def to_frame(jobs):
    """岗位列表 -> DataFrame（标准列 + extra 列，extra 列按首次出现顺序排在后面）。"""
    extras = list(dict.fromkeys(k for j in jobs for k in j["extra"]))
    rows = [{**{label: j[f] for f, label in STANDARD}, **{k: j["extra"].get(k, "") for k in extras}} for j in jobs]
    return pd.DataFrame(rows, columns=[label for _, label in STANDARD] + extras)


def read_jobs(path):
    """读回 CSV -> 标准岗位列表（extra 列一并还原）。"""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    std = {label: f for f, label in STANDARD}
    jobs = []
    for r in df.to_dict("records"):
        j = {f: r.get(label, "").strip() for label, f in std.items()}
        j["extra"] = {k: v for k, v in r.items() if k not in std and v}
        jobs.append(j)
    return jobs


def count_rows(paths):
    """CSV 里的岗位数（不是文本行数：岗位职责里可能有换行）。"""
    return sum(len(pd.read_csv(p, usecols=["岗位代码"], dtype=str)) for p in paths)


def normalize_city(c):
    """'杭州市' -> '杭州'（两个字以上才去掉"市"）。"""
    c = (c or "").strip()
    return c[:-1] if len(c) > 2 and c.endswith("市") else c


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_date(s):
    return bool(_DATE.match(s or ""))
