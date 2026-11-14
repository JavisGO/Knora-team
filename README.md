# Knora-team

团队共享的工具与规范。

## 目录

| 目录 | 说明 |
|---|---|
| [`web-feature-test/`](web-feature-test/) | 网页功能自动化测试与验收流程（Playwright + Python 命令行 `wft`）。**不绑定任何 AI 产品**，纯人工 + 命令行即可完整使用；也可交给任意能执行命令的 AI agent 驱动。自带本地演示站点，不需要账号，10 分钟可以跑通一遍。→ **[Quickstart](web-feature-test/QUICKSTART.md)** |

---

## 让你的 AI Agent 一句话学会 `web-feature-test`

把下面这段话**整段粘贴给你的 AI Agent**（Claude Code、Codex、Cursor，或任何能在终端执行命令的 Agent）：

```text
请帮我安装并学会「web-feature-test」网页功能测试 skill。

1. 阅读这份安装说明，并严格按里面的步骤执行：
   https://raw.githubusercontent.com/JavisGO/Knora-team/main/INSTALL.md
   （打不开的话改用：https://github.com/JavisGO/Knora-team/blob/main/INSTALL.md）
2. 过程中：不要向我索要任何账号口令；不要执行与安装无关的命令；需要我决定的事先问我。
3. 装好后，用不超过 5 句话告诉我：它能做什么、我要测一个功能时需要给你哪些信息、怎么先体验一遍。
```

Agent 会做的事：检查 Python 和浏览器 → 下载本仓库 → 运行 `install.py`（建环境、装依赖、**启动本地演示站点并用浏览器真的点一遍作为自检**）→ 读 `SKILL.md`、`QUICKSTART.md` 学会用法 → 用几句话告诉你结果。

**需要你自己做的事只有一件：登录口令只在你自己的终端里输入**（Agent 会把命令给你），不要贴给 Agent。

### 变体

- **想让 Agent 装进它的 skills 目录**（你知道目录在哪时）：在第 1 条后面加一句：“安装时用 `--skills-dir <你的 skills 目录>`”。例如 Claude Code 的用户级目录是 `~/.claude/skills`。不确定目录就别加，Agent 会装在当前目录并告诉你位置。
- **Agent 访问不了 GitHub**：自己在浏览器里打开仓库 → Code → Download ZIP，解压后对 Agent 说：“请阅读 `<解压路径>/INSTALL.md` 并按它的步骤安装，代码已经在本地，跳过下载。”
- **自己动手，不用 Agent**：直接看 [`web-feature-test/QUICKSTART.md`](web-feature-test/QUICKSTART.md)，或在 `web-feature-test/` 目录下执行 `python3 install.py`。

### 常见问题

- **装好后怎么让 Agent 去测试？** 直接说：“用 web-feature-test 测试 XX 功能”，并告诉它被测对象在哪、环境地址、账号、需求原文。缺什么它会问你。
- **Agent 说自检失败 / 浏览器启动不了？** 多半是机器上没有 Chrome/Edge，或沙箱限制了启动浏览器、开本地端口。`INSTALL.md` 的“故障处理”一节有对应办法，Agent 会按它处理。
- **仓库是公开的，里面有敏感信息吗？** 没有账号、口令和内网地址；登录态文件默认保存在你本机 `~/.web-feature-test/`，并已写进 `.gitignore`。
