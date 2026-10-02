"""杭州市市属事业单位统一公开招聘（杭州市人力资源和社会保障局 hrss.hangzhou.gov.cn）。

只含市委组织部、市人社局组织的市属统一招聘这一批。各区、各单位自主招聘，以及高层次和特殊专业技术岗位，不在这里。
岗位表是公告页上的 xls「计划表」，下载链接带加密参数，每次从公告页现抓。
专业只有一栏（文字，参照教育部目录和浙江省公务员专业目录）；限应届的岗位写在「其他要求」里，
不是单独一列。性别是单独一列，取值「男」「女」「不限制」。
"""
import re
import urllib.parse

from lib.conditions import split_conditions
from lib.http import FetchError, download, get_text
from lib.normalize import major_columns
from lib.schema import make_job
from lib.xlsx import read_sheets

HOST = "https://hrss.hangzhou.gov.cn"
NOTICE = HOST + "/col/col1229782007/art/2026/art_984b55b5c8422a20265023286ebcb561.html"
# 「招聘 / 面向普通高校 2026 年应届毕业生」才是限应届。
# 「应届毕业生不做该项要求」「应届毕业生需取得执业医师证」说的是证书或经历的例外，不是考生类别。
_FRESH_ONLY = re.compile(r"招聘普通高校\d{4}年应届毕业生|面向普通高校\d{4}年应届毕业生招聘")

META = dict(
    name="杭州",
    order=32,
    list_url=HOST + "/col/col1229782007/index.html",
    note="只含杭州市市属事业单位统一公开招聘。各区、各单位自主招聘，以及高层次和特殊专业技术岗位招聘，暂未接入。",
    batches={
        "2026-shishu": dict(
            name="市属事业单位2026年统一公开招聘",
            published="2026-03-17",
            signup_start="2026-03-19",
            signup_end="2026-03-25",
            exam="笔试 2026年4月25日",
            exam_info=dict(
                written="《综合应用能力》（主观题）和《职业能力倾向测验》（客观题），两个科目满分均为 100 分；不指定辅导用书",
                written_date="2026年4月25日：综合应用能力 9:00—11:30，职业能力倾向测验 下午 2:00—3:30",
                shortlist="按《招聘计划表》「经笔试入围比例」从高分到低分确定面试对象，不足比例的按实际参考人员确定；缺考一门及以上或笔试违纪的不得入围。笔试成绩和入围名单可于 5 月底在网报平台查询",
                interview="由主管部门及招聘单位组织，形式可包括专业知识测试、试讲、实际操作、结构化面试；面试满分 100 分，合格分 60 分，不合格者不列入考察、体检对象",
                score="考试总成绩 = 笔试成绩 ÷ 4 + 面试成绩 ÷ 2。总成绩相同的，笔试成绩高的在前；仍相同的加试结构化面试",
                after="在面试合格人员中按总成绩 1:1 确定考察、体检对象；拟聘用人员在市人社局和招聘单位或主管部门网站公示 7 个工作日",
                notes=[
                    "每人限报一个岗位。有效报考人数不足招聘计划 3 倍的岗位，不开考或酌情核减",
                    "普通高校应届毕业生须在 2026 年 9 月 30 日前取得学历（学位）证书",
                ],
                sources=[["招聘公告", NOTICE]],
                checked="2026-10-02",
            ),
            notice_url=NOTICE,
            min_jobs=200,
            fresh_rule=dict(kind="year_window", cohort=2026, window=2),
            fresh_src="招聘公告",
            fresh_note=("部分岗位招聘 2026 年普通高校应届毕业生，包含 ① 2024 年、2025 年和 2026 年普通高校毕业生"
                        "（含同期毕业的留学回国人员，以及符合教研厅函〔2019〕1 号文规定的非全日制研究生）；"
                        "② 按国家政策规定可以享受应届毕业生就业待遇的其他情形人员。"
                        "2026 年普通高校毕业生取得相应证书的时限为 2026 年 9 月 30 日前。"),
        ),
    },
)


def _table_url(notice_url):
    """从公告页里找出计划表 xls 的下载链接（加密参数会变，不写死）。"""
    page = get_text(notice_url, what="杭州 公告页")
    for href in re.findall(r'href="(/api-gateway[^"]+)"', page):
        href = href.replace("&amp;", "&")
        m = re.search(r"fileName=([^&]+)", href)
        if m and urllib.parse.unquote(m.group(1)).lower().endswith(".xls"):
            return HOST + href
    raise FetchError("杭州 公告页里找不到 .xls 计划表的链接，页面结构可能变了")


def _fresh(text):
    m = _FRESH_ONLY.search(text or "")
    return m.group(0) if m else ""


def fetch():
    """下载每个批次的计划表并解析。下载不全 / 格式变了就抛异常（不要返回半截数据）。"""
    jobs = []
    for bkey, batch in META["batches"].items():
        path = download(_table_url(batch["notice_url"]), f"hangzhou/{bkey}.xls", what=f"杭州 {bkey} 计划表")
        got = []
        for _, rows in read_sheets(path, require=("招聘单位", "招聘岗位", "学历"), header_rows=1, scan=8, skip_sheets=("xlhide",)):
            for r in rows:
                edu = r.get("学历") or ""
                other = r.get("其他要求") or ""
                cond = split_conditions(other)
                gender = r.get("性别要求") or ""
                extra = {"主管单位": r.get("主管单位（部门）"), "其他要求原文": other, "其他说明": cond["soft"],
                         "咨询电话": r.get("招聘单位咨询电话"), "入围面试比例": r.get("经笔试入围比例"),
                         "专业测试": r.get("是否设置专业（业务、技能、心理素质）测试")}
                if gender in ("男", "女"):
                    extra["性别要求"] = gender
                got.append(make_job(
                    id=r["序号"], batch=bkey, unit=r.get("招聘单位"), city="杭州",
                    dept=r.get("招聘岗位"), grade=" ".join(x for x in (r.get("岗位类别"), r.get("岗位等级")) if x),
                    headcount=r.get("招聘人数"), fresh=_fresh(other), education=edu, degree=r.get("学位"),
                    **major_columns(r.get("专业要求"), edu),
                    age=r.get("年龄要求") or cond["age"], age_relaxed=cond["age_relaxed"],
                    experience=cond["experience"], certs=cond["certs"], title_req=cond["title"],
                    politics=cond["politics"], hukou=cond["hukou"], special=cond["special"], other=cond["other"],
                    exam="笔试+面试", extra=extra))
        if len(got) < batch["min_jobs"]:
            raise FetchError(f"杭州 {bkey} 只解析出 {len(got)} 个岗位，少于预期的 {batch['min_jobs']}，岗位表可能变了")
        print(f"  {bkey}: {len(got)} 个岗位", flush=True)
        jobs += got
    return jobs
