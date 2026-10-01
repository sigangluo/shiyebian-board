"""上海市事业单位公开招聘（https://rsj.sh.gov.cn/ 上海市人力资源和社会保障局 → 公示公告）。

上海每年春季集中招聘一次（公告 1 月底、2 月初报名、3 月底统一笔试），公告附一个 xlsx「招聘简章」，一个 sheet 里是全市所有岗位。
除了这次集中招聘，上海的市属、区属单位全年还会各自发布单位自主招聘的公告，那些不在这里，暂未接入。

和广东 / 深圳的表不同：
  - 专业要求只有文字，没有专业代码（如「计算机、通信工程等相关专业」），靠 profile.json 里的 keywords / related 匹配；
  - 有专门的「招聘对象」（应届毕业生 / 非应届毕业生 / 不限）、「最低工作年限」和「户籍要求」列；
  - 对外省户籍的非应届人员有居住证要求（公告里写的通用规则，不在岗位行里，所以这里按岗位补到 hukou 字段上）。
"""
import re

from lib.conditions import split_conditions
from lib.http import FetchError, download
from lib.normalize import education_text, major_columns
from lib.schema import make_job
from lib.xlsx import read_sheets

HOST = "https://rsj.sh.gov.cn"
NOTICE = HOST + "/tgsgg_17341/20260128/t0035_1438398.html"

META = dict(
    name="上海",
    order=40,
    list_url="https://rsj.sh.gov.cn/tgsgg_17341/",
    note="只含「上海市事业单位集中公开招聘」这一次统一招聘；各单位全年自主发布的招聘公告暂未接入。外省市户籍的非应届人员需持上海居住证满一年。",
    batches={
        "2026-jizhong": dict(
            name="2026年事业单位集中公开招聘",
            published="2026-01-28",
            signup_start="2026-02-02",
            signup_end="2026-02-06",
            exam="笔试 2026年3月28日（统一笔试，综合管理类 A 类）",
            notice_url=NOTICE,
            table_url=HOST + "/cmsres/dc/dc7be59af9c54cbbb30643a8788bde6a/5c318df0949a93dd14aef1da75dd4778.xlsx",
            min_jobs=1500,
            fresh_rule=dict(kind="no_staff_job", cohort=2026, window=2),
            fresh_note=("考试问答：毕业证书落款年度 2 年内（含毕业当年度，即 2025、2026 年）的普通高校毕业生，**未落实编制内工作**的，"
                        "可以应届毕业生身份报考；私企等非编制工作不影响。具有工作经历的应届毕业生，可以应届身份报考，"
                        "如果具备岗位规定的工作年限，也可以非应届身份报考要求工作经历的岗位，二者只能选其一。"
                        "外省市户籍的非应届毕业人员，须持有上海市居住证（有效期内）一年以上，计算截止 2026 年 12 月 31 日。"
                        "招聘对象为「限本市」户籍的岗位，外省户籍不能报。"),
        ),
    },
)

RESIDENCE_RULE = "外省市户籍非应届毕业人员须持有上海市居住证一年以上"


def either_major(text):
    """其它条件里写了「本科专业、研究生专业符合其一即可」之类：专业对口按本科、研究生取更优的。"""
    return "本科或研究生符合其一" if re.search(r"(?:本科|研究生).{0,8}(?:本科|研究生).{0,12}(?:符合其一|符合专业要求即可|符合即可)", text or "") else ""


def fetch():
    """下载每个批次的招聘简章并解析。下载不全 / 格式变了就抛异常（不要返回半截数据）。"""
    jobs = []
    for bkey, batch in META["batches"].items():
        path = download(batch["table_url"], f"shanghai/{bkey}.xlsx", what=f"上海 {bkey} 招聘简章")
        got = []
        for _, rows in read_sheets(path, require=("岗位编号", "用人单位", "学历要求")):
            for r in rows:
                target = r.get("招聘对象") or ""
                long_target = len(target) > 20          # 个别岗位这一格写成一大段，里面是「上海生源」之类的限定
                fresh_only = target.strip() == "应届毕业生"
                hukou = r.get("户籍要求") or ""
                if "限本市" in hukou:
                    hukou = "限上海户籍"                  # match.py 认「限……户籍」
                elif hukou == "不限":
                    hukou = ""
                if long_target:
                    hukou = "限上海生源（见招聘对象原文）"
                if not hukou and not fresh_only:           # 非应届的岗位：通用的居住证规则
                    hukou = RESIDENCE_RULE
                years = r.get("最低工作年限") or ""
                edu = r.get("学历要求") or ""
                cond = split_conditions(r.get("其它条件"))
                major = r.get("专业要求") or ""
                politics = r.get("政治面貌") or ""
                got.append(make_job(
                    id=r["岗位编号"], batch=bkey, unit=r.get("用人单位"), city="上海",
                    dept=r.get("岗位名称"), duty=r.get("岗位职责"), grade=r.get("岗位类别"),
                    headcount=r.get("招聘人数"),
                    fresh="应届毕业生（限定见原文）" if long_target else target,
                    education=education_text(edu, r.get("学位要求")),
                    degree="" if r.get("学位要求") == "不限" else r.get("学位要求"),
                    **major_columns(major, edu),
                    age=f"{r['年龄上限']}周岁以下" if r.get("年龄上限") else "",
                    experience=cond["experience"] or ("" if years in ("", "不限") else f"{years}以上工作经历"),
                    certs=cond["certs"], title_req=cond["title"],
                    politics="" if politics in ("", "不限") else politics,
                    special=cond["special"], hukou=hukou, other=cond["other"], exam="笔试+面试",
                    extra={"专业口径": either_major(r.get("其它条件")), "主管单位": r.get("主管单位"), "面试比例": r.get("面试比例"), "最低合格分数线": r.get("最低合格分数线"),
                           "笔试面试成绩比例": r.get("笔试面试成绩比例"), "备注": r.get("备注"),
                           "其它条件原文": r.get("其它条件"), "招聘对象原文": target if long_target else "",
                           "工作要求（不影响报考）": cond["soft"]}))
        if len(got) < batch["min_jobs"]:
            raise FetchError(f"上海 {bkey} 只解析出 {len(got)} 个岗位，少于预期的 {batch['min_jobs']}，岗位表可能变了")
        print(f"  {bkey}: {len(got)} 个岗位", flush=True)
        jobs += got
    return jobs
