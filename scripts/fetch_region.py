"""抓取一个地区，校验后写出 data/<key>/<批次>.csv。

用法:  python3 scripts/fetch_region.py <key>
一般不直接用，由 update.py 并行调用；也可以单独跑来调试新加的地区。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # 让地区的 fetch.py 能 from lib... 导入

from lib.regions import discover
from lib.schema import count_rows, to_frame, validate

DROP_WARN = 0.3   # 比上次少了这么多以上就报警：多半是抓取不全，而不是真的撤岗


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    (r,) = discover([sys.argv[1]])
    jobs = validate(r.module.fetch(), r.meta)
    before = count_rows(r.data_dir.glob("*.csv")) if r.data_dir.exists() else 0   # 覆盖前的岗位数
    if before and len(jobs) < before * (1 - DROP_WARN):
        print(f"⚠ 岗位数 {before} -> {len(jobs)}，减少超过 {DROP_WARN:.0%}，可能是抓取不全，请检查上面的输出", flush=True)
    r.data_dir.mkdir(parents=True, exist_ok=True)
    written = set()
    for bkey in r.meta["batches"]:
        part = [j for j in jobs if j["batch"] == bkey]
        to_frame(part).to_csv(r.data_dir / f"{bkey}.csv", index=False, encoding="utf-8-sig")
        written.add(f"{bkey}.csv")
        print(f"  {bkey}: {len(part)} 个岗位", flush=True)
    for stale in r.data_dir.glob("*.csv"):     # META["batches"] 改过之后，清掉不再产出的旧文件
        if stale.name not in written:
            stale.unlink()
    print(f"完成：共 {len(jobs)} 个岗位 -> {r.data_dir}", flush=True)


if __name__ == "__main__":
    main()
