"""浙江省省属事业单位集中公开招聘（https://rlsbt.zj.gov.cn/ 浙江省人力资源和社会保障厅）。

浙江省属事业单位每年集中招聘两次（上半年、下半年），公告附一个 xlsx「招聘计划表」，里面有「单位信息表」和「岗位信息表」两个 sheet。
注意：这里只有**省属**单位。各市、县自行组织的招聘不在这里。
岗位表的下载链接是页面里的动态链接（带加密参数），所以每次从公告页上现抓，不写死在这里。

和广东 / 深圳的表不同：表头三层；没有岗位代码（用序号）；专业只有一栏，代码是纯数字（学科门类 08、一级学科 0812）；
对象类别分「应届毕业生」「机关事业单位正式在编人员」「不限」三种。
"""
import re
import urllib.parse

from lib.conditions import split_conditions
from lib.http import FetchError, download, get_text
from lib.schema import make_job
from lib.xlsx import read_sheets

HOST = "https://rlsbt.zj.gov.cn"
NOTICE = HOST + "/col/col1229743683/art/2026/art_99f2702a91aa43edaab3ef5037d8d0ad.html"

META = dict(
    name="浙江（省属）",
    order=30,
    list_url="https://rlsbt.zj.gov.cn/col/col1229743683/index.html",
    note="只含浙江省省属事业单位（以及部属驻浙单位），不含各市、县自行组织的招聘。每年上半年、下半年各一批。",
    batches={
        "2026-h1": dict(
            name="省属事业单位2026年上半年集中公开招聘",
            published="2026-03-17",
            signup_start="2026-03-19",
            signup_end="2026-03-25",
            exam="笔试 2026年4月25日（杭州）",
            exam_info=dict(
                written="《综合应用能力》（上午）和《职业能力倾向测验》（下午），由省人事考试院统一实施，不指定辅导用书；笔试总分 200 分，换算成百分制计入总成绩",
                written_date="2026年4月25日（杭州）：综合应用能力 9:00—11:30，职业能力倾向测验 下午 2:00—3:30",
                shortlist="笔试成绩预计 5 月 25 日前公布；按各岗位《招聘计划表》「经笔试入围比例」确定入围人员，取得有效笔试成绩的人数不超过该比例的可以全部入围；部分岗位笔试后加专业测评，测评低于 60 分不得入围面试，再按表中比例入围面试",
                interview="由主管单位组织，主要考查综合素质；岗位对专业、业务能力有要求但不安排专业测评的，在面试内容中体现；经笔试直接进入面试的岗位，以及参加面试人数不超过计划招聘人数 2 倍的岗位，面试合格线 60 分",
                score="① 笔试直接进入面试：笔试 × 50% + 面试 × 50%；② 笔试 + 专业测评 + 面试（无免笔试入围）：笔试 × 30% + （专业测评 × 50% + 面试 × 50%） × 70%；③ 有免笔试人员入围时：专业测评 × 50% + 面试 × 50%（均为百分制）",
                after="一般按 1:1 确定体检、考察对象；拟聘人员公示 5 个工作日；签订聘用合同并约定试用期",
                notes=[
                    "每位应聘人员限报同期委托省人事考试院实施笔试的省属事业单位中的一个岗位",
                    "通过资格初审并缴费确认的人数未达到开考比例的岗位，将核减招聘人数直至取消招聘计划；残疾人专项岗位无需缴费，且不设开考比例",
                ],
                sources=[["招聘公告", "https://rlsbt.zj.gov.cn/col/col1229743683/art/2026/art_aa250f574a114936b87ea93a5ca2c6b5.html"]],
                checked="2026-10-02",
            ),
            notice_url="https://rlsbt.zj.gov.cn/col/col1229743683/art/2026/art_aa250f574a114936b87ea93a5ca2c6b5.html",
            min_jobs=350,
            fresh_rule=dict(kind="year", cohort=2026),
            fresh_src="招聘公告",
            fresh_note=("招聘对象类别中的应届毕业生，主要指按学制于 2026 年内完成学业并取得学历、学位证书的普通高校毕业生；"
                        "有关政策规定视同普通高校应届毕业生同等对待的群体，也可应聘限招应届毕业生的岗位。"
                        "部分单位对取得证书的时间另有规定，见计划表「其他条件」栏。"),
        ),
        "2026-h2": dict(
            name="省属事业单位2026年下半年集中公开招聘",
            published="2026-08-11",
            signup_start="2026-08-13",
            signup_end="2026-08-19",
            exam="笔试 2026年9月19日（杭州）",
            exam_info=dict(
                written="《综合应用能力》（上午）和《职业能力倾向测验》（下午），由省人事考试院统一实施，不指定辅导用书；笔试总分 200 分，换算成百分制计入总成绩",
                written_date="2026年9月19日（杭州）：综合应用能力 9:00—11:30，职业能力倾向测验 14:00—15:30",
                shortlist="笔试成绩预计 10 月 23 日前公布；按各岗位《招聘计划表》「经笔试入围比例」栏确定入围人员；部分岗位笔试后加专业测评（见表中「专业测评」栏），测评低于 60 分不得入围面试，再按表中比例入围面试",
                interview="由主管单位组织，主要考查综合素质；岗位对专业、业务能力有要求但不安排专业测评的，在面试内容中体现；面试合格线 60 分（经笔试直接进入面试的岗位，以及参加面试人数不超过计划招聘人数 2 倍的岗位）",
                score="① 笔试直接进入面试：笔试 × 50% + 面试 × 50%；② 笔试 + 专业测评 + 面试：笔试 × 30% + （专业测评 × 50% + 面试 × 50%） × 70%；③ 有免笔试人员入围时：专业测评 × 50% + 面试 × 50%（均为百分制）",
                after="一般按 1:1 确定体检、考察对象；拟聘人员公示 5 个工作日；签订聘用合同并约定试用期",
                notes=[
                    "每位应聘人员限报同期委托省人事考试院实施笔试的省属事业单位中的一个岗位",
                    "通过资格初审并缴费确认的人数未达到开考比例的岗位，将核减招聘人数直至取消招聘计划",
                ],
                sources=[["招聘公告", NOTICE]],
                checked="2026-10-02",
            ),
            notice_url=NOTICE,
            min_jobs=80,
            fresh_rule=dict(kind="year", cohort=2026),
            fresh_src="招聘公告",
            fresh_note=("招聘对象类别分 ① 应届毕业生——主要指按学制于 2026 年内完成学业并取得学历、学位证书的普通高校毕业生"
                        "（部分岗位对取得证书的时间另有规定，见计划表「其他条件」栏），有关政策规定视同应届毕业生的群体也可应聘；"
                        "② 机关事业单位正式在编人员；③ 不限。"),
        ),
    },
)


def _table_url(notice_url):
    """从公告页里找出「招聘计划表」xlsx 的下载链接（页面里同一个附件会出现多次，取第一个 .xlsx）。"""
    page = get_text(notice_url, what="浙江 公告页")
    for href in re.findall(r'href="(/api-gateway[^"]+)"', page):
        href = href.replace("&amp;", "&")
        m = re.search(r"fileName=([^&]+)", href)
        if m and urllib.parse.unquote(m.group(1)).lower().endswith(".xlsx"):
            return HOST + href
    raise FetchError("浙江 公告页里找不到 .xlsx 招聘计划表的链接，页面结构可能变了")


def _city(location):
    """'杭州市西湖区' -> '杭州'；认不出来原样返回。"""
    loc = re.sub(r"^浙江省?", "", location or "")        # '浙江义乌' / '浙江省宁波' -> '义乌' / '宁波'
    m = re.match(r"(.+?)市", loc)
    return m.group(1) if m else loc


def fetch():
    """下载每个批次的计划表并解析。下载不全 / 格式变了就抛异常（不要返回半截数据）。"""
    jobs = []
    for bkey, batch in META["batches"].items():
        path = download(_table_url(batch["notice_url"]), f"zhejiang/{bkey}.xlsx", what=f"浙江 {bkey} 招聘计划表")
        city_of = {}
        got = []
        for _, rows in read_sheets(path, require=("单位名称", "单位所在地"), header_rows=2, scan=4, skip_sheets=("岗位信息表",)):
            for r in rows:
                city_of[re.sub(r"\s+", "", r["单位名称"])] = r["单位所在地"]
        for _, rows in read_sheets(path, require=("岗位名称", "对象类别", "学历"), header_rows=3, scan=4, skip_sheets=("单位信息表",)):
            for r in rows:
                unit = r.get("名称") or ""
                cond = split_conditions(r.get("其他条件"))
                exp = "；".join(x for x in (r.get("工作经历"), cond["experience"]) if x)
                certs = "；".join(x for x in (r.get("职业资格"), cond["certs"]) if x)
                got.append(make_job(
                    id=r["序号"], batch=bkey, unit=unit, city=_city(city_of.get(re.sub(r"\s+", "", unit), "")),
                    dept=r.get("岗位名称"), duty=r.get("岗位描述"),
                    grade=" ".join(x for x in (r.get("岗位类别"), r.get("岗位等级")) if x),
                    headcount=r.get("计划招聘人数"), fresh=re.sub(r"\s+", "", r.get("对象类别") or ""),
                    education=r.get("学历"), degree=r.get("学位"),
                    major_graduate=r.get("专业/学科方向") if "研究生" in (r.get("学历") or "") else "",
                    major_bachelor=r.get("专业/学科方向") if "研究生" not in (r.get("学历") or "") else "",
                    age=r.get("年龄") or cond["age"], age_relaxed=cond["age_relaxed"], experience=exp,
                    certs=certs, title_req="；".join(x for x in (r.get("专业技术职务任职资格"), cond["title"]) if x), politics=cond["politics"], hukou=cond["hukou"],
                    special=cond["special"], other=cond["other"], exam="笔试+面试" if (r.get("开考比例") or r.get("经笔试入围比例")) else "面试或直接业务考核",
                    extra={"主管单位": r.get("主管单位（部门）"), "其他条件原文": r.get("其他条件"), "其他说明": r.get("其他说明"), "工作要求（不影响报考）": cond["soft"],
                           "咨询电话": r.get("招聘单位咨询电话")}))
        if len(got) < batch["min_jobs"]:
            raise FetchError(f"浙江 {bkey} 只解析出 {len(got)} 个岗位，少于预期的 {batch['min_jobs']}，岗位表可能变了")
        print(f"  {bkey}: {len(got)} 个岗位", flush=True)
        jobs += got
    return jobs
