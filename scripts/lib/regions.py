"""自动发现 regions/ 下的地区：每个含 fetch.py 的子目录就是一个地区，目录名就是它的 key。

以 _ 或 . 开头的目录（如 _template）会被跳过。新增地区不需要改任何其他文件。
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from .schema import is_date

ROOT = Path(__file__).resolve().parents[2]
REGIONS_DIR = ROOT / "regions"
DATA_DIR = ROOT / "data"
REQUIRED_META = ("name", "list_url", "batches")
REQUIRED_BATCH = ("name", "published", "notice_url")
FRESH_KINDS = ("year", "unemployed", "no_staff_job", "unplaced")      # 含义见 lib/match.py 的 fresh_verdict


def _check_batches(key, batches):
    if not isinstance(batches, dict) or not batches:
        raise RuntimeError(f"regions/{key} 的 META['batches'] 必须是 {{批次key: {{...}}}}，且不能为空")
    for bk, b in batches.items():
        missing = [k for k in REQUIRED_BATCH if not b.get(k)]
        if missing:
            raise RuntimeError(f"regions/{key} 批次 {bk} 缺少: {missing}")
        if not is_date(b["published"]):
            raise RuntimeError(f"regions/{key} 批次 {bk} 的 published 要写成 YYYY-MM-DD")
        for k in ("signup_start", "signup_end"):
            if b.get(k) and not is_date(b[k]):
                raise RuntimeError(f"regions/{key} 批次 {bk} 的 {k} 要写成 YYYY-MM-DD")
        fr = b.get("fresh_rule")
        if fr is not None and (fr.get("kind") not in FRESH_KINDS or not isinstance(fr.get("cohort"), int)):
            raise RuntimeError(f"regions/{key} 批次 {bk} 的 fresh_rule 要写成 dict(kind=…, cohort=2026[, window=2])，kind 只能是 {FRESH_KINDS}")
        if bool(b.get("signup_start")) != bool(b.get("signup_end")):
            raise RuntimeError(f"regions/{key} 批次 {bk} 的 signup_start 和 signup_end 要么都写要么都不写")


def _load(d):
    key = d.name
    spec = importlib.util.spec_from_file_location(f"region_{key}", d / "fetch.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        raise RuntimeError(f"regions/{key}/fetch.py 导入失败: {e}") from e
    meta = getattr(mod, "META", None)
    if not isinstance(meta, dict) or not callable(getattr(mod, "fetch", None)):
        raise RuntimeError(f"regions/{key}/fetch.py 必须定义 META（dict）和 fetch()")
    missing = [k for k in REQUIRED_META if not meta.get(k)]
    if missing:
        raise RuntimeError(f"regions/{key}/fetch.py 的 META 缺少: {missing}")
    _check_batches(key, meta["batches"])
    meta = {"order": 100, "note": "", "fresh_note": "", **meta}
    return SimpleNamespace(key=key, dir=d, module=mod, meta=meta, data_dir=DATA_DIR / key)


def discover(only=None):
    """返回所有地区，按 META['order'] 再按 key 排序。only 是 key 列表，用来只取其中几个。"""
    found = [_load(d) for d in sorted(REGIONS_DIR.iterdir())
             if d.is_dir() and not d.name.startswith(("_", ".")) and (d / "fetch.py").exists()]
    if only is not None:
        unknown = [k for k in only if k not in {r.key for r in found}]
        if unknown:
            raise SystemExit(f"未知地区: {unknown}，可选: {[r.key for r in found]}")
        found = [r for r in found if r.key in only]
    return sorted(found, key=lambda r: (r.meta["order"], r.key))
