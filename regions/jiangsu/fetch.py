"""江苏省省属事业单位统一公开招聘（江苏省人力资源和社会保障厅 jshrss.jiangsu.gov.cn）。

只含**省属**单位（含部属驻苏单位）。各市、县自行组织的招聘不在这里。
公告和岗位表这里取的是江苏省税务局网站（jiangsu.chinatax.gov.cn）上转载的同一份官方公告——省人社厅网站的页面抓不稳，
转载页的公告全文和附件与官方一致。附件是 .xls：三层表头，没有岗位代码列以外的编号（用「单位代码-岗位代码」），
专业只有名称（取自《江苏省公务员专业参考目录》，没有代码），招聘对象写成「2026年毕业生」「社会人员」「不限」。
"""
import re

from lib.conditions import split_conditions
from lib.http import FetchError, download
from lib.normalize import education_text, major_columns
from lib.schema import make_job
from lib.xlsx import read_sheets

HOST = "https://jiangsu.chinatax.gov.cn"
NOTICE = HOST + "/art/2026/3/18/art_8274_1719146.html"
MERGED = ("主管部门", "名称", "单位代码", "经费来源")        # 岗位表里合并单元格的列
CITIES = ("南京", "苏州", "无锡", "常州", "镇江", "扬州", "泰州", "南通", "盐城", "淮安", "宿迁", "徐州", "连云港")

META = dict(
    name="江苏（省属）",
    order=50,
    list_url="http://jshrss.jiangsu.gov.cn/",
    note="只含江苏省省属事业单位（以及部属驻苏单位），不含各市、县自行组织的招聘。公告和岗位表来自江苏省税务局网站转载的官方公告。",
    batches={
        "2026-shengshu": dict(
            name="省属事业单位2026年统一公开招聘",
            published="2026-03-18",
            signup_start="2026-03-21",
            signup_end="2026-03-25",
            exam="笔试 2026年4月18日",
            exam_info=dict(
                written="《综合知识和能力素质》，闭卷，试卷含客观题和主观题。管理类、通用类专业技术、工勤技能类岗位的试卷各不相同，通用类专业技术中的法律类、计算机类、经济类（会计、审计 / 统计、其他经济）也各用不同试卷，「其他专技类」与管理类同卷；管理类和通用类专业技术岗位 150 分钟、满分 100 分",
                written_date="2026年4月18日 9:00—11:30",
                syllabus=[
                    ["综合知识", "学习理解掌握党的创新理论及党和国家方针政策的情况，以及在自然、人文社科等方面应知应会的基本知识和运用这些知识分析判断的能力（管理类、通用类专业技术、工勤技能类均考）"],
                    ["基本能力", "阅读理解能力、判断推理能力、处理数量关系能力、综合分析能力、解决问题能力、文字表达能力，以及履行岗位职责的必备能力"],
                    ["题型", "单项选择题、多项选择题、简答题、论述题、综合分析题、案例分析题、实务题、材料处理题、写作题等，试卷均含主观题和客观题，具体选取其中若干种"],
                    ["通用类专业技术岗位：专业知识和专业能力", "测试掌握本专业基本理论、基本知识的程度和实际应用能力。计算机类：计算机软硬件、操作系统、程序设计、常用办公软件，多媒体信息技术，计算机信息安全技术的基本原理及关键技术，关系数据库的基本概念及应用，软件工程的基本概念和软件分析、设计的基本方法，计算机网络的概念、理论和相关应用等"],
                ],
                shortlist="笔试合格分数线由省里统一划定；在笔试合格者中按 1:3（岗位表另有要求的从其要求）从高分到低分确定参加资格复审人选；笔试开考比例一般为 1:3，未达到的岗位将核减或取消",
                interview="面试（含专业测试、技能操作）原则上由各招聘单位的主管部门组织，成绩现场通知；有竞争的岗位面试合格线为面试总分的 50%，没有竞争的为 60%",
                score="总成绩 = 笔试成绩 × 50% + 面试成绩 × 50%（百分制）",
                after="面试合格者按总成绩由高到低、依岗位表「考察体检比例」确定考察体检人员；拟聘用人员公示 7 个工作日；聘用合同一般不低于 3 年并约定试用期，订立 3 年以上合同的，应在招聘单位最低服务 3 年（含试用期）",
                notes=[
                    "招聘条件有大学英语四级或六级要求的，需提供合格证书；只有成绩通知单的，成绩原则上不低于 425 分",
                ],
                sources=[["招聘公告", NOTICE], ["公共科目笔试考试大纲", "https://jshrss.jiangsu.gov.cn/art/2026/3/18/art_93341_11743853.html"]],
                checked="2026-10-02",
            ),
            notice_url=NOTICE,
            table_url=HOST + "/module/download/downfile.jsp?classid=0&filename=7cc501120b7e4af988cc272660d3128b.xls",
            min_jobs=400,
            fresh_rule=dict(kind="unemployed", cohort=2026, window=2),
            fresh_note=("公告：招聘条件中的「2026年毕业生」，指在 2026 年毕业并已取得学历（学位）证书，**且报名时无工作单位**的人员。"
                        "2024、2025 年普通高校毕业生，如报名时无工作单位，可应聘面向 2026 年毕业生的岗位。"
                        "基层服务项目志愿者（参加前无工作经历，服务期满且考核合格后 2 年内）、退役 1 年内的应届入伍人员也可应聘。"
                        "判断标准是「报名时有没有工作单位」，没有提缴纳社保。"
                        "招聘对象为「社会人员」的岗位面向非应届人员，一般要求工作经历。本次招聘原则上不设户籍限制（残疾人岗位除外）。"),
        ),
    },
)


def _city(unit, note):
    m = re.search(r"工作地点[为在]?\s*([一-鿿]{2,3})", note or "")
    for c in CITIES:
        if (m and c in m.group(1)) or (not m and c in (unit or "")):
            return c
    return "江苏"


def fetch():
    """下载每个批次的岗位表并解析。下载不全 / 格式变了就抛异常（不要返回半截数据）。"""
    jobs = []
    for bkey, batch in META["batches"].items():
        path = download(batch["table_url"], f"jiangsu/{bkey}.xls", what=f"江苏 {bkey} 岗位表")
        got = []
        for _, rows in read_sheets(path, require=("岗位名称", "招聘对象", "学历"), header_rows=3, scan=5):
            last = {}
            for r in rows:
                for col in MERGED:        # 单位这几列是合并单元格，只有每个单位的第一行有值，往下填充
                    if r.get(col):
                        last[col] = r[col]
                    else:
                        r[col] = last.get(col)
                target = r.get("招聘对象") or ""
                note = r.get("其他说明") or ""
                edu = r.get("学历") or ""
                major = r.get("专业") or ""
                cond = split_conditions(r.get("其他条件"))
                special = "；".join(x for x in (
                    cond["special"], "残疾人岗位" if "残疾人" in target else "",
                    "编外（不进事业编制）" if "编外" in note else "") if x)
                got.append(make_job(
                    id=f"{r.get('单位代码')}-{r.get('岗位代码')}", batch=bkey, unit=r.get("名称"), city=_city(r.get("名称"), note),
                    dept=r.get("岗位名称"), duty=r.get("岗位描述"), grade=r.get("岗位类别"),
                    headcount=r.get("拟招聘人数"), fresh=target, education=education_text(edu),
                    **major_columns(major, edu),
                    age=cond["age"], age_relaxed=cond["age_relaxed"], experience=cond["experience"],
                    certs=cond["certs"], title_req=cond["title"], politics=cond["politics"], special=special,
                    hukou=cond["hukou"], other=cond["other"], exam="笔试+面试",
                    extra={"主管部门": r.get("主管部门"), "经费来源": r.get("经费来源"), "其他说明": note,
                           "考试形式和比例": r.get("招聘部门（单位）考试形式和所占比例"), "其他条件原文": r.get("其他条件"),
                           "咨询电话": r.get("政策咨询电话、传真、联系人"), "工作要求（不影响报考）": cond["soft"]}))
        if len(got) < batch["min_jobs"]:
            raise FetchError(f"江苏 {bkey} 只解析出 {len(got)} 个岗位，少于预期的 {batch['min_jobs']}，岗位表可能变了")
        print(f"  {bkey}: {len(got)} 个岗位", flush=True)
        jobs += got
    return jobs
