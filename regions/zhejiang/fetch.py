"""浙江省省属事业单位集中公开招聘（https://rlsbt.zj.gov.cn/ 浙江省人力资源和社会保障厅）。

浙江省属事业单位每年集中招聘两次（上半年、下半年），公告附一个 xlsx「招聘计划表」，里面有「单位信息表」和「岗位信息表」两个 sheet。
注意：这里只有**省属**单位，各市（杭州、宁波、温州……）的市属、县属事业单位另有各自的公告，还没有接入。
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
    note="只含浙江省省属事业单位（以及部属驻浙单位），各市、县的事业单位招聘另有公告，暂未接入。每年上半年、下半年各一批。",
    batches={
        "2026-h2": dict(
            name="省属事业单位2026年下半年集中公开招聘",
            published="2026-08-11",
            signup_start="2026-08-13",
            signup_end="2026-08-19",
            exam="笔试 2026年9月19日（杭州）",
            notice_url=NOTICE,
            min_jobs=80,
            fresh_rule=dict(kind="year", cohort=2026),
            fresh_note=("公告：招聘对象类别分 ① 应届毕业生——主要指按学制于 2026 年内完成学业并取得学历、学位证书的普通高校毕业生"
                        "（部分岗位对取得证书的时间另有规定，见计划表「其他条件」栏），有关政策规定视同应届毕业生的群体也可应聘；"
                        "② 机关事业单位正式在编人员；③ 不限。判断标准是**毕业年份**，没有提缴纳社保或「未落实工作单位」。"
                        "也就是说，按这个定义 2026 年毕业的人在这一批算应届，但下一批（2027 年上半年）会换成 2027 年毕业，"
                        "以当时的公告为准。"),
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
                    headcount=r.get("计划招聘人数"), fresh=r.get("对象类别"),
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
