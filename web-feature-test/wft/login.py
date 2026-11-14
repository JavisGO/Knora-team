"""登录一次并保存登录态（Playwright storageState）。

用法：
  python -m wft login --url <被测页面> --account <账号> [--state 文件] [--headed]
口令来源（任选其一，绝不从命令行参数读取）：
  1) 环境变量 TEST_PASSWORD
  2) 交互输入（终端里输入时不回显）

登录态文件等同登录凭据：默认保存到 ~/.web-feature-test/，权限 600；不要提交仓库，不要放进交付目录。
遇到验证码/MFA/单点登录：加 --headed，在弹出的浏览器里手动完成一次，脚本检测到离开登录页后自动保存。
"""
import argparse
import getpass
import os
import re
import stat
import sys

from .browser import launch, new_context, default_state_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("TEST_URL"), required=not os.environ.get("TEST_URL"))
    ap.add_argument("--account", default=os.environ.get("TEST_ACCOUNT"))
    ap.add_argument("--state", help="登录态保存路径")
    ap.add_argument("--user-sel", default="#username", help="用户名输入框选择器")
    ap.add_argument("--pass-sel", default="#password", help="密码输入框选择器")
    ap.add_argument("--submit-text", default=r"登\s*录", help="登录按钮文字（正则）")
    ap.add_argument("--headed", action="store_true", help="有头模式，供人工完成验证码/MFA/单点登录")
    ap.add_argument("--channel", default=os.environ.get("WFT_CHANNEL", "chrome"))
    ap.add_argument("--login-url-keyword", default="login", help="登录页地址里的关键词，用于判断是否已离开登录页")
    args = ap.parse_args()

    if not args.account and not args.headed:
        sys.exit("需要 --account（或环境变量 TEST_ACCOUNT）；人工登录时可只加 --headed")
    state = args.state or default_state_path(args.account or "manual")
    os.makedirs(os.path.dirname(state), exist_ok=True)

    password = os.environ.get("TEST_PASSWORD")
    if not args.headed and not password:
        password = getpass.getpass(f"账号 {args.account} 的密码（输入不回显）：")

    from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

    with sync_playwright() as p:
        browser = launch(p, channel=args.channel, headless=not args.headed)
        ctx = new_context(browser)
        page = ctx.new_page()
        page.goto(args.url, wait_until="domcontentloaded", timeout=45000)

        # 单页应用常先加载目标页、再跳登录页：先等登录框出现，避免抢跑误判“已登录”
        on_login = False
        try:
            page.locator(args.user_sel).wait_for(timeout=10000)
            on_login = True
        except PWTimeout:
            pass
        if on_login and not args.headed:
            page.fill(args.user_sel, args.account)
            page.fill(args.pass_sel, password)
            page.get_by_role("button", name=re.compile(args.submit_text)).first.click()
        elif on_login:
            print("请在弹出的浏览器里完成登录（含验证码/MFA）……")

        kw = args.login_url_keyword
        page.wait_for_function(
            "([kw, sel]) => !location.href.includes(kw) && !document.querySelector(sel)",
            arg=[kw, args.user_sel],
            timeout=180000 if args.headed else 60000,
        )
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            pass
        if kw in page.url:
            sys.exit("仍停留在登录页，账号口令可能不对")
        ctx.storage_state(path=state)
        try:
            os.chmod(state, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass  # Windows 上忽略
        print(f"登录成功，登录态已保存：{state}")
        print(f"当前地址：{page.url}")
        browser.close()


if __name__ == "__main__":
    main()
