"""浏览器启动与上下文的公共封装。"""
import os


def default_state_path(account: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in account)
    return os.path.join(os.path.expanduser("~"), ".web-feature-test", f"state-{safe}.json")


def launch(p, channel: str = "chrome", headless: bool = True):
    """channel=chrome/msedge 用本机已装浏览器（无需下载）；chromium 用 Playwright 自带的。"""
    kwargs = {"headless": headless}
    if channel and channel != "chromium":
        kwargs["channel"] = channel
    return p.chromium.launch(**kwargs)


def new_context(browser, state: str = None, width: int = 1600, height: int = 1000, trace: bool = False):
    kwargs = {"viewport": {"width": width, "height": height}}
    if state:
        kwargs["storage_state"] = state
    ctx = browser.new_context(**kwargs)
    if trace:
        ctx.tracing.start(screenshots=True, snapshots=True)
    return ctx
