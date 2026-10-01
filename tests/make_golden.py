"""生成 JS 版匹配规则的交叉测试样例（tests/golden/cases.json）。

用 Python 版的 evaluate() 算「岗位 + 个人条件 + 批次应届规则 → 结果」，JS 版（site/assets/match.js）必须给出一模一样的结果：
    python3 tests/make_golden.py      # 需要 data/ 里有抓取好的岗位表；样例文件提交进仓库，贡献者不用重新抓取
    node --test tests/                # 逐条核对 JS 版

个人条件都是合成的，覆盖不同学历、应届身份、户籍、证书等组合，不是任何真人的信息。
改了 scripts/lib/match.py 或 scripts/lib/export.py 的规则后要重新生成，并且 JS 版要跟着改。
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.export import export_job
from lib.match import evaluate
from lib.regions import discover
from lib.schema import read_jobs

PROFILES = [
    {"education": "硕士", "majors": {"graduate": {"codes": ["A0812"], "names": ["计算机科学与技术"], "keywords": ["计算机", "软件", "工学"], "related": ["信息", "电子"]},
                                    "bachelor": {"codes": ["B080901"], "names": ["计算机科学与技术"]}},
     "fresh": "auto", "graduate_year": 2026, "employed_now": False, "had_staff_job": False, "had_any_job": True,
     "work_months": 3, "age": 25, "politics": "共青团员", "hukou": ["广东", "汕头"], "residence": [], "english": "CET6",
     "certs": [], "gender": "男", "include_special": False},
    {"education": "本科", "majors": {"bachelor": {"codes": ["B080901"], "names": ["计算机科学与技术"], "keywords": ["计算机"]}},
     "fresh": "yes", "graduate_year": 2026, "work_months": 0, "politics": "群众", "english": "CET4", "gender": "女"},
    {"education": "博士", "majors": {"graduate": {"codes": ["A0812"], "names": ["计算机科学与技术"]}}, "fresh": "no", "graduate_year": 2020,
     "employed_now": True, "had_staff_job": True, "had_any_job": True, "work_months": 60, "age": 33, "politics": "中共党员",
     "hukou": "上海", "residence": ["上海"], "english": "CET6", "certs": ["教师资格"], "include_special": True},
    {"education": "硕士", "fresh": "maybe"},
    {"education": "硕士", "majors": {"graduate": {"codes": ["A0835"], "names": ["软件工程"]}, "college": {"names": ["计算机应用技术"]}},
     "fresh": "auto", "graduate_year": 2025, "employed_now": True, "had_any_job": False, "work_months": 30, "age": 41,
     "hukou": ["浙江", "杭州"], "gender": "女", "english": "CET4"},
    {"education": "大专", "majors": {"college": {"names": ["计算机应用技术"], "codes": []}}, "fresh": "yes", "work_months": 12, "age": 22},
]
CLOSED_AT = "2026-10-02"
PER_BATCH_RANDOM, PER_FEATURE, PER_POSITIVE = 25, 6, 8
FEATURES = ("ei", "zb", "pn", "fo", "he", "hn", "gd", "xy", "adx", "arx", "cl", "ti", "sp", "po")


def main():
    random.seed(20261002)
    jobs, raw, rules = [], [], {}
    for r in discover():
        for bkey, b in r.meta["batches"].items():
            f = r.data_dir / f"{bkey}.csv"
            if not f.exists():
                sys.exit(f"缺少 {f}，先运行 python3 scripts/update.py")
            allj = read_jobs(f)
            pick = {id(j) for j in random.sample(allj, min(PER_BATCH_RANDOM, len(allj)))}
            exported = [(j, export_job(j, r.key)) for j in allj]
            for feat in FEATURES:                              # 每个解析字段至少抽几个有值的，保证各分支都有样例
                have = [j for j, e in exported if feat in e]
                pick |= {id(j) for j in random.sample(have, min(PER_FEATURE, len(have)))}
            fr = b.get("fresh_rule")
            for i, p in enumerate(PROFILES):                    # 每组条件再各抽几个「没被筛掉」的，保证符合 / 待确认的分支也有足够样例
                rule = {**fr, "closed": i % 2 == 0} if fr else None
                have = [j for j in allj if evaluate(j, p, rule)["status"] != "no"]
                pick |= {id(j) for j in random.sample(have, min(PER_POSITIVE, len(have)))}
            for j, e in exported:
                if id(j) in pick:
                    jobs.append(e)
                    raw.append(j)
            fr = b.get("fresh_rule")
            rules[f"{r.key}/{bkey}"] = fr
    expected = []
    for i, p in enumerate(PROFILES):
        closed = i % 2 == 0             # 偶数号条件按「批次已结束」算（届别顺延一年），奇数号按「还没结束」算
        row = []
        for e, j in zip(jobs, raw):
            fr = rules[f"{e['r']}/{e['b']}"]
            ev = evaluate(j, p, {**fr, "closed": closed} if fr else None)
            row.append({"status": ev["status"], "no": [list(x) for x in ev["no"]], "check": ev["check"], "major": ev["major"],
                        "lower": ev["lower"], "fresh_info": ev["fresh_info"]})
        expected.append(row)
    out = ROOT / "tests" / "golden" / "cases.json"
    out.write_text(json.dumps({"profiles": PROFILES, "rules": rules, "closed_by_profile": [i % 2 == 0 for i in range(len(PROFILES))],
                               "jobs": jobs, "expected": expected}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    from collections import Counter
    print(f"{len(jobs)} 个岗位 × {len(PROFILES)} 组条件 = {len(jobs) * len(PROFILES)} 条样例 -> {out}（{out.stat().st_size / 1e6:.2f} MB）")
    for i in range(len(PROFILES)):
        print(f"  条件 {i}:", dict(Counter(e['status'] for e in expected[i])))


if __name__ == "__main__":
    main()
