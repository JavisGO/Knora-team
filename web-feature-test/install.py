#!/usr/bin/env python3
"""web-feature-test 一键安装（只用标准库，Windows / macOS / Linux 通用）。

用法（在 web-feature-test 目录下执行）：
  python3 install.py                      # 建 .venv、装依赖、预检、跑一次自检
  python3 install.py --skills-dir DIR     # 另外把本目录复制到某个 AI agent 的 skills 目录 DIR/web-feature-test
  python3 install.py --no-venv            # 不建虚拟环境，装进当前 Python 环境
  python3 install.py --no-selftest        # 跳过自检（自检会启动本地演示站点并用浏览器跑 1 个用例）
  python3 install.py --channel msedge     # 用 Edge；没有 Chrome/Edge 时先 python -m playwright install chromium，再用 --channel chromium

做什么：
  1. 检查 Python ≥ 3.9
  2. 创建 .venv 并安装 requirements.txt（除非 --no-venv）
  3. 运行 wft doctor（依赖、浏览器能否启动）
  4. 自检：启动本地演示站点，用浏览器跑 1 个用例（证明“能真的点页面”）
  5. （可选）复制到 skills 目录
不会做的事：不读取、不询问任何账号口令；不访问被测系统；除 .venv 和 --skills-dir 指定的目录外不写别处。

最后会打印一行 `WFT_PYTHON=<解释器路径>`，之后所有命令都用它：  <WFT_PYTHON> -m wft ...
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def venv_python(venv):
    return os.path.join(venv, "Scripts", "python.exe") if os.name == "nt" else os.path.join(venv, "bin", "python")


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=HERE, text=True, encoding="utf-8", errors="replace", **kw)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def selftest(py, channel):
    """启动演示站点，用浏览器跑 TC-01（入口：悬停→更多→进入面板）。"""
    port = free_port()
    out = tempfile.mkdtemp(prefix="wft-selftest-")
    srv = subprocess.Popen([py, os.path.join("examples", "demo-site", "server.py"), str(port)], cwd=HERE,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
                break
            except OSError:
                time.sleep(0.3)
        else:
            print("[FAIL] 演示站点没有起来")
            return False
        r = run([py, "-m", "wft", "run", os.path.join("examples", "demo-site", "demo.spec.json"), "--out", out, "--no-login",
                 "--only", "TC-01", "--no-trace", "--channel", channel,
                 "--var", f"ENTRY_URL=http://127.0.0.1:{port}/index.html"], capture_output=True)
        print((r.stdout or "").strip().splitlines()[-4:] and "\n".join((r.stdout or "").strip().splitlines()[-4:]))
        return r.returncode == 0
    finally:
        srv.terminate()
        shutil.rmtree(out, ignore_errors=True)


def copy_skill(dst_root):
    dst = os.path.join(os.path.abspath(dst_root), "web-feature-test")
    ignore = shutil.ignore_patterns(".venv", "__pycache__", "out*", "*.pyc", ".DS_Store", ".mcp-out")
    if os.path.abspath(dst) == HERE:
        print("[SKIP] 目标就是当前目录，无需复制")
        return dst
    if os.path.exists(dst):
        print(f"[WARN] {dst} 已存在，将覆盖其中同名文件（不会删除多余文件）")
    shutil.copytree(HERE, dst, ignore=ignore, dirs_exist_ok=True)
    print(f"[OK]   已复制到 {dst}")
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skills-dir", help="AI agent 的 skills 目录；会复制到 <DIR>/web-feature-test")
    ap.add_argument("--no-venv", action="store_true")
    ap.add_argument("--no-selftest", action="store_true")
    ap.add_argument("--channel", default=os.environ.get("WFT_CHANNEL", "chrome"))
    args = ap.parse_args()

    if sys.version_info < (3, 9):
        sys.exit("[FAIL] 需要 Python 3.9 或更高版本，当前 " + sys.version.split()[0])
    print(f"[OK]   Python {sys.version.split()[0]}")

    py = sys.executable
    if not args.no_venv:
        venv = os.path.join(HERE, ".venv")
        if not os.path.exists(venv_python(venv)):
            print("…     创建虚拟环境 .venv")
            if run([sys.executable, "-m", "venv", venv]).returncode != 0:
                sys.exit("[FAIL] 创建虚拟环境失败（Linux 可能需要 apt install python3-venv）")
        py = venv_python(venv)
    print("…     安装依赖（首次约 1 分钟；公司内网可先配置 pip 镜像）")
    if run([py, "-m", "pip", "install", "-q", "-r", "requirements.txt"]).returncode != 0:
        sys.exit("[FAIL] 依赖安装失败：检查网络或 pip 镜像后重试")
    print("[OK]   依赖已安装")

    d = run([py, "-m", "wft", "doctor", "--out", tempfile.gettempdir(), "--channel", args.channel], capture_output=True)
    print("\n".join("       " + l for l in (d.stdout or "").strip().splitlines()))
    if d.returncode != 0:
        print("[FAIL] 预检未通过。没有 Chrome/Edge 时：")
        print(f"       {py} -m playwright install chromium   然后重新运行本脚本并加 --channel chromium")
        sys.exit(1)

    ok = True
    if not args.no_selftest:
        print("…     自检：启动本地演示站点，用浏览器跑 1 个用例")
        ok = selftest(py, args.channel)
        print("[OK]   自检通过" if ok else "[FAIL] 自检失败（浏览器没能完成交互，见上方输出）")

    if args.skills_dir:
        copy_skill(args.skills_dir)

    print("\n" + "=" * 60)
    print("安装" + ("完成" if ok else "未完全成功"))
    print(f"WFT_PYTHON={py}")
    print(f"WFT_HOME={HERE}")
    print("之后所有命令形如：  <WFT_PYTHON> -m wft <子命令>      （子命令清单：<WFT_PYTHON> -m wft --help）")
    print("下一步：阅读 SKILL.md（流程与红线）→ QUICKSTART.md（10 分钟演示）→ references/02-测试规范.md")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
