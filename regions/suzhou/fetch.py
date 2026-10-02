"""苏州市市属事业单位公开招聘（苏州市人力资源和社会保障局 hrss.suzhou.gov.cn）。

只含市属这一批。吴江、相城等区另行公告，不在这里。
岗位表是公告页上的 xls：两层表头，没有单独的「招聘对象」列，应届、性别写在「其他条件」里，
用逗号隔开。专业只有名称（参照《江苏省公务员专业参考目录》，没有代码）。
"""
import re

from lib.conditions import split_conditions
from lib.http import FetchError, download
from lib.normalize import education_text, major_columns
from lib.schema import make_job
from lib.xlsx import read_sheets

NOTICE = "https://hrss.suzhou.gov.cn/szrskszl/sydwkszt/202603/c6fb537f773c4ef7a953b94ab20eeead.shtml"
TABLE = ("https://hrss.suzhou.gov.cn/szrskszl/sydwkszt/202603/"
         "c6fb537f773c4ef7a953b94ab20eeead/files/f76efb5e55614cad86c848f1b5224b11.xls")
OUTLINE = "https://jshrss.jiangsu.gov.cn/art/2026/3/18/art_93341_11743853.html"
_MALE = re.compile(r"^(?:适合|限)?男性$")
_FEMALE = re.compile(r"^(?:适合|限)?女性$")
_FRESH = re.compile(r"^\d{4}年毕业生$")

META = dict(
    name="苏州",
    order=54,
    list_url="https://hrss.suzhou.gov.cn/szrskszl/sydwkszt/list.shtml",
    note="只含苏州市属事业单位公开招聘。各区（吴江、相城等）另行公告，暂未接入。",
    batches={
        "2026-shishu": dict(
            name="市属事业单位2026年公开招聘",
            published="2026-03-18",
            signup_start="2026-03-21",
            signup_end="2026-03-25",
            exam="笔试 2026年4月18日",
            exam_info=dict(
                written="《综合知识和能力素质》，闭卷，参加江苏省事业单位统一公开招聘笔试。管理类与各类专业技术岗位科目名称相同、试卷不同；经济类中会计与审计同卷，统计与其他经济同卷，「其他类」专业技术与管理类同卷。不指定辅导用书",
                written_date="2026年4月18日，具体场次以准考证为准",
                syllabus=[
                    ["综合知识", "学习理解掌握党的创新理论及党和国家方针政策的情况，以及在自然、人文社科等方面应知应会的基本知识和运用这些知识分析判断的能力"],
                    ["基本能力", "阅读理解、判断推理、数量关系、综合分析、解决问题、文字表达，以及履行岗位职责的必备能力"],
                    ["通用类专业技术岗位：专业知识和专业能力", "测试掌握本专业基本理论、基本知识的程度和实际应用能力。范围同《江苏省2026年省属事业单位统一公开招聘人员公共科目笔试考试大纲》"],
                ],
                shortlist="笔试百分制，合格分数线 50 分。在合格者中按 1:3 从高分到低分确定面试人选，不足比例的按实际合格人数确定。开考比例一般为 1:3，岗位另有要求的除外，未达到的将核减或取消",
                interview="管理岗位为结构化面试，由人社部门组织；专业技术岗位由主管部门组织，考查业务能力和综合素质。面试百分制，合格分数线 60 分，不合格者不计算总成绩",
                score="总成绩 = 笔试成绩 × 40% + 面试成绩 × 60%。总成绩相同的，取笔试成绩高者；仍相同的另行加试",
                after="在面试合格人员中按总成绩 1:1 确定体检人员；拟聘用人员公示 7 个工作日。聘用合同不低于 3 年并约定试用期，订立 3 年以上合同的，应在招聘单位最低服务 3 年（含试用期）",
                notes=[
                    "定向招聘退役大学生士兵的岗位（岗位代码 081）限苏州户籍（不含在苏高校学生集体户口）或苏州生源",
                ],
                sources=[["招聘公告", NOTICE], ["公共科目笔试考试大纲", OUTLINE]],
                checked="2026-10-02",
            ),
            notice_url=NOTICE,
            table_url=TABLE,
            min_jobs=90,
            fresh_rule=dict(kind="unemployed", cohort=2026, window=2),
            age_default=dict(max=38, relaxed=45),    # 岗位表没写年龄时，公告统一规定 38 周岁以下，部分情形放宽（招聘公告第 4 条）
            fresh_src="招聘公告",
            fresh_note=("招聘条件中的「2026年毕业生」，指在 2026 年毕业并已取得学历（学位）证书，且报名时无工作单位的人员。"
                        "能够提供《毕业生就业推荐表》的 2026 年普通高校毕业生，取得证书的日期可放宽至 2026 年 12 月 31 日。"
                        "2024 年、2025 年普通高校毕业生，如报名时无工作单位，可应聘面向 2026 年毕业生的岗位。"
                        "基层服务项目志愿者（参加前无工作经历，服务期满且考核合格后 2 年内）、退役 1 年内的应届入伍人员也可应聘。"
                        "户籍不限"
                        "（定向招聘退役大学生士兵的岗位除外，该岗位限苏州户籍或苏州生源）。"),
        ),
    },
)


def _parse_other(text):
    """「其他条件」是用逗号接起来的短句：应届、性别各归各，剩下的交给 split_conditions。

    返回 (考生类别, 性别要求或空串, 剩余文字)。男女两种都写到的，不把性别拆出去。
    """
    fresh, gender_hits, rest = "", [], []
    for raw in re.split(r"[，,；;]", text or ""):
        p = raw.strip()
        if not p:
            continue
        if _FRESH.fullmatch(p):
            fresh = p
        elif _MALE.fullmatch(p):
            gender_hits.append(("男", p))
        elif _FEMALE.fullmatch(p):
            gender_hits.append(("女", p))
        else:
            rest.append(p)
    kinds = {g for g, _ in gender_hits}
    if len(kinds) == 1:
        gender = next(iter(kinds))
    else:
        gender = ""
        rest.extend(p for _, p in gender_hits)
    return fresh, gender, "，".join(rest)


def fetch():
    """下载每个批次的岗位表并解析。下载不全 / 格式变了就抛异常（不要返回半截数据）。"""
    jobs = []
    for bkey, batch in META["batches"].items():
        path = download(batch["table_url"], f"suzhou/{bkey}.xls", what=f"苏州 {bkey} 岗位表")
        got = []
        for _, rows in read_sheets(path, require=("岗位名称", "学历", "专业"), header_rows=2, scan=5):
            for r in rows:
                edu = r.get("学历") or ""
                raw_other = r.get("其他条件") or ""
                fresh, gender, rest = _parse_other(raw_other)
                cond = split_conditions(rest)
                extra = {"单位代码": r.get("单位代码"), "开考比例": r.get("开考比例"),
                         "其他条件原文": raw_other, "工作要求（不影响报考）": cond["soft"],
                         "咨询电话": r.get("咨询电话（区号0512）")}
                if gender:
                    extra["性别要求"] = gender
                got.append(make_job(
                    id=f"{r.get('单位代码')}-{r.get('岗位代码')}", batch=bkey, unit=r.get("单位名称"), city="苏州",
                    dept=r.get("岗位名称"), duty=r.get("岗位简介"), grade=r.get("岗位类别"),
                    headcount=r.get("招聘人数"), fresh=fresh, education=education_text(edu),
                    **major_columns(r.get("专业"), edu),
                    age=cond["age"], age_relaxed=cond["age_relaxed"], experience=cond["experience"],
                    certs=cond["certs"], title_req=cond["title"], politics=cond["politics"],
                    hukou=cond["hukou"], special=cond["special"], other=cond["other"], exam="笔试+面试",
                    extra=extra))
        if len(got) < batch["min_jobs"]:
            raise FetchError(f"苏州 {bkey} 只解析出 {len(got)} 个岗位，少于预期的 {batch['min_jobs']}，岗位表可能变了")
        print(f"  {bkey}: {len(got)} 个岗位", flush=True)
        jobs += got
    return jobs
