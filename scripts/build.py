"""把各地区的 CSV 合并成看板数据。**这里不按个人条件筛选**：公开的看板包含全部岗位，筛选在浏览器里做
（site/assets/match.js），个人条件只存在使用者自己的浏览器里。

读:  data/<地区>/<批次>.csv      （由 fetch_region.py 产出，保留岗位表原文）
写:  site/data/index.json                  地区、批次的元信息（前端启动时先读它）
     site/data/jobs/<地区>-<批次>.json     这个批次的全部岗位（原文 + 解析好的字段，格式见 lib/export.py）
     site/data/csv/<地区>-<批次>.csv       这个批次全部岗位的 CSV 副本，供页面上下载
     site/data/profile.local.json          仅限本机：如果有 profile.json，复制一份让页面自动载入（--public 时不生成）

如果有 profile.json，还会用 Python 版的匹配规则（lib/match.py）算一遍并打印摘要——这是抽查新地区数据、
核对前后端结果一致的主要手段，不影响生成的文件。

用法:
    python3 scripts/build.py                 # 以今天为数据日期；本机有 profile.json 就生成 profile.local.json
    python3 scripts/build.py --date 2026-10-05
    python3 scripts/build.py --public        # 发布用：绝不带上个人条件（scripts/publish.py 用的就是这个）
"""
import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.export import export_job
from lib.match import REASON_LABEL, batch_rule, evaluate, load_profile, main_reason
from lib.regions import ROOT, discover
from lib.schema import read_jobs

SITE_DATA = ROOT / "site" / "data"
# 不进前端的批次字段：下载地址、岗位数下限只对抓取有用
HIDDEN_BATCH_KEYS = ("min_jobs", "table_url", "tables")


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def batch_status(b, today):
    """报名状态：open 报名中 / upcoming 即将开始 / closed 已结束 / rolling 没有统一报名时间。前端有同样的函数。"""
    if not b.get("signup_start"):
        return "rolling"
    if today < b["signup_start"]:
        return "upcoming"
    return "open" if today <= b["signup_end"] else "closed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat(), help="数据日期 YYYY-MM-DD")
    ap.add_argument("--public", action="store_true", help="发布用：不生成 profile.local.json，也不打印个人条件的匹配摘要")
    ap.add_argument("--out", default=str(SITE_DATA), help="输出目录（默认 site/data；publish.py 用它构建到临时目录）")
    args = ap.parse_args()
    today = args.date
    site_data = Path(args.out)

    for stale in (site_data / "jobs", site_data / "csv"):      # 每次整体重建，已移除的批次不会残留
        shutil.rmtree(stale, ignore_errors=True)
    for stale in ("jobs.json", "index.json", "profile.local.json"):
        (site_data / stale).unlink(missing_ok=True)

    profile = None if args.public else load_profile()          # --public：连读都不读，绝不可能带出个人条件
    regions, summary = [], []
    out_counts, total_kept = Counter(), 0
    for r in discover():
        if not r.data_dir.exists() or not list(r.data_dir.glob("*.csv")):
            print(f"⚠ {r.meta['name']}（{r.key}）还没有数据，已跳过。先运行: python3 scripts/update.py --only {r.key}")
            continue
        batches = []
        for bkey, b in r.meta["batches"].items():
            f = r.data_dir / f"{bkey}.csv"
            if not f.exists():
                print(f"⚠ {r.meta['name']} 批次 {bkey} 没有 CSV，已跳过")
                continue
            jobs = read_jobs(f)
            name = f"{r.key}-{bkey}"
            dump(site_data / "jobs" / f"{name}.json", [export_job(j, r.key) for j in jobs])
            (site_data / "csv").mkdir(parents=True, exist_ok=True)
            shutil.copy(f, site_data / "csv" / f"{name}.csv")
            batches.append({"key": bkey, **{k: v for k, v in b.items() if k not in HIDDEN_BATCH_KEYS},
                            "total": len(jobs), "file": f"jobs/{name}.json", "csv": f"csv/{name}.csv"})
            if profile:      # Python 版的匹配：只用来打印摘要
                status = batch_status(b, today)
                fr = batch_rule(b)
                rule = {**fr, "closed": status == "closed"} if fr else None
                kept = 0
                for j in jobs:
                    ev = evaluate(j, profile, rule)
                    if ev["status"] == "no":
                        out_counts[main_reason(ev["no"])] += 1
                    else:
                        kept += 1
                total_kept += kept
                summary.append((r.meta["name"], b["name"], status, kept, len(jobs)))
        regions.append({"key": r.key, "name": r.meta["name"], "list_url": r.meta["list_url"], "note": r.meta["note"],
                        "batches": batches})
    if not regions:
        sys.exit("没有任何地区有数据，先运行: python3 scripts/update.py")

    has_profile = bool(profile)
    if has_profile:
        raw = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
        dump(site_data / "profile.local.json", {k: v for k, v in raw.items() if not k.startswith("_")})
    dump(site_data / "index.json", {"generated": today, "regions": regions, "local_profile": has_profile})

    n_jobs = sum(b["total"] for r in regions for b in r["batches"])
    print(f"{today}：{len(regions)} 个地区、{sum(len(r['batches']) for r in regions)} 个批次、共 {n_jobs} 个岗位"
          + ("（--public：未带个人条件）" if args.public else ""))
    if profile:
        print(f"  Python 版匹配（按 profile.json）：保留 {total_kept}，不符 {sum(out_counts.values())}")
        print("  不符的原因:", "、".join(f"{REASON_LABEL[k]} {n}" for k, n in out_counts.most_common()) or "无")
        for name, bname, status, kept, total in summary:
            print(f"  {name} · {bname}（{status}）: {kept} / {total}")
    else:
        print("  没有 profile.json，没有打印匹配摘要。")


if __name__ == "__main__":
    main()
