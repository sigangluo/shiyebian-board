"""更新数据：重新抓取各地区的岗位表，再合并成看板数据。

用法:
    python3 scripts/update.py                        # 抓取 regions/ 下所有地区 + 合并
    python3 scripts/update.py --only guangdong       # 只重抓指定地区
    python3 scripts/update.py --build-only           # 不抓取，只用现有 data/*/*.csv 重新合并（改了 profile.json 后用这个）
    python3 scripts/update.py --list                 # 列出当前有哪些地区和批次

地区由 regions/ 下的目录自动发现，新增地区不用改这里。各地互不依赖、访问不同站点，所以并行跑。
任何一个地区失败都会中止，不会拿旧 CSV 混进新数据。
"""
import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)   # 管道 / 重定向时也按行输出，避免和子进程输出顺序错乱
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from lib.regions import discover


def run(r):
    started = time.time()
    p = subprocess.run([sys.executable, "-W", "ignore", str(SCRIPTS / "fetch_region.py"), r.key],
                       capture_output=True, text=True)
    lines = [ln for ln in p.stdout.strip().splitlines() if ln]
    tail = [ln for ln in lines[:-4] if ln.startswith("⚠")] + lines[-4:]    # 只截取最后几行，但 ⚠ 警告不能被截掉
    # 退出码为 0 也要确认 CSV 真的被刷新了
    stale = [f.name for f in r.data_dir.glob("*.csv") if f.stat().st_mtime < started] if r.data_dir.exists() else ["（没有产出任何 CSV）"]
    ok = p.returncode == 0 and not stale and any(r.data_dir.glob("*.csv"))
    return r, ok, tail, p.stderr.strip().splitlines()[-3:], stale, time.time() - started


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只抓这些地区（key），逗号分隔")
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--list", action="store_true")
    args, rest = ap.parse_known_args()

    if args.list:
        for r in discover():
            print(f"{r.key:12} {r.meta['name']}  {r.meta['list_url']}")
            for bk, b in r.meta["batches"].items():
                print(f"{'':14}{bk}: {b['name']}（公告 {b['published']}）")
        return

    if not args.build_only:
        regions = discover(args.only.split(",") if args.only else None)
        print(f"并行抓取: {', '.join(r.key for r in regions)} ...")
        failed = []
        with ThreadPoolExecutor(max_workers=len(regions)) as pool:
            for r, ok, tail, err, stale, secs in pool.map(run, regions):
                print(f"\n[{r.key}] {'完成' if ok else '失败'}（{secs:.0f}s）")
                for ln in tail:
                    print("   ", ln)
                if not ok:
                    failed.append(r.key)
                    for ln in err:
                        print("    !", ln)
                    if stale:
                        print("    ! 这些 CSV 没有被更新:", ", ".join(stale))
        if failed:
            sys.exit(f"\n抓取失败: {', '.join(failed)}。已中止，未合并。修好后可用 --only {','.join(failed)} 重抓，再 --build-only。")

    print("\n合并数据 ...")
    subprocess.run([sys.executable, str(SCRIPTS / "build.py"), *rest], check=True)


if __name__ == "__main__":
    main()
