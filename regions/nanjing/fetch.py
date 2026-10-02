"""南京市事业单位统一公开招聘（南京市人力资源和社会保障局 rsj.nanjing.gov.cn）。

只含市人社局为市、区部分事业单位管理类岗位和通用类专业技术岗位提供的统一招聘。
紧缺人才直接考察、教育卫生等行业自主招聘不在这里。
岗位表是公告页上的 xls：两层表头，专业只有名称（参照《江苏省公务员专业参考目录》，没有代码），
招聘对象写成「2026年毕业生」「社会人员」「不限」「残疾人」。
"""
from lib.conditions import split_conditions
from lib.http import FetchError, download
from lib.normalize import education_text, major_columns
from lib.schema import make_job
from lib.xlsx import read_sheets

NOTICE = "https://rsj.nanjing.gov.cn/njsrlzyhshbzj/202603/t20260318_5807842.html"
TABLE = "https://rsj.nanjing.gov.cn/njsrlzyhshbzj/202603/P020260319617384616267.xls"
OUTLINE = "https://jshrss.jiangsu.gov.cn/art/2026/3/18/art_93341_11743853.html"

META = dict(
    name="南京",
    order=52,
    list_url="https://rsj.nanjing.gov.cn/",
    note="只含南京市统一招聘的管理类和通用类专业技术岗位（市级和部分区）。紧缺人才直接考察、教育卫生等行业自主招聘暂未接入。岗位表中有少量编外岗位。",
    batches={
        "2026-tongyi": dict(
            name="2026年事业单位统一公开招聘",
            published="2026-03-18",
            signup_start="2026-03-21",
            signup_end="2026-03-25",
            exam="笔试 2026年4月18日",
            exam_info=dict(
                written="《综合知识和能力素质》，参加江苏省事业单位统一公开招聘笔试。管理类与通用类专业技术（法律类、计算机类、经济类会计审计、经济类统计及其他、其他专技类）内容各不相同，「其他专技类」与管理类同卷；不指定教材",
                written_date="2026年4月18日 9:00—11:30（考点在南京）",
                syllabus=[
                    ["综合知识", "学习理解掌握党的创新理论及党和国家方针政策的情况，以及在自然、人文社科等方面应知应会的基本知识和运用这些知识分析判断的能力"],
                    ["基本能力", "阅读理解、判断推理、数量关系、综合分析、解决问题、文字表达，以及履行岗位职责的必备能力"],
                    ["通用类专业技术岗位：专业知识和专业能力", "测试掌握本专业基本理论、基本知识的程度和实际应用能力。范围同《江苏省2026年省属事业单位统一公开招聘人员公共科目笔试考试大纲》"],
                ],
                shortlist="笔试合格分数线由市事业单位人事综合管理部门划定；在合格者中按岗位开考比例从高分到低分确定资格复审人选。开考比例见岗位表，未达到的将核减或取消",
                interview="原则上由主管部门组织，或委托市人事考试中心统一组织；有竞争的岗位，面试各项合格线为该项总分的 50%，没有竞争的为 60%。具体形式和所占比例见岗位表",
                score="总成绩为百分制，计算方式见《岗位信息表》。多数岗位为笔试 × 50% + 面试 × 50%，部分岗位为笔试 × 40% + 面试 × 60%",
                after="在面试合格人员中按总成绩 1:1 确定考察体检人员；拟聘用人员公示 7 个工作日。市、区所属单位最低服务 3 年（含试用期），街镇所属单位最低服务 5 年（含试用期）",
                notes=[
                    "招聘条件有大学英语四级或六级要求的，需提供合格证书；只有成绩通知单的，成绩原则上不低于 425 分",
                    "本次招聘原则上不设户籍限制。应聘残疾人岗位的，须具有南京户籍或为南京生源，并持有有效残疾人证或残疾军人证",
                ],
                sources=[["招聘公告", NOTICE], ["公共科目笔试考试大纲", OUTLINE]],
                checked="2026-10-02",
            ),
            notice_url=NOTICE,
            table_url=TABLE,
            min_jobs=500,
            fresh_rule=dict(kind="unemployed", cohort=2026, window=2),
            fresh_src="招聘公告",
            fresh_note=("招聘条件中的「2026年毕业生」，指在 2026 年毕业并已取得学历（学位）证书，且报名时无工作单位的人员。"
                        "能够提供《毕业生就业推荐表》的 2026 年普通高校毕业生，取得证书的日期可放宽至 2026 年 12 月 31 日。"
                        "2024 年、2025 年普通高校毕业生，如报名时无工作单位，可应聘面向 2026 年毕业生的岗位。"
                        "基层服务项目志愿者（参加前无工作经历，服务期满且考核合格后 2 年内）、退役 1 年内的应届入伍人员也可应聘。"
                        "本次招聘原则上不设户籍限制（残疾人岗位除外）。"),
        ),
    },
)


def fetch():
    """下载每个批次的岗位表并解析。下载不全 / 格式变了就抛异常（不要返回半截数据）。"""
    jobs = []
    for bkey, batch in META["batches"].items():
        path = download(batch["table_url"], f"nanjing/{bkey}.xls", what=f"南京 {bkey} 岗位表")
        got = []
        for _, rows in read_sheets(path, require=("岗位名称", "招聘对象", "学历"), header_rows=2, scan=5):
            for r in rows:
                target = r.get("招聘对象") or ""
                edu = r.get("学历") or ""
                cond = split_conditions(r.get("其他条件"))
                special = "；".join(x for x in (
                    cond["special"],
                    "残疾人岗位" if "残疾" in target else "",
                    "编外（不进事业编制）" if "编外" in (r.get("用人方式") or "") else "",
                ) if x)
                got.append(make_job(
                    id=r["序号"], batch=bkey, unit=r.get("单位"), city="南京",
                    dept=r.get("岗位名称"), duty=r.get("岗位描述"), grade=r.get("岗位类别"),
                    headcount=r.get("招聘人数"), fresh=target, education=education_text(edu),
                    **major_columns(r.get("专业"), edu),
                    age=cond["age"], age_relaxed=cond["age_relaxed"], experience=cond["experience"],
                    certs=cond["certs"], title_req=cond["title"], politics=cond["politics"],
                    hukou=cond["hukou"], special=special, other=cond["other"],
                    exam=r.get("考试形式和所占比例") or "笔试+面试",
                    extra={"所属": r.get("所属"), "主管部门": r.get("主管部门"), "经费来源": r.get("经费来源"),
                           "笔试类别": r.get("笔试类别"), "用人方式": r.get("用人方式"), "其他说明": r.get("其他说明"),
                           "其他条件原文": r.get("其他条件"), "工作要求（不影响报考）": cond["soft"],
                           "咨询电话": r.get("政策咨询电话及信息发布网址")}))
        if len(got) < batch["min_jobs"]:
            raise FetchError(f"南京 {bkey} 只解析出 {len(got)} 个岗位，少于预期的 {batch['min_jobs']}，岗位表可能变了")
        print(f"  {bkey}: {len(got)} 个岗位", flush=True)
        jobs += got
    return jobs
