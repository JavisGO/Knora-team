"""验证 Playwright MCP 服务是否可用（最小 MCP 客户端，不依赖任何 AI 产品）。

用法：
  python -m wft mcp-check [--url 页面地址] [--state 登录态文件] [--browser chrome]

做什么：用 npx 启动 @playwright/mcp（headless + isolated），完成 MCP 握手，列出工具，
检查关键工具齐全；给了 --url 就带登录态打开该页面并报告落地地址与标题
（落在登录页说明登录态失效）。
需要：Node.js（npx）与网络（首次会下载 @playwright/mcp）。
"""
import argparse
import json
import os
import queue
import subprocess
import sys
import threading

KEY_TOOLS = ["browser_navigate", "browser_snapshot", "browser_click", "browser_hover", "browser_type",
             "browser_file_upload", "browser_network_requests", "browser_take_screenshot", "browser_wait_for"]


class MCP:
    def __init__(self, cmd, cwd):
        self.p = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
        self.q, self.n = queue.Queue(), 0
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=lambda: [None for _ in self.p.stderr], daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            line = line.strip()
            if line:
                try:
                    self.q.put(json.loads(line))
                except ValueError:
                    pass

    def call(self, method, params=None, timeout=120):
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": method}
        if params is not None:
            msg["params"] = params
        self.p.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.p.stdin.flush()
        while True:
            m = self.q.get(timeout=timeout)
            if m.get("id") == self.n:
                return m

    def notify(self, method):
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.p.stdin.flush()

    def tool(self, name, args=None, timeout=120):
        r = self.call("tools/call", {"name": name, "arguments": args or {}}, timeout)
        if "error" in r:
            return True, str(r["error"])
        res = r["result"]
        text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        return bool(res.get("isError")), text

    def close(self):
        try:
            self.p.stdin.close()
            self.p.terminate()
        except Exception:  # noqa: BLE001
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url")
    ap.add_argument("--state", help="登录态文件（wft login 生成）")
    ap.add_argument("--browser", default="chrome")
    ap.add_argument("--version", default="latest", help="@playwright/mcp 的版本，默认 latest")
    args = ap.parse_args()

    npx = "npx.cmd" if os.name == "nt" else "npx"
    cmd = [npx, "-y", f"@playwright/mcp@{args.version}", "--headless", "--isolated", "--browser", args.browser,
           "--output-dir", os.path.join(os.getcwd(), ".mcp-out")]
    if args.state:
        cmd += ["--storage-state", args.state]
    try:
        m = MCP(cmd, cwd=os.getcwd())
    except FileNotFoundError:
        print("[FAIL] 找不到 npx：请先安装 Node.js")
        return 1
    fail = 0
    try:
        r = m.call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                  "clientInfo": {"name": "wft-mcp-check", "version": "1"}}, timeout=180)
        info = r["result"]["serverInfo"]
        print(f"[OK]   服务启动：{info['name']} {info['version']}（协议 {r['result']['protocolVersion']}）")
        m.notify("notifications/initialized")
        tools = {t["name"] for t in m.call("tools/list")["result"]["tools"]}
        print(f"[OK]   工具 {len(tools)} 个")
        missing = [t for t in KEY_TOOLS if t not in tools]
        if missing:
            fail = 1
            print("[FAIL] 缺少关键工具：" + ", ".join(missing) + "（版本差异，请对照该版本的工具清单调整用法）")
        else:
            print("[OK]   关键工具齐全")
        if args.url:
            err, text = m.tool("browser_navigate", {"url": args.url})
            if err:
                fail = 1
                print("[FAIL] 打开页面失败：" + text[:200].replace("\n", " "))
            else:
                # 单页应用可能先落在目标地址、随后才跳登录页：等几秒再读最终地址
                m.tool("browser_wait_for", {"time": 4})
                err, text = m.tool("browser_snapshot")
                url = next((l.split(": ", 1)[1] for l in text.splitlines() if l.startswith("- Page URL:")), "?")
                title = next((l.split(": ", 1)[1] for l in text.splitlines() if l.startswith("- Page Title:")), "?")
                print(f"[OK]   已打开：{url}（标题：{title}）")
                if "login" in url.lower():
                    fail = 1
                    print("[FAIL] 落在了登录页：登录态失效或未加载，请重新 wft login")
    except Exception as e:  # noqa: BLE001
        fail = 1
        print(f"[FAIL] {type(e).__name__}: {e}")
    finally:
        m.close()
    print("MCP 可用" if not fail else "MCP 检查未通过")
    return fail


if __name__ == "__main__":
    sys.exit(main())
