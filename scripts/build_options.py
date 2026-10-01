"""生成页面「我的条件」里的选项：site/assets/options.json。

选项来自官方目录，不手抄（专业目录有上千项，手抄必错）:
  本科   普通高等学校本科专业目录（2025年）          教育部      PDF  → 840 个专业，按 学科门类 / 专业类 分组
  研究生 研究生教育学科专业目录（2022年）            国务院学位委员会、教育部  PDF  → 一级学科和专业学位类别
  大专   职业教育专业目录（2021年）高职专科部分      教育部      docx → 697 个专业
  省市   china-division（民政部行政区划，npm 包）    → 省 → 地级市
生成的 JSON 已经提交在仓库里，用户页面直接读它，**平时不需要运行本脚本**；教育部更新目录后再运行:

    python3 scripts/build_options.py            # 下载 → 解析 → 写 site/assets/options.json
    python3 scripts/build_options.py --check    # 只解析、打印数量，不写文件
    python3 scripts/build_options.py --refresh  # 重新下载（默认复用 raw/options/ 里已下载的）

解析 PDF 要用 poppler 的 pdftotext（brew install poppler）；这是开发时才需要的，用户不需要。
专业「关联词」（页面用它给名称对不上的岗位标待确认）是人工维护的 CLUSTERS，改它不需要下载。
"""
import argparse
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.http import RAW_DIR, FetchError, download
from lib.regions import ROOT

OUT = ROOT / "site" / "assets" / "options.json"
CACHE = Path("options")        # 在 raw/ 下，不进 git
SOURCES = {
    "bachelor": ("https://www.csdp.edu.cn/upload/attachment/202504/22/110909/2.%E6%99%AE%E9%80%9A%E9%AB%98%E7%AD%89%E5%AD%A6%E6%A0%A1"
                 "%E6%9C%AC%E7%A7%91%E4%B8%93%E4%B8%9A%E7%9B%AE%E5%BD%95%EF%BC%882025%E5%B9%B4%EF%BC%89.pdf", "ug.pdf", b"%PDF"),
    "graduate": ("http://www.moe.gov.cn/srcsite/A22/moe_833/202209/W020220914572994461110.pdf", "pg.pdf", b"%PDF"),
    "college": ("https://www.gov.cn/zhengce/zhengceku/2021-03/22/5594778/files/39260d2c75ae43c186052520a440495c.docx", "vc.docx", b"PK"),
    "divisions": ("https://unpkg.com/china-division@2.7.0/dist/pc-code.json", "pc-code.json", b"["),
}
LABELS = {"bachelor": "普通高等学校本科专业目录（2025年）", "graduate": "研究生教育学科专业目录（2022年）",
          "college": "职业教育专业目录（2021年）高职专科", "divisions": "china-division 2.7.0（民政部行政区划）"}

# 直辖市没有「市」这一级，只有区
MUNICIPALITIES = {"北京", "天津", "上海", "重庆"}
SKIP_GRAD_CATEGORIES = {"军事学"}       # 军事学门类不对应事业单位招聘

# 专业「关联词」：同一组里的专业互相算相关。岗位只写文字（上海、江苏）又没出现你专业的名称时，出现这些词就标「待确认」而不是「不符」。
# grad / bachelor 里写 4 位代码（研究生是一级学科代码，本科是专业类代码）或学科门类名（整个门类）。
CLUSTERS = [
    {"name": "计算机与信息", "terms": ["计算机", "软件", "信息", "电子", "网络", "数据", "大数据", "通信", "人工智能", "智能", "自动化"],
     "graduate": ["0812", "0835", "0839", "0854", "0810", "0811", "0809", "1405", "1401", "0711", "1205"], "bachelor": ["0809", "0807", "0808"]},
    {"name": "数学与统计", "terms": ["数学", "统计", "数据", "精算"],
     "graduate": ["0701", "0714", "0252", "0711"], "bachelor": ["0701", "0712"]},
    {"name": "机械电气", "terms": ["机械", "电气", "自动化", "机电", "控制", "能源", "动力", "仪器"],
     "graduate": ["0802", "0804", "0807", "0808", "0811", "0855", "0858"], "bachelor": ["0802", "0803", "0805", "0806", "0808"]},
    {"name": "土木建筑", "terms": ["土木", "建筑", "水利", "规划", "工程管理", "造价", "测绘"],
     "graduate": ["0813", "0814", "0815", "0816", "0833", "0851", "0853", "0859", "0862", "1256"], "bachelor": ["0810", "0811", "0812", "0828"]},
    {"name": "化工材料环境", "terms": ["化学", "化工", "材料", "环境", "生态", "制药"],
     "graduate": ["0703", "0805", "0817", "0830", "0856", "0857", "0903"], "bachelor": ["0703", "0804", "0813", "0825"]},
    {"name": "经济金融财会", "terms": ["经济", "金融", "财务", "会计", "审计", "统计", "贸易", "财政", "税务", "保险"],
     "graduate": ["0201", "0202", "0251", "0252", "0253", "0254", "0255", "0256", "0258", "1202", "1251", "1253", "1257"],
     "bachelor": ["0201", "0202", "0203", "0204", "1202"]},
    {"name": "管理与公共管理", "terms": ["管理", "公共管理", "行政", "工商管理", "人力资源", "物流"],
     "graduate": ["1201", "1202", "1204", "1251", "1252", "1254", "1255", "1256"], "bachelor": ["1201", "1202", "1204", "1205", "1206", "1207"]},
    {"name": "法学与政治", "terms": ["法学", "法律", "政治", "公安", "行政", "监察"],
     "graduate": ["0301", "0302", "0305", "0306", "0307", "0308", "0351", "0353", "0354", "0355"], "bachelor": ["0301", "0302", "0303", "0305", "0306"]},
    {"name": "中文与新闻", "terms": ["中文", "汉语言", "新闻", "传播", "编辑", "出版", "文秘"],
     "graduate": ["0501", "0503", "0552", "0553"], "bachelor": ["0501", "0503"]},
    {"name": "外语", "terms": ["外语", "英语", "翻译", "语言"], "graduate": ["0502", "0551", "0453"], "bachelor": ["0502"]},
    {"name": "教育心理体育", "terms": ["教育", "心理", "体育", "教学", "学前"],
     "graduate": ["0401", "0402", "0403", "0451", "0452", "0453", "0454"], "bachelor": ["0401", "0402", "0711"]},
    {"name": "医药卫生", "terms": ["医学", "临床", "护理", "药学", "公共卫生", "康复", "医疗"], "graduate": ["医学"], "bachelor": ["医学"]},
    {"name": "农林生物", "terms": ["生物", "农学", "园艺", "林业", "畜牧", "植物", "动物"], "graduate": ["农学", "0710"], "bachelor": ["农学", "0710"]},
    {"name": "艺术设计", "terms": ["艺术", "设计", "美术", "音乐", "舞蹈", "传媒"], "graduate": ["艺术学"], "bachelor": ["艺术学"]},
]

# 学科门类 → 页面里给「对口关键词」的词（岗位写「工学类」「理工类」就算对口）
CATEGORY_WORDS = {"工学": ["工学", "理工", "工科"], "理学": ["理学", "理工", "理科"]}

# 常见资格证书：label 给人看，tokens 是和岗位表证书原文做「包含」比较的词（match.py 里 h in c or c in h）。
# 范围取自现有岗位表里出现最多的证书；不在这里的证书，页面允许直接输入。
CERTS = [
    ("教师资格证", ["教师资格"]), ("医师资格 / 执业医师", ["医师", "医生"]), ("护士执业资格", ["护士"]),
    ("法律职业资格（司法考试）", ["法律职业资格", "司法考试"]), ("会计专业技术资格（初级 / 中级）", ["会计"]), ("注册会计师", ["注册会计师"]),
    ("计算机技术与软件资格（软考）", ["软考", "计算机技术与软件"]), ("普通话水平测试证书", ["普通话"]),
    ("造价工程师", ["造价工程师"]), ("建造师", ["建造师"]), ("注册建筑师", ["注册建筑师"]), ("注册结构工程师", ["注册结构工程师"]),
    ("注册土木工程师", ["注册土木工程师"]), ("注册城乡规划师", ["注册城乡规划师"]), ("新闻记者职业资格", ["记者"]),
    ("社会工作者（社工师）", ["社会工作师", "社工师"]), ("执业药师", ["执业药师"]), ("运动员等级证书", ["运动员"]),
    ("心理咨询师", ["心理咨询"]), ("人力资源管理师", ["人力资源管理师"]), ("执业兽医", ["执业兽医"]),
]


def fetch_source(key, refresh=False):
    """下载到 raw/options/；已经下载过就直接用（--refresh 强制重新下载）。"""
    url, name, magic = SOURCES[key]
    cached = RAW_DIR / CACHE / name
    if cached.exists() and not refresh:
        return cached
    return download(url, CACHE / name, what=LABELS[key], magic=magic)


def pdf_text(path):
    try:
        return subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True, text=True).stdout
    except FileNotFoundError:
        sys.exit("需要 pdftotext（brew install poppler）。它只用来解析 PDF 目录，运行页面不需要。")


def clean_name(s):
    """去掉名称后面的括号说明（可授…学位 / 注：…）和专业学位的星号。括号有时被换行截断，所以直接截到行尾。"""
    return re.sub(r"[（(].*$", "", s).replace("*", "").strip()


def parse_bachelor(text):
    out, cat, cls = [], None, None
    for line in text.splitlines():
        s = line.strip()
        if m := re.match(r"^(\d\d)\s+学科门类[：:]\s*(\S+)", s):
            cat = m[2]
        elif m := re.match(r"^(\d{4})\s+(\S+类)$", s):
            cls = m[2]
        elif (m := re.match(r"^(\d{6})([KT]*)\s+(\S+)", s)) and cat and cls:
            out.append([m[1], clean_name(m[3]), cat, cls])
    return out


def parse_graduate(text):
    out, cat = [], None
    for line in text.splitlines():
        s = line.strip()
        if m := re.match(r"^(\d\d)\s+([一-龥]+)$", s):
            cat = m[2]
        elif (m := re.match(r"^(\d{4})\s+(.+)$", s)) and cat and cat not in SKIP_GRAD_CATEGORIES:
            out.append([m[1], clean_name(m[2]), cat, 1 if m[1][2] >= "5" else 0])     # 第三位从 5 开始的是专业学位类别
    return out


def parse_college(path):
    """docx 里是三个层次的表：中职（大类 61–79）、高职专科（41–59）、高职本科（21–39），要的是高职专科。"""
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    out, cat, cls = [], None, None
    for row in re.findall(r"<w:tr[ >].*?</w:tr>", xml, flags=re.S):
        cells = ["".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", c)) for c in re.findall(r"<w:tc>.*?</w:tc>", row, flags=re.S)]
        if len(cells) == 1:
            if m := re.match(r"^(\d{2})(\S+大类)$", cells[0]):
                cat, cls = m[2], None
            elif m := re.match(r"^(\d{4})(\S+类)$", cells[0]):
                cls = m[2]
        elif len(cells) == 3 and re.fullmatch(r"[45]\d{5}", cells[1]) and cat and cls:
            out.append([cells[1], cells[2].strip(), cat, cls])
    return out


def parse_divisions(path):
    """省 → 地级市。名称去掉「省 / 市 / 自治区」后缀：户籍匹配是看岗位原文里有没有这个词，「广东省」「揭阳市」都包含「广东」「揭阳」。"""
    out = []
    for p in json.loads(Path(path).read_text(encoding="utf-8")):
        prov = re.sub(r"(壮族|回族|维吾尔)?自治区$|特别行政区$|省$|市$", "", p["name"])
        cities = [] if prov in MUNICIPALITIES else [c["name"][:-1] if c["name"].endswith("市") else c["name"]
                                                    for c in p.get("children", []) if "直辖县级" not in c["name"]]
        out.append([prov, cities])
    return out


def check(data):
    """数量不对多半是目录格式变了、解析漏了，宁可报错也不要写出残缺的选项。"""
    floor = {"bachelor": 800, "graduate": 150, "college": 650, "divisions": 30}
    for k, n in floor.items():
        if len(data[k]) < n:
            sys.exit(f"{LABELS[k]} 只解析出 {len(data[k])} 项（至少应有 {n}），目录格式可能变了，请检查解析规则。")
    codes = [x[0] for x in data["bachelor"]]
    if len(set(codes)) != len(codes):
        sys.exit("本科专业代码有重复，解析有误。")
    for must in (("bachelor", "080902", "软件工程"), ("graduate", "0812", "计算机科学与技术"), ("graduate", "0854", "电子信息")):
        if not any(x[0] == must[1] and x[1] == must[2] for x in data[must[0]]):
            sys.exit(f"{must} 没有解析到，目录格式可能变了。")
    cluster_codes = {c for cl in CLUSTERS for lvl in ("graduate", "bachelor") for c in cl[lvl]}
    known = {x[0][:4] for x in data["bachelor"]} | {x[0] for x in data["graduate"]} | {x[2] for k in ("bachelor", "graduate") for x in data[k]}
    unknown = sorted(c for c in cluster_codes if c not in known)
    if unknown:
        sys.exit(f"CLUSTERS 里有目录中不存在的代码或门类：{unknown}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只解析并打印数量，不写文件")
    ap.add_argument("--refresh", action="store_true", help="重新下载目录（默认用 raw/options/ 里已下载的）")
    args = ap.parse_args()
    try:
        data = {
            "bachelor": parse_bachelor(pdf_text(fetch_source("bachelor", args.refresh))),
            "graduate": parse_graduate(pdf_text(fetch_source("graduate", args.refresh))),
            "college": parse_college(fetch_source("college", args.refresh)),
            "divisions": parse_divisions(fetch_source("divisions", args.refresh)),
        }
    except FetchError as e:
        sys.exit(str(e))
    check(data)
    print("、".join(f"{LABELS[k]} {len(v)}" for k, v in data.items()))
    if args.check:
        return
    out = {"sources": LABELS, "categoryWords": CATEGORY_WORDS, "clusters": CLUSTERS,
           "majors": {"graduate": data["graduate"], "bachelor": data["bachelor"], "college": data["college"]},
           "places": data["divisions"], "certs": [{"label": l, "tokens": t} for l, t in CERTS]}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"已写入 {OUT.relative_to(ROOT)}（{OUT.stat().st_size // 1024} KB）")


if __name__ == "__main__":
    main()
