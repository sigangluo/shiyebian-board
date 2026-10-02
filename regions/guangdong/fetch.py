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
            exam_info=dict(                 # 考试与成绩摘要：逐条对照公告原文，写不清楚的就写「公告未写明」，不要靠印象补
                written="笔试主要测评基本能力（公告未列科目和题型，以当年笔试公告和考试大纲为准）",
                written_date="2026年3月14日 15:00—16:30",
                shortlist="笔试成绩在笔试结束后 20 个工作日内公布；合格分数线由县级以上事业单位人事综合管理部门划定；在笔试合格者中按岗位招聘人数 1:5 的比例、依笔试成绩由高到低确定入围面试人员（合格人数不足的全部入围）",
                interview="入围后先资格复审，再由事业单位或其主管部门组织面试，采取结构化面试、试讲、业务考核和技能测试等方式，面试成绩当场公布；部分岗位为面试或直接业务考核，不设笔试",
                score="综合成绩 = 笔试成绩 × 50% + 面试成绩 × 50%（面试或直接业务考核岗位：综合成绩 = 面试或业务考核成绩）",
                after="综合成绩合格者按综合成绩由高到低、等额确定体检人员，之后考察；拟聘用人员公示 5 个工作日，公示期满 30 日内备案并签订聘用合同，设试用期",
                notes=[
                    "「笔试+面试」岗位须在规定时间内登录招聘系统确认是否参加笔试（本批次为 2 月 26 日 9:00 至 27 日 16:00），公告未写明逾期后果，务必按时确认",
                    "汕头、韶关、河源、梅州、惠州、汕尾、江门、阳江、湛江、茂名、肇庆、清远、潮州、揭阳、云浮等市的乡镇事业单位聘用人员，应在招聘单位服务不少于 5 年",
                ],
                sources=[["招聘公告", NOTICE], ["笔试时间安排公告", "https://hrss.gd.gov.cn/zwgk/sydwzp/zpgg/content/post_4856733.html"]],
                checked="2026-10-02",
            ),
            notice_url=NOTICE,
            table_url=TABLE,
            min_jobs=5000,    # 岗位表里至少应该有这么多岗位；少了多半是下载或解析不全
            fresh_rule=dict(kind="unplaced", cohort=2026, window=2),     # 规则的含义见 lib/match.py 的 fresh_verdict
            fresh_src="报考指南第 4 问、第 11 问",
            fresh_note=("考生类别条件为「应届毕业生」的岗位，可报考：① 国家统一招生的 2026 届普通高校、职业学校毕业生（非在职）；② 2026 届技工院校毕业生（非在职）；③ 国家统一招生的 2024、2025 届普通高校毕业生（非在职）未落实工作单位的人员；④ 2024 年 1 月 1 日至 2026 年 2 月 2 日期间取得国（境）外学历学位且未落实工作单位的留学回国人员，并在规定时间内完成教育部门认证；⑤ 正在参加或服务期满且考核合格后 2 年内的基层服务项目人员；⑥ 面向社会招收的普通高校应届毕业生住院医师规范化培训对象，于 2026 年 1 月 1 日至报名首日培训合格，且选择报考医疗卫生机构岗位的人员。"
                        "招聘岗位考生类别条件为「应届毕业生」的，应聘人员不得以非最高学历专业报考，必须以最高学历专业报考。"
                        "招聘岗位考生类别条件为「不限」的，应聘人员可以非最高学历专业报考。"),
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
