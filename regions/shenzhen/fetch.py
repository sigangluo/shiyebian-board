"""深圳市事业单位公开招聘（https://hrss.sz.gov.cn/ 人力资源和社会保障局 → 事业单位招聘）。

深圳每年集中招聘一次高校毕业生，比广东省的批次早（2026 年这批 2025 年 11 月底发公告、12 月初报名）。
公告附两个 .xls 岗位表：「笔试+面试」和「面试或者直接业务考核」。
和广东省的表不同：表头是两层合并表头；专业只有一栏，写成「本科：…；研究生：…」；
年龄、政治面貌、工作经历、证书都挤在「与岗位有关的其它条件」一段话里（lib/conditions.py 负责拆）。
岗位表的下载地址每年都变，写在 META["batches"] 里，明年新批次出来后加一项就行。
"""
import re

from lib.conditions import split_conditions
from lib.http import FetchError, download
from lib.normalize import education_text
from lib.schema import make_job
from lib.xlsx import read_sheets

NOTICE = "https://hrss.sz.gov.cn/gkmlpt/content/12/12516/post_12516345.html"

META = dict(
    name="深圳",
    order=20,
    list_url="https://hrss.sz.gov.cn/",
    note="深圳市属和各区事业单位的岗位在同一份表里；笔试分一般类、教育类、医疗类，计算机岗位一般考「一般类」。",
    batches={
        "2026-jizhong": dict(
            name="2026年集中公开招聘高校毕业生",
            published="2025-11-25",
            signup_start="2025-12-01",
            signup_end="2025-12-05",
            exam="笔试 2025年12月27日",
            notice_url=NOTICE,
            tables=[("https://hrss.sz.gov.cn/attachment/1/1653/1653473/12516345.xls", "笔试+面试"),
                    ("https://hrss.sz.gov.cn/attachment/1/1653/1653467/12516345.xls", "面试或直接业务考核")],
            min_jobs=400,
            fresh_rule=dict(kind="unplaced", cohort=2026, window=2),
            fresh_note=("有关问题解答第 1 问：考生类别为「应届毕业生」的岗位，可报考 ① 国家统一招生的 2026 届普通高校、职业学校毕业生（非在职）；"
                        "② 2026 年应届中外合作办学毕业生（非在职）；③ 留学回国未落实工作单位的人员；"
                        "④ 国家统一招生的 2024、2025 届普通高校毕业生（非在职）中「未落实工作单位」的人员；⑤ 基层服务项目人员等。"
                        "判断标准是「非在职」和「未落实工作单位」，没有提缴纳社保。入职后又离职算不算「未落实」，指南没写，以当年公告为准或打咨询电话确认。"
                        "考生类别为「不限」的岗位面向所有符合条件的人，并且允许以非最高学历的专业报考。"),
        ),
    },
)

_LEVEL = re.compile(r"(大专|专科|本科|研究生)\s*[：:]")


def split_majors(text, education):
    """'本科：A（B0801）；B（B0802）\\n研究生：C（A0812）' -> {'major_college', 'major_bachelor', 'major_graduate'}。

    没有「本科：」这类前缀的，整段放进岗位学历对应的那一栏（研究生岗位放研究生栏，其余放本科栏）。
    """
    out = {"major_college": "", "major_bachelor": "", "major_graduate": ""}
    key = {"大专": "major_college", "专科": "major_college", "本科": "major_bachelor", "研究生": "major_graduate"}
    marks = list(_LEVEL.finditer(text or ""))
    if not marks:
        if (text or "").strip():
            out["major_graduate" if "研究生" in education else "major_bachelor"] = text.strip()
        return out
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        col = key[m.group(1)]
        out[col] = (out[col] + "；" if out[col] else "") + text[m.end():end].strip().strip("；;")
    return out


def fetch():
    """下载每个批次的岗位表并解析。下载不全 / 格式变了就抛异常（不要返回半截数据）。"""
    jobs = []
    for bkey, batch in META["batches"].items():
        got = []
        for n, (url, exam) in enumerate(batch["tables"]):
            path = download(url, f"shenzhen/{bkey}-{n}.xls", what=f"深圳 {bkey} 岗位表 {n + 1}")
            for sheet, rows in read_sheets(path, require=("岗位编码", "招聘单位", "学历"), header_rows=2):
                for r in rows:
                    cond = split_conditions(r.get("与岗位有关的其它条件"))
                    edu = r.get("学历") or ""
                    wtype = r.get("笔试类别")
                    got.append(make_job(
                        id=r["岗位编码"], batch=bkey, unit=r.get("招聘单位"), city="深圳",
                        dept=r.get("岗位名称"), duty=r.get("招聘岗位职责"),
                        grade=" ".join(x for x in (r.get("岗位类别"), r.get("岗位等级")) if x),
                        headcount=r.get("拟聘人数"), fresh=r.get("考生类别"),
                        education=education_text(edu, r.get("学位")), degree=r.get("学位"), special=cond["special"],
                        **split_majors(r.get("专业"), edu),
                        age=cond["age"], age_relaxed=cond["age_relaxed"], experience=cond["experience"],
                        certs=cond["certs"], title_req="；".join(x for x in (r.get("最低专业技术资格"), cond["title"]) if x), politics=cond["politics"],
                        hukou=cond["hukou"], other="；".join(x for x in (cond["other"], r.get("备注")) if x),
                        exam=f"{exam}（{wtype}）" if wtype else exam,
                        extra={"所属市区": r.get("所属市区"), "主管单位": r.get("主管单位"),
                               "其它条件原文": r.get("与岗位有关的其它条件"), "年龄放宽(其他)": cond["age_other"],
                               "工作要求（不影响报考）": cond["soft"]}))
        if len(got) < batch["min_jobs"]:
            raise FetchError(f"深圳 {bkey} 只解析出 {len(got)} 个岗位，少于预期的 {batch['min_jobs']}，岗位表可能变了")
        print(f"  {bkey}: {len(got)} 个岗位", flush=True)
        jobs += got
    return jobs
