"""把岗位表里「其它条件」这类自由文本拆成年龄、政治面貌、工作经历、证书、户籍和剩余的其他条件。

有的地区（深圳、北京、上海……）不像广东那样每项条件一列，而是写成一段话：
「40岁以下；中共党员（含预备党员）；具有2年以上相关工作经历。」。
match.py 需要的是分开的字段，否则每个有这段话的岗位都会因为「有其他条件」被标成待确认。

拆法：去掉编号（1. / 一、），按 ； ; 。 换行 切成小句，每个小句归入一类；
一句话里混了几类的，再按逗号切一次，切完每段都只有一类才拆；认不出来的原样留在 other 里——
宁可让用户多看一眼，也不要拆错。
"""
import re

_SPLIT = re.compile(r"[；;。\n]+")
_COMMA = re.compile(r"[，,]")
_ENUM = re.compile(r"^[\s（(]*(?:[一二三四五六七八九十]+|\d+)\s*[、.．)）]\s*")     # 1. / 一、 / （2）
_AGE = re.compile(r"\d+\s*(?:周)?岁")
_EXP = re.compile(r"工作经历|工作经验|从业经历|从业经验|年以上.{0,12}工作|工作.{0,8}满?\d+年|从事.{0,20}工作.{0,6}\d+年")
_POL = re.compile(r"党员|团员")
_HUKOU = re.compile(r"户籍|户口|生源|居住证")
_CERT = re.compile(r"资格证?|执业证|证书|职业资格|运动员称号|人员证|英语[四六]级|CET|计算机[一二三四]级")
_DIPLOMA = re.compile(r"学历|学位")      # 「取得学历学位证书的时限为……」说的是毕业证书的时间，不是资格证书
_SOFT = re.compile(r"责任心|沟通|文字功底|吃苦|良好的|较强的|能熟练|身体|身心健康|品行|团队|服务意识|值班|值守|加班|出差|夜班|倒班"
                   r"|热爱|服从|性格|乐观|政治素质|政治立场|拥护|大局意识|政策理论|心理素质|奉献|敬业|廉洁|体检和考察"
                   r"|符合其一|专业符合|以最高学历")        # 最后一行是专业口径的说明，口径由各地 fetch.py 另行识别，不是条件本身
_PREFER = re.compile(r"优先|加分|慎重应聘")                      # 「……者优先」是倾向，不是硬性条件
_DEADLINE = re.compile(r"证书.{0,30}时限|时限.{0,10}\d{4}年")        # 「应届毕业生取得学历学位证书的时限为2026年12月底前」：已经毕业的人不受影响
_SPECIAL = re.compile(r"三支一扶|大学生村官|退役|残疾|服务期满|西部计划|基层服务项目|特岗|军人|军属|烈士")
_TRIVIAL = re.compile(r"^(?:本科及以上需)?(?:取得|具有)相应(?:学历[、，])?(?:学位|学历)$|^(?:无|不限)(?:其他条件)?$")   # 「取得相应学位」「无」：没有信息量
_TITLE = re.compile(r"职称|职务任职资格")
_KINDS = (("special", _SPECIAL), ("title", _TITLE), ("age", _AGE), ("experience", _EXP), ("politics", _POL), ("hukou", _HUKOU), ("certs", _CERT))


def _kinds(clause):
    kinds = [k for k, rx in _KINDS if rx.search(clause)]
    if "certs" in kinds and _DIPLOMA.search(clause):
        kinds.remove("certs")
    if "certs" in kinds and "title" in kinds:      # 「会计初级及以上职称证书」是职称，不是资格证书
        kinds.remove("certs")
    return kinds


def _classify(clause, out):
    """把一小句放进 out；能归类返回 True。"""
    kinds = _kinds(clause)
    if "放宽" in clause and "age" in kinds:     # 「具有正高职称的年龄放宽到50周岁」：说的是年龄放宽，不是要求职称
        kinds = ["age"]
    # 倾向性说明、毕业证书时限、软性要求 / 工作性质（值班、文字功底……）：不影响能不能报，记进 soft
    if (_PREFER.search(clause) or _DEADLINE.search(clause) or _TRIVIAL.match(clause)
            or (not kinds and _SOFT.search(clause))):
        out["soft"].append(clause)
        return True
    if len(kinds) != 1 or len(clause) > 40:
        return False
    kind = kinds[0]
    if kind == "age" and "放宽" in clause:        # 「硕士研究生年龄条件放宽到43岁」等：硕士的单独记，其他（博士、职称）记 age_other
        out["age_relaxed" if "硕士" in clause else "age_other"].append(clause)
    else:
        out[kind].append(re.sub(r"^政治面貌[:：]", "", clause))
    return True


def split_conditions(text):
    """返回 {'age', 'age_relaxed', 'age_other', 'politics', 'experience', 'certs', 'special', 'title', 'hukou', 'soft', 'other'}，
    每项是字符串（多句用「；」连起来），没有就是空串。age_relaxed 是对硕士的年龄放宽；soft 是软性要求 / 工作性质，不影响能不能报。"""
    out = {k: [] for k in ("age", "age_relaxed", "age_other", "politics", "experience", "certs", "special", "title", "hukou", "soft", "other")}
    for raw in _SPLIT.split(text or ""):
        clause = _ENUM.sub("", raw.strip()).strip()
        clause = "，".join(p for p in _COMMA.split(clause) if not _TRIVIAL.match(p.strip()))     # 「取得相应学位，尊重基督教信仰」
        if not clause:
            continue
        if _classify(clause, out):
            continue
        parts = [_ENUM.sub("", p.strip()).strip() for p in _COMMA.split(clause)]
        parts = [p for p in parts if p]
        if len(parts) > 1 and len({k for p in parts for k in _kinds(p)}) > 1 and all(len(_kinds(p)) <= 1 for p in parts):
            for p in parts:                        # 每段都只有一类：分开归类，认不出类别的那段进 other
                if not _classify(p, out):
                    out["other"].append(p)
        else:
            out["other"].append(clause)
    return {k: "；".join(v) for k, v in out.items()}
