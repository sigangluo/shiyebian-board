"""把一个岗位和你的个人条件（profile.json）对照，判断能不能报。

结果分三档：
  ok     符合：每一项都能确认满足
  check  待确认：至少有一项不能确定（写法特殊、你没填、各地认定不同），需要看公告或打电话问
  no     不符：至少有一项明确不满足（学历不够、专业不对、要求的经历你没有……）

宁可多放进「待确认」，也不要把可能能报的岗位判成「不符」——不符的岗位默认不出现在看板里。
所有判断规则都在这个文件里，改了之后先跑测试: python3 -m unittest discover -s tests
"""
import json
import re

from .regions import ROOT

PROFILE_PATH = ROOT / "profile.json"
EDU_LEVEL = {"大专": 1, "本科": 2, "硕士": 3, "博士": 4}
LEVEL_COLUMN = {1: "major_college", 2: "major_bachelor", 3: "major_graduate", 4: "major_graduate"}
LEVEL_NAME = {1: "大专", 2: "本科", 3: "硕士研究生", 4: "博士研究生"}
FRESH_VALUES = ("auto", "yes", "no", "maybe")      # auto：按各批次公告的应届规则推断；maybe：一律待定

# 校验不通过的原因，按这个顺序取第一个作为「主要原因」，用来统计被过滤掉的岗位
REASON_ORDER = ("education", "major", "fresh", "hukou", "experience", "age", "gender", "special", "certs", "title", "politics")
REASON_LABEL = {"education": "学历不符", "major": "专业不符", "fresh": "应届 / 往届身份不符", "hukou": "户籍不符",
                "experience": "要求工作经历", "age": "年龄超限", "gender": "性别不符", "special": "专项招聘 / 编外", "certs": "要求资格证书",
                "title": "要求职称", "politics": "政治面貌不符"}


def load_profile(path=PROFILE_PATH):
    """读 profile.json。文件不存在返回 None（这时不做任何筛选）。字段写错直接报错，别带着错误的条件去筛。"""
    if not path.exists():
        return None
    p = json.loads(path.read_text(encoding="utf-8"))
    if p.get("education") not in EDU_LEVEL:
        raise ValueError(f"profile.json 的 education 必须是 {list(EDU_LEVEL)} 之一，现在是 {p.get('education')!r}")
    if p.get("fresh", "auto") not in FRESH_VALUES:
        raise ValueError(f"profile.json 的 fresh 必须是 {list(FRESH_VALUES)} 之一")
    for k in ("age", "work_months"):
        if p.get(k) is not None and not isinstance(p[k], (int, float)):
            raise ValueError(f"profile.json 的 {k} 必须是数字或 null")
    return p


_FEMALE = re.compile(r"限女|仅限女|只限女|女性岗位|入住女生宿舍|女生宿舍|限招女|限女性|女性报考")
_MALE = re.compile(r"限男|仅限男|只限男|男性岗位|入住男生宿舍|男生宿舍|限招男|限男性|适合男性")


def gender_restriction(job):
    """岗位文字里明确限定性别 -> '女' / '男' / ''。男女两种写法都出现（如「男女分设」）算没有限定。

    岗位表有单独的「性别要求」列、且取值就是男 / 女（杭州写成「男」「女」，「不限制」不算）时，直接用这一列。
    否则看岗位职责、其他条件、部门和岗位表里其他信息（如「其它条件原文」）。
    """
    raw = ((job.get("extra") or {}).get("性别要求") or "").strip()
    if raw in ("男", "男性", "限男", "限男性"):
        return "男"
    if raw in ("女", "女性", "限女", "限女性"):
        return "女"
    text = " ".join([job["duty"], job["other"], job["dept"]] + list(job["extra"].values()))
    f, m = bool(_FEMALE.search(text)), bool(_MALE.search(text))
    return "女" if f and not m else "男" if m and not f else ""


def category_flags(cat):
    """考生类别文字 -> (限在编人员, 限往届 / 社会人员, 限应届)。注意「非应届」里也有「应届」二字；江苏写成「2026年毕业生」。"""
    zaibian = "在编" in cat       # 如「机关事业单位正式在编人员」
    past_only = bool(re.search(r"往届|社会人员|非应届", cat))
    fresh_only = not past_only and bool(re.search(r"应届|\d{4}年毕业生", cat))
    return zaibian, past_only, fresh_only


def hukou_flags(text):
    """户籍要求文字 -> (明确限定, 只针对非应届)。

    明确限定：写了「限……户籍」「须具有……户籍 / 居住证」之类，且不是「不限」「……优先」。
    只针对非应届：如上海「外省市户籍非应届毕业人员须持有上海市居住证一年以上」。
    """
    explicit = bool(re.search(r"^限|限.{0,6}(户籍|户口)|须.{0,8}(户籍|户口|居住证)|具有.{0,8}(户籍|户口)", text)
                    and "不限" not in text and "优先" not in text)
    return explicit, "非应届" in text


def doctor_relaxed_text(job):
    """岗位表里博士的年龄放宽条件（存在 extra 里，列名含「博士」和「年龄」）。"""
    return next((v for k, v in job["extra"].items() if "博士" in k and "年龄" in k), "")


def either_major_flag(job):
    """岗位写明「本科专业、研究生专业符合其一即可」（由各地 fetch.py 识别后记在 extra 里）。"""
    return job["extra"].get("专业口径") == "本科或研究生符合其一"


# ---------- 各项条件的解析 ----------

def parse_education(text):
    """'本科以上' -> (2, True)；'硕士研究生' -> (3, False)；认不出来 -> None。第二项表示「以上」。"""
    t = text or ""
    for key, lv in (("博士", 4), ("硕士", 3), ("研究生", 3), ("本科", 2), ("大学", 2), ("大专", 1), ("专科", 1)):
        if key in t:
            return lv, bool(re.search(r"以上|及以上", t))
    return None


_CODE_PAREN = re.compile(r"[（(]\s*([A-Z]?\d{2,8})\s*[）)]")    # 括号里的代码：(A0812) / （B080901） / （07）
_CODE_BARE = re.compile(r"[A-Z]\d{2,8}")


def parse_major(text):
    """专业要求 -> {'blank'} / {'unlimited'} / {'codes': [...], 'text': 原文}。

    代码有两种写法：广东、深圳带字母（研究生 A0812、本科 B080901），浙江只有数字（学科门类 08、一级学科 0812）。
    """
    t = (text or "").strip()
    if not t:
        return {"blank": True}
    codes = _CODE_PAREN.findall(t) or _CODE_BARE.findall(t)
    if not codes and "不限" in t:
        return {"unlimited": True}
    return {"codes": codes, "text": t}


def major_fit(req, codes, names, keywords=(), related=()):
    """岗位专业要求 req（parse_major 的结果）和你的专业对照 -> 'match' / 'check' / 'no'。

    专业代码按前缀比较：岗位写学科门类 A08，你的专业是 A0812，算符合；
    岗位写得比你更细（A081201，你是 A0812），你的二级学科方向不确定，算待确认。
    岗位没有写代码（只有名称，如上海的「计算机、通信工程等相关专业」）时按文字判断：
      包含你的专业名称或 keywords（如「计算机」「工学」）算符合；包含 related（如「信息」「电子」）或专业名称前三个字算待确认；
      都没有才算不符。keywords / related 写在 profile.json 的 majors.<层次> 里。
    """
    if req.get("codes"):
        digits = lambda c: re.sub(r"^[A-Z]", "", c)       # 浙江只写数字，别的地区带字母，统一成数字再比
        verdict = "no"
        for r in map(digits, req["codes"]):
            for u in map(digits, codes):
                if u.startswith(r):
                    return "match"
                if r.startswith(u):
                    verdict = "check"
        if verdict == "no":
            text = req["text"]
            # 名称完全相同、代码不同：多半是两套目录的写法（如计算机科学与技术 0812 工学 / 0775 理学），不敢直接判不符
            if any(n and n in text for n in names):
                return "check"
            # 混写：有的专业带代码、有的只写名称。只写名称的那几段，名称前三个字对得上也算待确认
            for seg in re.split(r"[；;、，,\n]+", text):
                if not _CODE_PAREN.search(seg) and not _CODE_BARE.search(seg) and any(
                        x and x in seg for x in [n[:3] for n in names] + list(keywords) + list(related)):
                    return "check"
        return verdict
    text = req.get("text", "")
    if any(n and n in text for n in names) or any(k and k in text for k in keywords):
        return "match"
    if any(r and r in text for r in related) or any(n and n[:3] in text for n in names):
        return "check"
    return "no"


_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def parse_experience_years(text):
    """'2年以上相关工作经历' -> 2.0；无 / 不限 / 空 -> 0.0；写了但认不出年限 -> None。"""
    t = (text or "").strip()
    if not t or re.fullmatch(r"(无|不限|无要求|不要求|无工作经历要求)[。；;]?", t):
        return 0.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*年", t)
    if m:
        return float(m.group(1))
    m = re.search(r"([一二两三四五六七八九十])\s*年", t)
    if m:
        return float(_NUM[m.group(1)])
    m = re.search(r"(\d+)\s*个月", t)
    if m:
        return int(m.group(1)) / 12
    return None


def parse_max_age(text):
    """'18-38周岁' / '35周岁以下' / '放宽到40周岁' -> 38 / 35 / 40；认不出来 -> None。"""
    t = text or ""
    m = (re.search(r"\d+\s*[-—~～至]\s*(\d+)\s*周?岁", t) or re.search(r"(\d+)\s*周?岁\s*(?:及)?以下", t)
         or re.search(r"(\d+)\s*周岁", t))
    return int(m.group(1)) if m else None


def parse_relaxed_age(text):
    """'放宽到40周岁' / '40周岁以下' -> 40。"""
    m = re.search(r"(\d+)\s*周?岁", text or "")
    return int(m.group(1)) if m else None


def split_list(text):
    return [x.strip() for x in re.split(r"[,，、;；\n]+", text or "") if x.strip()]


# ---------- 应届身份：每个批次有自己的规则 ----------

def fresh_verdict(profile, rule):
    """这个批次里，你算不算应届 -> ('yes' | 'no' | 'maybe', 一句话说明)。

    各地对「应届」的定义不同（要从公告里读，写在批次的 fresh_rule 里）：
      year          按毕业年份：应届 = 当年毕业（浙江省属）
      year_window   毕业 window 年内（含当年）都算应届，不看是否在职（杭州：2024–2026 年毕业生）
      unemployed    毕业 window 年内，且报名时无工作单位（江苏、南京、苏州）
      no_staff_job  毕业 window 年内（含毕业当年），且没有在编制内工作过——私企工作不影响（上海）
      unplaced      当年毕业且非在职；往届 window 年内的要「未落实工作单位」，入职过又离职算不算落实公告没写（广东、深圳）
    规则里 cohort 是该批次「应届」对应的毕业年份；批次已经结束的（rule['closed']），假设下一批规则不变、届别顺延一年。
    profile.fresh 设成 yes / no 就一律按它；maybe 一律待定；auto（默认）才按规则推断。
    """
    pf = profile.get("fresh", "auto")
    if pf in ("yes", "no"):
        return pf, f"按所设定的应届身份（{'应届' if pf == 'yes' else '往届'}）"
    gy = profile.get("graduate_year")
    if pf == "maybe" or not rule or gy is None:
        return "maybe", "是否属于应届取决于当地认定，需查阅公告或咨询招聘单位"
    kind, window = rule["kind"], rule.get("window", 2)
    c = rule["cohort"] + (1 if rule.get("closed") else 0)
    tail = f"（按已结束的这一批的规则推断，假设下一批规则不变、届别顺延到 {c} 届）" if rule.get("closed") else ""
    employed = bool(profile.get("employed_now"))
    if kind == "year":
        return ("yes" if gy == c else "no"), f"该批次按毕业年份判断：应届 = {c} 年毕业，考生为 {gy} 年毕业{tail}"
    if kind == "year_window":
        lo = c - window
        return (("yes" if lo <= gy <= c else "no"),
                f"该批次应届含 {lo}–{c} 年毕业，不看是否在职，考生为 {gy} 年毕业{tail}")
    if not c - window <= gy <= c:
        return "no", f"该批次应届限毕业 {window} 年内（{c - window}–{c} 年毕业），考生为 {gy} 年毕业{tail}"
    if kind == "unemployed":
        return (("no", f"该批次要求报名时无工作单位，考生目前在职{tail}") if employed
                else ("yes", f"该批次规则：毕业 {window} 年内且报名时无工作单位，考生符合（报名时仍须无工作单位）{tail}"))
    if kind == "no_staff_job":
        return (("no", f"该批次要求未落实编制内工作，考生有编制内工作经历{tail}") if profile.get("had_staff_job")
                else ("yes", f"该批次规则：毕业 {window} 年内且未落实「编制内」工作，私企工作不影响，考生符合{tail}"))
    if kind == "unplaced":
        if employed:
            return "no", f"该批次要求非在职，考生目前在职{tail}"
        if gy == c or not profile.get("had_any_job"):
            return "yes", f"该批次规则：非在职的当届毕业生或未落实工作单位的往届毕业生，考生符合{tail}"
        return "maybe", f"该批次要求往届毕业生「未落实工作单位」，考生入职后又离职，是否属于「落实」公告未说明，需咨询{tail}"
    raise ValueError(f"未知的应届规则 kind: {kind!r}")


# ---------- 综合判断 ----------

def evaluate(job, profile, fresh_rule=None):
    """返回 {'status': 'ok'|'check'|'no', 'no': [(类别, 说明)], 'check': [说明], 'major': 对口度, 'lower': bool, 'fresh_info': str}。

    fresh_rule 是该批次的应届规则（META["batches"][..]["fresh_rule"]，已结束的批次带 closed=True），见 fresh_verdict。

    major 是专业对口度：'对口'（岗位专业要求里列了你的专业）/ '不限专业' / '需核对' / '不符' / ''（没法比较）。
    lower 为 True 表示岗位只要求较低学历，你只能以较低学历（及其专业）报考。
    """
    no, check = [], []
    major_label = ""
    U = EDU_LEVEL[profile["education"]]
    verdict = []                                    # 应届判断只算一次，后面户籍也会用到

    def fresh():
        if not verdict:
            verdict.extend(fresh_verdict(profile, fresh_rule))
        return verdict

    # 学历：决定后面比较哪一栏专业要求
    edu = parse_education(job["education"])
    use_level = U
    if edu is None:
        check.append(f"学历要求「{job['education']}」写法无法识别，需核对")
    else:
        lv, plus = edu
        if plus:
            if U < lv:
                no.append(("education", f"要求{LEVEL_NAME[lv]}以上，考生为{profile['education']}"))
        elif U < lv:
            no.append(("education", f"要求{LEVEL_NAME[lv]}，考生为{profile['education']}"))
        elif U > lv:
            use_level = lv        # 只要求较低学历：只能用较低学历（及其专业）报考，很多地方不允许
            low_key = {1: "college", 2: "bachelor"}.get(lv)
            if lv == 1 and not (((profile.get("majors") or {}).get(low_key) or {}).get("codes")
                                or ((profile.get("majors") or {}).get(low_key) or {}).get("names")):
                no.append(("education", f"岗位只要求{LEVEL_NAME[lv]}，未填写{LEVEL_NAME[lv]}学历，按无该层次学历处理"))
            else:
                check.append(f"岗位只要求{LEVEL_NAME[lv]}，考生的最高学历更高，需核实能否以{LEVEL_NAME[lv]}学历（及专业）报考")

    # 专业
    if either_major_flag(job) and use_level >= 3:
        # 岗位写明「本科专业、研究生专业符合其一即可」：分别按研究生专业、本科专业比一遍，取对口的
        plain = {**job, "extra": {k: v for k, v in job["extra"].items() if k != "专业口径"}}    # 去掉标记，否则会无限递归
        either = [evaluate({**plain, "major_graduate": job["major_graduate"] or job["major_bachelor"]}, profile, fresh_rule),
                  evaluate({**plain, "education": "本科", "major_bachelor": job["major_bachelor"] or job["major_graduate"]}, profile, fresh_rule)]
        best = min(either, key=lambda e: {"对口": 0, "不限专业": 1, "需核对": 2, "": 3, "不符": 4}.get(e["major"], 3))
        major_label = best["major"]
        if major_label == "不符":
            no.append(("major", "专业要求「本科或研究生专业符合其一」，考生的本科、研究生专业均不在其列"))
        elif major_label == "需核对":
            check.append("专业要求「本科或研究生专业符合其一」，考生专业与岗位表的写法不易对应，需核对")
        skip_major = True
    else:
        skip_major = False
    col = LEVEL_COLUMN[use_level]
    req = parse_major(job[col])
    key = "graduate" if use_level >= 3 else "bachelor" if use_level == 2 else "college"
    mine = (profile.get("majors") or {}).get(key) or {}
    codes, names = mine.get("codes") or [], mine.get("names") or []
    keywords, related = mine.get("keywords") or names, mine.get("related") or []
    if skip_major:
        pass
    elif req.get("unlimited"):
        major_label = "不限专业"
    elif req.get("blank"):
        lower = [(c, k) for c, k in (("major_bachelor", "bachelor"), ("major_college", "college")) if job[c]]
        if not any(job[c] for c in LEVEL_COLUMN.values()):
            major_label = "不限专业"
        elif use_level >= 3 and lower:
            # 「本科以上」的岗位只写了一栏专业（本科栏）：研究生能不能用，各地写法不一，先按你的本科专业比一下，提醒核对
            col, k = lower[0]
            low_req = parse_major(job[col])
            low = (profile.get("majors") or {}).get(k) or {}
            label = {"bachelor": "本科", "college": "大专"}[k]
            if low_req.get("unlimited"):
                major_label = "不限专业"
            elif low.get("codes") or low.get("names"):
                fit = major_fit(low_req, low.get("codes") or [], low.get("names") or [],
                                low.get("keywords") or low.get("names") or [], low.get("related") or [])
                major_label = "对口" if fit == "match" else "需核对"
                check.append(f"岗位只写了{label}专业要求「{low_req['text'][:30]}」，按考生的{label}专业比对："
                             f"{ {'match': '对口', 'check': '可能对口', 'no': '不对口'}[fit] }；研究生能否按此报考需核对")
            else:
                major_label = "需核对"
                check.append(f"岗位只写了{label}专业要求，未填写{label}专业，无法比对")
        else:
            major_label = ""
            check.append(f"该岗位没有写{LEVEL_NAME[use_level]}栏的专业要求，需核对")
    elif not codes and not names:
        major_label = "需核对"
        check.append(f"未填写{LEVEL_NAME[use_level]}专业，无法比对「{req['text'][:30]}」")
    else:
        fit = major_fit(req, codes, names, keywords, related)
        if fit == "match":
            major_label = "对口"
        elif fit == "check":
            major_label = "需核对"
            check.append(f"专业要求「{req['text'][:40]}」写法特殊或比考生专业更细，需核对")
        else:
            major_label = "不符"
            no.append(("major", f"专业要求「{req['text'][:40]}」不含考生专业"))

    # 考生类别（应届 / 往届 / 在编）
    cat = job["fresh"]
    fresh_info = ""
    zaibian, past_only, fresh_only = category_flags(cat)
    if zaibian:
        no.append(("fresh", f"考生类别「{cat}」，仅限在编人员报考"))
    if fresh_only:
        v, note = fresh()
        fresh_info = note
        if v == "no":
            no.append(("fresh", f"限应届毕业生，{note}"))
        elif v == "maybe":
            check.append(f"限应届毕业生：{note}")
    elif past_only:
        v, note = fresh()
        if v == "yes":
            no.append(("fresh", f"限往届 / 社会人员，而{note}"))
        elif v == "maybe":
            check.append(f"限往届 / 社会人员：{note}")

    # 工作经历
    years = parse_experience_years(job["experience"])
    wm = profile.get("work_months")
    if years is None:
        check.append(f"工作经历要求「{job['experience'][:30]}」无法识别，需核对")
    elif years > 0:
        if wm is None:
            check.append(f"要求 {years:g} 年工作经历，未填写工作经历月数")
        elif wm < years * 12:
            no.append(("experience", f"要求 {years:g} 年工作经历，考生有 {wm:g} 个月"))

    # 年龄
    age = profile.get("age")
    if age is not None:
        mx = parse_max_age(job["age"])
        relaxed = None
        if U >= 3:
            rtext = job["age_relaxed"] if U == 3 else doctor_relaxed_text(job)
            relaxed = parse_relaxed_age(rtext)
        mx = max(mx, relaxed) if (mx and relaxed) else (mx or relaxed)
        if mx is not None and age > mx:
            no.append(("age", f"年龄上限 {mx} 周岁，考生 {age} 岁"))
        elif mx is None and job["age"]:
            check.append(f"年龄要求「{job['age'][:20]}」无法识别，需核对")

    # 性别：只有岗位明确限定了才筛，没填性别时只提醒
    need = gender_restriction(job)
    if need:
        mine_g = profile.get("gender")
        if mine_g is None:
            check.append(f"岗位限{need}性，未填写性别")
        elif mine_g != need:
            no.append(("gender", f"岗位限{need}性，考生为{mine_g}性"))

    # 专项招聘（退役军人、基层服务项目人员、残疾人……）
    if job["special"] and not profile.get("include_special"):
        no.append(("special", f"专项招聘：{job['special']}"))

    # 资格证书（英语四六级单独处理：六级满足四级；没填英语等级就只提醒，不判不符）
    held = profile.get("certs") or []
    missing = []
    for c in split_list(job["certs"]):
        if re.search(r"英语[四六]级|CET", c):
            need = 6 if ("六级" in c and U >= 3) or ("四级" not in c) else 4
            have = profile.get("english")
            if have is None:
                check.append(f"要求大学英语{'六' if need == 6 else '四'}级，未填写英语等级")
            elif {"CET4": 4, "CET6": 6}.get(have, 0) < need:
                missing.append(c)
        elif not any(h in c or c in h for h in held):
            missing.append(c)
    if missing:
        no.append(("certs", f"要求资格证书：{'、'.join(missing)}"))

    # 职称
    if job["title_req"]:
        no.append(("title", f"要求职称：{job['title_req']}"))

    # 政治面貌
    pol = job["politics"]
    mine_pol = profile.get("politics")
    if pol:
        if mine_pol is None:
            check.append(f"政治面貌要求「{pol}」，未填写政治面貌")
        elif ("党员" in pol and "党员" not in mine_pol) or ("团员" in pol and "党员" not in pol
                                                        and not any(x in mine_pol for x in ("党员", "团员"))):
            no.append(("politics", f"政治面貌要求「{pol}」，考生为{mine_pol}"))

    # 户籍：明确写「限……户籍」「须具有……户籍 / 居住证」的，和你的户籍对不上就是不符；其他写法只提醒
    if job["hukou"]:
        text = job["hukou"]
        mine_h = profile.get("hukou") or []
        mine_h = [mine_h] if isinstance(mine_h, str) else list(mine_h)     # 可以写 "揭阳"，也可以写 ["广东", "揭阳"]
        held = mine_h + list(profile.get("residence") or [])                # residence：你持有有效居住证的城市
        explicit, only_nonfresh = hukou_flags(text)
        shown = f"户籍要求：{text[:50]}（考生户籍：{'、'.join(mine_h) or '未填'}）"
        if only_nonfresh and fresh()[0] == "yes":
            pass                                                            # 这条只针对非应届，你算应届，不受影响
        elif any(h and h in text for h in held):
            pass
        elif explicit and only_nonfresh and fresh()[0] == "maybe":
            check.append(shown + "；若考生属于应届则不受此限")
        elif explicit:
            no.append(("hukou", shown))
        else:
            check.append(shown)
    if job["other"]:
        check.append(f"其他条件：{job['other'][:60]}")

    status = "no" if no else "check" if check else "ok"
    return {"status": status, "no": no, "check": check, "major": major_label, "lower": use_level < U,
            "fresh_info": fresh_info}


def main_reason(no):
    """被判不符的岗位，按 REASON_ORDER 取第一个类别，用来统计。"""
    kinds = {k for k, _ in no}
    return next((k for k in REASON_ORDER if k in kinds), None)
