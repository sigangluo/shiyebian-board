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
            exam_info=dict(
                written="《职业能力倾向测验》（90 分钟）和《综合应用能力》（120 分钟），连续进行、两科均须参加；采用国家人社部人事考试中心统一命制的事业单位分类考试公共科目联考试题，所有考生使用综合管理类（A 类）试卷，范围见《事业单位公开招聘分类考试公共科目笔试考试大纲（2026 年版）》",
                written_date="2026年3月28日 8:30—12:00",
                syllabus=[                  # 笔试内容摘要，依据考试大纲原文；每项 [标题, 内容]
                    ["《职业能力倾向测验》（客观题）", "含常识判断、言语理解与表达、数量关系、判断推理、资料分析五部分"],
                    ["常识判断", "测查从事综合管理工作应知应会的基本知识和运用这些知识分析判断的能力，涉及党的创新理论、党和国家方针政策、经济、历史、文化、法律、管理、科技等"],
                    ["言语理解与表达", "理解语句之间的逻辑关系、辨析词义、根据语境排序和选择恰当的词句；常见题型有词语填空、句子填空、语句排序、主旨概括、标题拟定"],
                    ["数量关系", "理解、把握事物间量化关系和解决数量关系问题的能力，涉及数据关系的分析、运算和推断"],
                    ["判断推理", "对图形、语词概念、事物关系和文字材料的理解、比较、组合、演绎和归纳；常见题型有图形推理、定义判断、类比推理、逻辑判断、综合判断推理"],
                    ["资料分析", "对统计性图表、文字材料等复合性数据资料的综合理解与分析加工"],
                    ["《综合应用能力》（以主观题为主）", "由背景材料和任务组成，任务涉及管理岗位的典型工作，如观点归纳、资料分类、草拟信函、应急处理、联络通知；测查管理角色意识、分析判断能力、计划与控制能力、沟通协调能力和文字表达能力"],
                ],
                shortlist="笔试成绩和面试分数线于 2026 年 5 月 9 日公布；通过面试分数线者，由招聘单位资格审核，审核通过后进入面试；审核未通过的，可按笔试成绩依次递补",
                interview="面试一般于成绩公布一周后陆续开始，时间地点由用人单位另行通知；面试时须提供本人有效居民身份证、学生证（工作证）原件、准考证、报名信息表及招聘单位要求的其他材料",
                score="公告未写明总成绩的计算方式，以招聘单位的通知为准",
                after="体检、考察参照公务员录用标准和要求执行；拟聘用人员公示 5 个工作日",
                notes=[
                    "报名分「报名信息提交」和「笔试确认」两个阶段，未在规定时间（本批次为 2 月 25 日 10:00 至 27 日 12:00）完成笔试确认的，视作放弃笔试",
                    "原则上只接受对缺考、零分和违纪违规三种情形有异议的成绩复核申请，须在成绩公布后 7 个工作日内提出",
                ],
                sources=[["招聘公告", NOTICE], ["公共科目笔试考试大纲（2026 年版，人社部人事考试中心，政府网站转载）", "https://www.shaanxi.gov.cn/xw/ztzl/zxzt/zkzl/2026/szyf/202606/P020260603605181886003.pdf"]],
                checked="2026-10-02",
            ),
            notice_url=NOTICE,
            table_url=HOST + "/cmsres/dc/dc7be59af9c54cbbb30643a8788bde6a/5c318df0949a93dd14aef1da75dd4778.xlsx",
            min_jobs=1500,
            fresh_rule=dict(kind="no_staff_job", cohort=2026, window=2),
            fresh_src="招聘公告、公告附件4《上海市2026年事业单位公开招聘考试问答》",
            fresh_note=("毕业证书落款年度 2 年内（含毕业当年度）即 2025 年、2026 年普通高校毕业生未落实编制内工作的，可以应届毕业生身份报考，如果具备岗位规定的工作年限，也可以非应届毕业生身份报考要求具有工作经历的岗位，只能选其一。"
                        "留学回国人员参照以上说明执行。"
                        "「三支一扶」招募岗位除外。"
                        "已进入编制内工作的，后又离开编制内工作的，视为已落实编制内工作。"
                        "参加大学生村官、「三支一扶」计划期满且考核合格的当年及次年，可以应届毕业生的身份报考。"
                        "自学考试、成人教育、网络教育、夜大、电大等毕业生的考生身份均为非应届毕业人员。"
                        "外省市户籍非应届毕业人员，须持有上海市居住证（在有效期内）一年以上，计算截止时间为 2026 年 12 月 31 日。"),
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
