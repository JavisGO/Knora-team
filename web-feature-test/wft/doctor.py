"""环境预检。用法：python -m wft doctor [--url 被测地址] [--out 输出目录]
任一 FAIL 返回非 0。不读取、不打印任何账号口令。"""
import argparse
import os
import shutil
import sys
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="被测地址（可选，给了就检查连通性）")
    ap.add_argument("--out", default=".", help="输出目录（检查可写）")
    ap.add_argument("--channel", default=os.environ.get("WFT_CHANNEL", "chrome"), help="浏览器通道：chrome / msedge / chromium")
    args = ap.parse_args()
    fail = 0

    def ok(m):
        print("[OK]  ", m)

    def bad(m):
        nonlocal fail
        fail = 1
        print("[FAIL]", m)

    def warn(m):
        print("[WARN]", m)

    if sys.version_info >= (3, 9):
        ok(f"Python {sys.version.split()[0]}")
    else:
        bad("需要 Python 3.9+")

    for mod, pipname in (("playwright", "playwright"), ("openpyxl", "openpyxl")):
        try:
            __import__(mod)
            ok(f"{mod} 已安装")
        except ImportError:
            bad(f"缺少 {mod}：pip install {pipname}")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            try:
                b = p.chromium.launch(channel=None if args.channel == "chromium" else args.channel, headless=True)
                ok(f"浏览器可启动（通道 {args.channel}，版本 {b.version}）")
                b.close()
            except Exception as e:  # noqa: BLE001
                bad(f"无法启动浏览器（通道 {args.channel}）：{str(e).splitlines()[0]}。"
                    f"装了 Chrome 就用 --channel chrome；没有就执行 python -m playwright install chromium 后用 --channel chromium")
    except ImportError:
        pass

    if args.url:
        try:
            req = urllib.request.Request(args.url, method="GET")
            with urllib.request.urlopen(req, timeout=8) as r:
                ok(f"被测地址可达 HTTP {r.status}")
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            if code and code < 500:
                ok(f"被测地址可达 HTTP {code}")
            else:
                bad(f"被测地址不可达（{type(e).__name__}）：检查 VPN / 内网 / 地址")

    try:
        os.makedirs(args.out, exist_ok=True)
        probe = os.path.join(args.out, ".wft_write_probe")
        open(probe, "w").close()
        os.remove(probe)
        ok(f"输出目录可写：{args.out}")
    except OSError:
        bad(f"输出目录不可写：{args.out}")

    if not shutil.which("python3") and not shutil.which("python"):
        warn("PATH 中找不到 python/python3，仅影响直接调用脚本，不影响 python -m wft")

    warn("平台通常不支持同一浏览器同时登录：每次 wft run 是独立浏览器上下文，可并行；共用同一个手动操作的浏览器则只能串行（见 references/01）")
    print("预检通过" if not fail else "预检未通过，请先处理 [FAIL] 项")
    return fail


if __name__ == "__main__":
    sys.exit(main())
