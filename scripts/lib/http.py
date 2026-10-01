"""各地区抓取脚本共用的 HTTP 小工具。"""
import time
from pathlib import Path

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "raw"


class FetchError(RuntimeError):
    """抓取失败。抛出后 fetch_region.py 会以非零退出码结束，update.py 据此中止。"""


def new_session(**headers):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, **headers})
    return s


def download(url, dest, what="下载", tries=4, magic=(b"PK", b"\xd0\xcf\x11\xe0")):
    """带重试地下载文件到 dest（相对 raw/ 或绝对路径），返回 Path。

    magic: 期望的文件头（bytes 或 tuple），默认 PK（xlsx / docx / zip）或 OLE（xls / doc）。服务器出错时常常返回一个 200 的 HTML 错误页，
    不检查文件头就会把它当成岗位表去解析。
    """
    dest = Path(dest)
    if not dest.is_absolute():
        dest = RAW_DIR / dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = ""
    for attempt in range(tries):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=(15, 90))
            r.raise_for_status()
            if magic and not r.content.startswith(magic):
                last = f"返回的不是预期的文件（开头 {r.content[:20]!r}）"
            else:
                dest.write_bytes(r.content)
                return dest
        except Exception as e:
            last = f"请求失败: {e}"
        print(f"{what}: {last}（第 {attempt + 1}/{tries} 次）", flush=True)
        time.sleep(2 * (attempt + 1))
    raise FetchError(f"{what}连续失败，已停止：{last}")


def get_text(url, what="请求", tries=4):
    """带重试地取网页文本（用来读公告页的发布日期等）。"""
    last = ""
    for attempt in range(tries):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
            r.raise_for_status()
            try:           # 不用 r.apparent_encoding：它靠 chardet 猜编码，对 200KB 的中文页要猜将近一分钟
                return r.content.decode("utf-8")
            except UnicodeDecodeError:
                return r.content.decode("gb18030", errors="replace")
        except Exception as e:
            last = f"请求失败: {e}"
        print(f"{what}: {last}（第 {attempt + 1}/{tries} 次）", flush=True)
        time.sleep(2 * (attempt + 1))
    raise FetchError(f"{what}连续失败，已停止：{last}")
