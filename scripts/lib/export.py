"""把一个岗位导出成前端用的紧凑格式：岗位表原文（显示用）+ 已经解析好的字段（比较用）。

文字解析（学历、专业代码、经历年限、年龄上限、考生类别、户籍写法……）都在这里用 match.py 里的同一批函数做完，
浏览器里的 site/assets/match.js 只做「岗位字段 vs 你的条件」的比较，不再解析文字——这样解析规则只有 Python 一份。

字段名（空值不导出，前端当空字符串 / 空列表 / false 处理）:
  显示用:  id r b ci un dp du gr n fr ed dg mc mb mg ag ar xp cr ti po ex sp ho ot u x
  解析后:  el ep        学历要求的层次（1 大专 2 本科 3 硕士 4 博士；认不出来就没有）和是否「以上」
           kc kb kg     大专 / 本科 / 研究生三栏专业要求的类型：u 不限 / c 带代码 / t 只有文字（没有这个字段就是空栏）
           cc cb cg     三栏专业要求里的专业代码
           xy           工作经历要求的年限（没有这个字段 = 无要求；null = 写了但认不出年限）
           amx arx adx  年龄上限 / 硕士放宽后的上限 / 博士放宽后的上限
           gd           性别限定：女 / 男
           cl           资格证书列表
           ei           专业按「本科或研究生符合其一」
           zb pn fo     考生类别：限在编人员 / 限往届或社会人员 / 限应届
           he hn        户籍要求：明确限定 / 只针对非应届
"""
from .match import (category_flags, doctor_relaxed_text, either_major_flag, gender_restriction, hukou_flags,
                    parse_education, parse_experience_years, parse_major, parse_max_age, parse_relaxed_age, split_list)
from .schema import normalize_city


def _major(text):
    """专业要求 -> (类型, 代码列表)。类型：b 空栏 / u 不限 / c 带代码 / t 只有文字。"""
    req = parse_major(text)
    if req.get("blank"):
        return "b", []
    if req.get("unlimited"):
        return "u", []
    return ("c" if req["codes"] else "t"), req["codes"]


def export_job(j, region_key):
    """标准岗位（schema.make_job 的结果）-> 前端用的紧凑 dict。"""
    zb, pn, fo = category_flags(j["fresh"])
    edu = parse_education(j["education"])
    mc, mb, mg = (_major(j[c]) for c in ("major_college", "major_bachelor", "major_graduate"))
    he, hn = hukou_flags(j["hukou"]) if j["hukou"] else (False, False)
    out = {
        "id": j["id"], "r": region_key, "b": j["batch"], "ci": normalize_city(j["city"]), "un": j["unit"], "dp": j["dept"],
        "du": j["duty"], "gr": j["grade"], "n": int(j["headcount"] or 0), "fr": j["fresh"], "ed": j["education"],
        "dg": j["degree"], "mc": j["major_college"], "mb": j["major_bachelor"], "mg": j["major_graduate"],
        "ag": j["age"], "ar": j["age_relaxed"], "xp": j["experience"], "cr": j["certs"], "ti": j["title_req"],
        "po": j["politics"], "ex": j["exam"], "sp": j["special"], "ho": j["hukou"], "ot": j["other"],
        "u": j["url"] if j["url"].startswith("https://") else "",
        # 岗位表里没进标准字段的其他信息（其它条件原文、主管单位……），在详情里显示
        "x": [[k, v] for k, v in j["extra"].items() if k != "岗位表" and len(v) <= 400],
        # 解析后的字段
        "el": edu[0] if edu else None, "ep": bool(edu and edu[1]),
        "kc": mc[0] if mc[0] != "b" else "", "kb": mb[0] if mb[0] != "b" else "", "kg": mg[0] if mg[0] != "b" else "",
        "cc": mc[1], "cb": mb[1], "cg": mg[1],
        "xy": parse_experience_years(j["experience"]),
        "amx": parse_max_age(j["age"]), "arx": parse_relaxed_age(j["age_relaxed"]),
        "adx": parse_relaxed_age(doctor_relaxed_text(j)),
        "gd": gender_restriction(j), "cl": split_list(j["certs"]), "ei": either_major_flag(j),
        "zb": zb, "pn": pn, "fo": fo, "he": he, "hn": hn,
    }
    # 空值不导出以减小体积；xy 的 None（写了但认不出）要保留，0（没有要求）可以省
    return {k: v for k, v in out.items() if k == "xy" and v is None or v not in ("", [], None, False, 0) or k in ("id", "r", "b", "n")}
