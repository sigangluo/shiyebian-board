"""把看板（含全部岗位数据，不含任何个人条件）发布到 gh-pages 分支，这个分支永远只有一个提交。

为什么单提交：岗位数据每次更新都会变，如果都提交进历史，旧数据会一直留在 git 历史里。
这里的做法是：把 site/ 拷到临时目录，用 build.py --public 把数据构建进去，在里面新建一个只有一个提交的仓库，强制推送到 gh-pages。

个人条件的保护（发布到公开网站前最重要的一步）：
  - 构建用 --public --out 临时目录：不读 profile.json，不生成 profile.local.json，也不碰你本机的 site/data；
  - 构建后再检查一遍：临时目录里不能有 profile 相关文件，index.json 里 local_profile 必须是 false；
  - 个人条件在访问者自己的浏览器里（localStorage），从来不在发布的文件里。

用法:
    python3 scripts/publish.py           # 只构建发布目录并检查，不推送（安全，默认）
    python3 scripts/publish.py --push    # 确认无误后加上，强制推送 gh-pages

前提: 仓库已配置 remote（默认 origin），并在 GitHub 的 Settings → Pages 里把 Source 设为 gh-pages 分支。
提交作者取本仓库 git config 里的 user.name / user.email —— 发布到外部平台前请确认它是你想公开的身份（不要用公司 / 内网邮箱）。
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def git(*args, cwd=ROOT, check=True):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and p.returncode:
        sys.exit(f"git {' '.join(args)} 失败:\n{p.stderr.strip()}")
    return p.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true", help="真的推送（不加就只构建和检查）")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--branch", default="gh-pages")
    args = ap.parse_args()

    name, email = git("config", "user.name", check=False), git("config", "user.email", check=False)
    if not name or not email:
        sys.exit("git 没有配置提交作者。先在本仓库里运行:\n  git config user.name <名字>\n  git config user.email <你想公开的邮箱>")

    with tempfile.TemporaryDirectory(prefix="shiye-publish-") as tmp:
        stage = Path(tmp)
        shutil.copytree(SITE, stage, ignore=shutil.ignore_patterns("data"), dirs_exist_ok=True)
        p = subprocess.run([sys.executable, "-W", "ignore", str(ROOT / "scripts" / "build.py"), "--public", "--out", str(stage / "data")],
                           capture_output=True, text=True)
        if p.returncode:
            sys.exit(f"构建失败:\n{p.stdout}\n{p.stderr}")
        print(p.stdout.strip().splitlines()[0])
        (stage / ".nojekyll").write_text("")            # 别让 Pages 用 Jekyll 处理这些文件

        # 保护个人条件：再检查一遍
        bad = [f for f in stage.rglob("*") if f.is_file() and "profile" in f.name.lower()]
        index = json.loads((stage / "data" / "index.json").read_text(encoding="utf-8"))
        if bad or index.get("local_profile"):
            sys.exit(f"发布目录里发现个人条件相关内容，已中止: {[str(b.relative_to(stage)) for b in bad]} local_profile={index.get('local_profile')}")

        files = [f for f in stage.rglob("*") if f.is_file()]
        size = sum(f.stat().st_size for f in files) / 1e6
        print(f"发布内容: {len(files)} 个文件，{size:.1f} MB（数据日期 {index['generated']}）；已确认不含个人条件")
        print(f"提交作者: {name} <{email}>")

        remote_url = git("remote", "get-url", args.remote, check=False)
        if remote_url and "://" not in remote_url and "@" not in remote_url:   # 本地路径的远端：相对路径要按仓库根目录解析
            remote_url = str((ROOT / remote_url).resolve())
        if not args.push:
            print(f"\n未推送。目标: {remote_url or '（还没有配置 remote %s）' % args.remote} 的 {args.branch} 分支（强制覆盖，只留一个提交）")
            print("确认无误后运行: python3 scripts/publish.py --push")
            return
        if not remote_url:
            sys.exit(f"没有 remote「{args.remote}」，先运行: git remote add {args.remote} <仓库地址>")

        git("init", "-q", "-b", args.branch, cwd=stage)
        git("config", "user.name", name, cwd=stage)
        git("config", "user.email", email, cwd=stage)
        git("add", "-A", cwd=stage)
        git("commit", "-q", "-m", f"publish: 数据日期 {index['generated']}", cwd=stage)
        git("push", "--force", remote_url, f"HEAD:{args.branch}", cwd=stage)
        print(f"已强制推送到 {remote_url} 的 {args.branch} 分支。Pages 通常一两分钟后更新。")


if __name__ == "__main__":
    main()
