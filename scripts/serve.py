"""本地预览看板：python3 scripts/serve.py [端口，默认 8000]，然后打开 http://localhost:8000。

和 `python3 -m http.server -d site` 的区别：每次都让浏览器重新校验，更新数据后刷新页面就是最新的，
不会因为浏览器缓存了旧的数据或 app.js 而看到过期内容。只监听 127.0.0.1：本机的 site/data 里可能有 profile.local.json
（你的个人条件，来自 profile.json），不要让它暴露到局域网或公网；要公开请用 scripts/publish.py。
"""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"


class NoCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *args):   # 不刷屏
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"http://localhost:{port}  （Ctrl+C 退出）")
    ThreadingHTTPServer(("127.0.0.1", port), partial(NoCache, directory=str(SITE))).serve_forever()
