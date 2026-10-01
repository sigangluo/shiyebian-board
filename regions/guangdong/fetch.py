"""广东省事业单位公开招聘（https://hrss.gd.gov.cn/zwgk/sydwzp/index.html）。

广东每年集中招聘一次高校毕业生，公告里附带一个 xlsx 岗位表（多个 sheet：笔试+面试、技工院校、专项、
面试或直接业务考核、中央驻粤），所有市县的岗位都在里面。岗位表的下载地址每年都变，所以写在 META["batches"] 里：
明年新批次出来后，加一项就行（见 .claude/CLAUDE.md「新增批次」）。
"""
from lib.http import FetchError, download
from lib.schema import make_job
from lib.xlsx import read_sheets

NOTICE = "https://hrss.gd.gov.cn/zwgk/sydwzp/zpgg/content/post_4848983.html"
TABLE = "https://hrss.gd.gov.cn/attachment/0/605/605123/4848983.xlsx"

META = dict(
    name="广东",
    order=10,
    list_url="https://hrss.gd.gov.cn/zwgk/sydwzp/index.html",
    note="岗位表按考区（市）分，含省直和中央驻粤单位；考试一般为笔试+面试，部分岗位只面试或直接业务考核。",
    batches={
        "2026-jizhong": dict(
            name="2026年集中公开招聘高校毕业生",
            published="2026-01-27",
            signup_start="2026-02-02",
            signup_end="2026-02-06",
            exam="笔试 2026年3月",
            notice_url=NOTICE,
            table_url=TABLE,
            min_jobs=5000,    # 岗位表里至少应该有这么多岗位；少了多半是下载或解析不全
            fresh_rule=dict(kind="unplaced", cohort=2026, window=2),     # 规则的含义见 lib/match.py 的 fresh_verdict
            fresh_note=("报考指南第 4 问：考生类别为「应届毕业生」的岗位，可报考 ① 2026 届普通高校、职业学校毕业生（非在职）；"
                        "② 2026 届技工院校毕业生（非在职）；③ 2024、2025 届普通高校毕业生（非在职）中「未落实工作单位」的人员；"
                        "④ 留学回国未落实工作单位的人员；⑤ 基层服务项目人员等。判断标准是「非在职」和「未落实工作单位」，"
                        "报考指南没有写缴纳社保与应届身份的关系；入职后又离职算不算「未落实」，要以当年指南为准或打咨询电话确认。"
                        "考生类别为「不限」的岗位面向所有符合条件的人，并且允许以非最高学历的专业报考（第 11 问）。"),
        ),
    },
)

# 岗位表列名 -> 标准字段。同一个字段有多列时（如两种资格证书）合并
COLUMNS = {
    "考区": "city", "岗位代码": "id", "招聘单位": "unit", "工作部门": "dept", "岗位职责任务": "duty",
    "岗位等级": "grade", "聘用人数": "headcount", "考生类别": "fresh", "政治面貌": "politics",
    "学历要求": "education", "学位要求": "degree",
    "专业要求(大专)": "major_college", "专业要求(本科)": "major_bachelor", "专业要求(研究生)": "major_graduate",
    "年龄": "age", "（放宽年龄）硕士研究生年龄要求": "age_relaxed", "工作经历": "experience",
    "准入类专业技术职业资格": "certs", "准入类技能人员职业资格": "certs", "职称等级": "title_req",
    "专项招聘对象": "special", "其他条件": "other", "残疾人岗位其他条件": "other", "考试方式": "exam",
}
JOIN = {"certs": "、", "other": "；"}


def fetch():
    """下载每个批次的岗位表并解析。下载不全 / 格式变了就抛异常（不要返回半截数据）。"""
    jobs = []
    for bkey, batch in META["batches"].items():
        path = download(batch["table_url"], f"guangdong/{bkey}.xlsx", what=f"广东 {bkey} 岗位表")
        got = []
        for sheet, rows in read_sheets(path, require=("岗位代码", "招聘单位", "考区")):
            default_exam = "面试或直接业务考核" if "直接业务考核" in sheet else "笔试+面试"
            for r in rows:
                f, extra = {}, {"岗位表": sheet}
                for col, val in r.items():
                    if col in COLUMNS and val:
                        field = COLUMNS[col]
                        f[field] = (f[field] + JOIN[field] + val) if field in f else val
                    elif val and col not in COLUMNS:
                        extra[col] = val
                if "职称系列" in extra and f.get("title_req"):     # 职称等级 + 职称系列 合成一句
                    f["title_req"] += f"（{extra['职称系列']}）"
                f.setdefault("exam", default_exam)
                got.append(make_job(batch=bkey, url="", extra=extra, **f))
        if len(got) < batch["min_jobs"]:
            raise FetchError(f"广东 {bkey} 只解析出 {len(got)} 个岗位，少于预期的 {batch['min_jobs']}，岗位表可能变了")
        print(f"  {bkey}: {len(got)} 个岗位", flush=True)
        jobs += got
    return jobs
