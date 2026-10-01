"""<地区名>事业单位公开招聘（<官网地址>）。

新增一个地区：
  1. 复制整个 _template 目录，目录名改成地区的拼音 key（如 shanghai），它同时是 data/<key>/ 的目录名；
  2. 改下面的 META，实现 fetch()；
  3. 运行  python3 scripts/update.py --only <key>  ——它会抓取、校验并写出 data/<key>/<批次>.csv，
     然后  python3 scripts/update.py --build-only  合并进看板。看板和文档都会自动带上这个地区，不用改别处。

写 fetch() 前先找到官方公告和岗位表：多数地方是公告页 + xlsx 附件（直接用 lib.xlsx.read_sheets 读），
少数地方是网页里的岗位列表（用 requests 抓，抓不全就抛异常）。
注意：只抓官方网站的公开信息，岗位的要求原文照抄，不要自己改写——解析成学历、专业代码、年龄这些是 lib/match.py 的事。
以 _ 开头的目录不会被当成地区。
"""
from lib.http import FetchError, download, get_text   # download: 带重试的文件下载；get_text: 带重试的网页文本
from lib.schema import make_job                       # 统一的岗位格式
from lib.xlsx import read_sheets                      # 读岗位表 Excel，自动找表头

META = dict(
    name="地区名",                           # 看板上显示的名字
    order=100,                              # 显示顺序，数字小的在前（可省略）
    list_url="https://example.com/",        # 该地区官方的事业单位招聘栏目页
    note="",                                # 这个地区数据的特殊说明，会显示在看板上（可省略）
    batches={                               # 批次 = 一次公告 + 一份岗位表。每个批次的 key 要稳定（如 "2027-jizhong"）
        "example": dict(
            name="2027年集中公开招聘",
            published="2027-01-01",         # 公告发布日期
            signup_start="2027-02-01",      # 报名起止日期；滚动招聘、没有统一报名时间就不写这两项
            signup_end="2027-02-07",
            exam="笔试 2027年3月",           # 考试安排的一句话说明（可省略）
            exam_info=dict(                 # 考试与成绩摘要（可省略，但强烈建议写）：逐条对照公告原文，写不清楚就写「公告未写明」，不要靠印象补
                written="笔试科目、题型、时长",
                written_date="2027年3月14日 15:00—16:30",
                syllabus=[["科目或模块名称", "考什么（依据考试大纲原文；公告和大纲都没写就不要写这一项）"]],   # 可省略
                shortlist="笔试成绩如何划线、按什么比例入围面试",
                interview="面试由谁组织、什么形式、合格线",
                score="总成绩 = 笔试成绩 × 50% + 面试成绩 × 50%",
                after="体检、考察、公示、聘用（可省略）",
                notes=["其他需要留意的事项，如笔试确认环节、服务期（可省略）"],
                sources=[["招聘公告", "https://example.com/notice"]],   # 摘要依据的官方页面，必须 https://
                checked="2027-01-01",       # 核对日期
            ),
            notice_url="https://example.com/notice",   # 公告页，必须 https://；岗位没有单独链接时看板指向这里
            table_url="https://example.com/table.xlsx",
            min_jobs=100,                   # 岗位数下限，少于它就当作抓取 / 解析不全（可省略）
            fresh_note="",                  # 公告里对「应届」的定义（原文摘要）。这对往届生最重要，一定要读公告写清楚
        ),
    },
)


def fetch():
    """抓取全部批次的岗位，返回 make_job(...) 的列表。抓不到 / 格式变了就抛异常（不要返回半截数据）。"""
    raise NotImplementedError("照 regions/guangdong/fetch.py 写")
    # 示例：
    # path = download(META["batches"]["example"]["table_url"], "<key>/example.xlsx")
    # for sheet, rows in read_sheets(path, require=("岗位代码", "招聘单位")):
    #     for r in rows:
    #         jobs.append(make_job(id=r["岗位代码"], batch="example", unit=r["招聘单位"], education=r["学历要求"], ...))
