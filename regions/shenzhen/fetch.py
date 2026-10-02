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
            exam_info=dict(
                written="分一般类、教育类、医疗类三类，主要测评基本能力（公告未列科目和题型，以当年笔试公告和考试大纲为准）",
                written_date="2025年12月27日 9:00—10:30",
                shortlist="笔试成绩在笔试结束后 20 个工作日内公布；合格分数线由市、区事业单位人事综合管理部门划定；在笔试合格者中按岗位招聘人数 1:5 的比例、依笔试成绩由高到低确定入围面试人员（合格人数不足的全部入围）",
                interview="入围后先资格复审，再由事业单位或其主管部门组织面试，采取结构化面试、试讲、业务考核和技能测试等方式，面试成绩当场公布；部分岗位为面试或直接业务考核，不设笔试",
                score="综合成绩 = 笔试成绩 × 50% + 面试成绩 × 50%（面试或直接业务考核岗位：综合成绩 = 面试或业务考核成绩）",
                after="综合成绩合格者按综合成绩由高到低、等额确定体检人员，之后考察；拟聘用人员公示 5 个工作日，公示期满 30 日内备案并签订聘用合同，设试用期",
                notes=[
                    "「笔试+面试」岗位须在规定时间内登录招聘系统确认是否参加笔试（本批次为 12 月 9 日 9:00 至 10 日 16:00），公告未写明逾期后果，务必按时确认",
                    "因应聘人员原因，自招聘公告发布之日起 1 年内未办理聘用备案的，取消聘用资格",
                ],
                sources=[["招聘公告", NOTICE]],
                checked="2026-10-02",
            ),
            notice_url=NOTICE,
            tables=[("https://hrss.sz.gov.cn/attachment/1/1653/1653473/12516345.xls", "笔试+面试"),
                    ("https://hrss.sz.gov.cn/attachment/1/1653/1653467/12516345.xls", "面试或直接业务考核")],
            min_jobs=400,
            fresh_rule=dict(kind="unplaced", cohort=2026, window=2),
            fresh_src="公告附件3《深圳市事业单位2026年公开招聘高校毕业生有关问题的解答》",
            fresh_note=("考生类别条件为「应届毕业生」的岗位，可报考：① 国家统一招生的 2026 届普通高校、职业学校毕业生（非在职），须于 2026 年 9 月 30 日前取得相应毕业证书、学位证书及岗位要求的其他证明材料；② 在境内就读的中外合作办学 2026 年应届毕业生（非在职），须于 2026 年 12 月 31 日前取得相应毕业证书、学位证书及岗位要求的其他证明材料；③ 2024 年 1 月 1 日至 2025 年 12 月 1 日期间取得国（境）外学历学位且未落实工作单位的留学回国人员，并在规定时间内完成教育部门认证；④ 国家统一招生的 2024、2025 届普通高校毕业生（非在职）未落实工作单位的人员；⑤ 2024、2025 年在境内就读的中外合作办学应届毕业生（非在职）未落实工作单位的人员；⑥ 正在参加或服务期满且考核合格后 2 年内的基层服务项目人员；⑦ 面向社会招收的普通高校应届毕业生住院医师规范化培训对象，于 2025 年 1 月 1 日至报名首日培训合格，且选择报考医疗卫生机构岗位的人员。"
                        "以上 ④ 至 ⑦ 列明的报考者均须于面试资格复审前取得相应毕业证书、学位证书。"
                        "招聘岗位考生类别条件为「应届毕业生」的，应聘人员不得以非最高学历专业报考，必须以最高学历专业报考。"
                        "招聘岗位考生类别条件为「不限」的，应聘人员可以非最高学历专业报考。"),
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
