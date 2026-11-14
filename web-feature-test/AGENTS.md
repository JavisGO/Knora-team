# AGENTS.md —— web-feature-test

给任何 AI 编码/测试 agent 的入口说明。完整流程见 `SKILL.md`；本文件只列必须知道的几条。

## 你是在做什么
测试一个网页功能并交付带截图的测试报告。工具是本目录的 `wft`（Playwright + Python 命令行），用例是 JSON 文件。你负责：拆需求、写用例、执行、看结果、判定、写缺陷与结论。程序负责：执行、截图、抓接口、冒烟门禁、数据创建护栏、报告核对。

## 先做
1. 读 `SKILL.md`，再读 `references/04-用例DSL与wft命令参考.md` 和 `references/02-测试规范.md`。
2. 向使用者确认：被测对象、地址、账号、需求原文、范围边界。**口令不要让使用者写进聊天或文件**，让他在终端里 `export TEST_PASSWORD=…` 并自己运行 `python -m wft login`，你只使用登录态文件。
3. 环境：`python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python -m wft doctor`。

## 常用命令
```bash
python -m wft doctor --url <地址> --out <目录>
python -m wft pack good|anomalies --spec <规格.json> --out <数据包目录>
python -m wft run <spec.json> --out <目录> --state <登录态> --data-dir <数据包目录> --prefix R1_ [--allow-create] [--only TC-01]
python -m wft report <results.json>
python -m wft check <测试报告.md>
python -m wft deliver --report <报告.md> --src <工作目录> --out <交付目录>
python -m wft pdf <交付目录>/测试报告.md     # 可选：PDF
```

## 需要现场探索页面时
配 Playwright MCP（`references/08-PlaywrightMCP接入.md`），先 `python -m wft mcp-check` 自检；探索结果固化成 `spec.json` 再用 `wft run` 回归。

## 红线
- 不改、不删、不重跑他人或已有的数据与配置；新建数据名称带本轮前缀。
- 没测到的不写通过；需求写明禁止的行为以需求为准；环境干扰标“待复核”。
- 每个测试点要有截图并嵌入报告。
- 不在任何文件、命令行参数、报告里出现口令。
- 冒烟失败最多再试 2 次；`wft run` 报“产生了非预期的数据”要立刻停下告诉使用者。
