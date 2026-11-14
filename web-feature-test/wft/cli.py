"""统一入口：python -m wft <子命令> ...

子命令
  doctor    环境预检（Python 依赖、浏览器、被测地址、输出目录）
  login     登录一次并保存登录态（口令只从环境变量/交互输入读取）
  run       执行声明式用例（JSON），产出 results.json、截图、trace、用例明细
  pack      生成正常/异常测试数据包（Excel + 附件目录的 ZIP）
  init      初始化一轮测试的目录与约定
  check     交付前核对测试报告（图片、章节、计数、缺陷截图、结论一致性）
  deliver   整理交付目录（只拷报告引用的截图和测试数据）
  report    把 results.json 渲染成报告里的“用例明细”表
  pdf       把 Markdown 报告渲染成 PDF（图片内嵌）
  mcp-check 验证 Playwright MCP 服务是否可用（可选，给 AI agent 现场探索页面用）
"""
import sys

COMMANDS = {
    "doctor": ("doctor", "main"),
    "login": ("login", "main"),
    "run": ("runner", "main"),
    "pack": ("packs", "main"),
    "init": ("initrun", "main"),
    "check": ("check", "main"),
    "deliver": ("deliver", "main"),
    "report": ("report", "main"),
    "pdf": ("pdf", "main"),
    "mcp-check": ("mcpcheck", "main"),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"未知子命令: {cmd}\n")
        print(__doc__)
        sys.exit(2)
    mod_name, fn = COMMANDS[cmd]
    import importlib

    mod = importlib.import_module(f"wft.{mod_name}")
    sys.argv = [f"wft {cmd}"] + sys.argv[2:]
    result = getattr(mod, fn)()
    if isinstance(result, int):
        sys.exit(result)
