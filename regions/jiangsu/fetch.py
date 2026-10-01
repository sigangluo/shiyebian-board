"""江苏省省属事业单位统一公开招聘（江苏省人力资源和社会保障厅 jshrss.jiangsu.gov.cn）。

只含**省属**单位（含部属驻苏单位），各市（南京、苏州、无锡……）的市属、县属事业单位另有各自的公告，暂未接入。
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
    note="只含江苏省省属事业单位（以及部属驻苏单位），各市、县的事业单位招聘另有公告，暂未接入。公告和岗位表来自江苏省税务局网站转载的官方公告。",
    batches={
        "2026-shengshu": dict(
            name="省属事业单位2026年统一公开招聘",
            published="2026-03-18",
            signup_start="2026-03-21",
            signup_end="2026-03-25",
            exam="笔试 2026年4月18日",
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
