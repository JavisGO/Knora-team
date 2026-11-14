---
name: web-feature-test
description: 网页功能的自动化测试与验收流程（Playwright + Python 命令行 wft）：把需求拆成用例、写成可重复执行的 JSON 用例、构造正常/异常测试数据包、自动截图与抓接口取证、核对报告并整理交付。当需要测试某个页面或功能、做验收、出带截图的测试报告、回归或补测时使用。
---

# web-feature-test：网页功能测试与验收

把“测一个功能”做成固定流程：**接单确认 → 需求拆解 → 预检登录冒烟 → 造数 → 写用例并执行 → 判定成文 → 核对交付 → 补测**。

核心思路：**用例写成 JSON，由 `wft`（Playwright）确定性地执行、截图、抓接口、判定**；人或 AI agent 负责设计用例、判定业务含义、写缺陷与结论。流程不依赖某一个 AI 产品，纯人工 + 命令行也能完整走通。

本 skill 不保存任何环境地址、账号、口令，每次测试由使用者临时提供。

## 开始之前先问清（缺哪项问哪项，不要自己猜）

填写 `templates/测试需求输入单.md`，或让需求方口述：
1. **被测对象**：名称与入口路径（需求方指定的就是它，不得自行更换）。
2. **环境与账号**：地址、账号；口令由使用者自己在终端输入（`export TEST_PASSWORD=…` 或交互输入），不写进任何文件、命令参数或报告。环境里是否还有别人/别的自动化在用同一账号。
3. **需求原文**：完整粘贴，不删改。
4. **范围与边界**：必测项、不测项、能否改共享配置（默认不能）、**怎么造出一条会失败的数据**。
5. **交付要求**：默认每个对象一份报告、每个测试点带截图并嵌入报告、只保留自测内容。

> 想先体验一遍：看 `QUICKSTART.md`（自带本地演示站点，不需要账号）。

## 工具与安装

```bash
cd web-feature-test
python3 -m venv .venv && . .venv/bin/activate        # Windows: py -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m wft doctor --url <被测地址> --out ./测试输出   # 预检
```

默认使用本机 Chrome（没有就 `--channel msedge`，或 `python -m playwright install chromium` 后 `--channel chromium`）。命令清单：`python -m wft --help`，完整参考见 `references/04-用例DSL与wft命令参考.md`。

## 流程（详见 references/01-流程与分工.md）

1. **拆解**：需求逐条 → 用例，写出追溯表；对照 `references/06-通用用例维度清单.md` 补盲区；可直接套 `cases/批量异步任务类功能用例库.md`；用 `python -m wft init` 建本轮目录与约定（任务前缀、截图前缀）。
2. **登录与冒烟**：`python -m wft login …` 登录一次保存登录态；跑标了 `"smoke": true` 的用例。冒烟失败 `wft run` 会自动停止后续用例；**最多再试 2 次**，仍失败就写“主链路阻塞”。
3. **造数**：`python -m wft pack good|anomalies --spec <规格.json>` 生成正常包与 14 类异常包（manifest 标注期望结果）。
4. **写用例并执行**：照 `specs/batch-task.example.spec.json` 写 `spec.json`，`python -m wft run spec.json --out out --state <登录态> --data-dir <数据包>`。会新建数据的用例标 `creates:true`，需加 `--allow-create`。
5. **判定成文**：看 `out/results.json`、截图和 trace；“未测（待人工判定）”的项看图定论；`python -m wft report` 生成明细表；写缺陷清单、未覆盖项、结论（`templates/测试报告模板.md`）。
6. **核对交付**：`python -m wft check <报告>` ERROR 清零；人工抽查关键截图；`python -m wft deliver` 只拷“报告引用的截图 + 测试数据”；需要 PDF 时 `python -m wft pdf <报告.md>`；按 `references/03-验收标准.md` 过清单并汇报。
7. **补测**：缺陷修复/环境恢复后新开一轮（`wft init --round N`，截图前缀 `R{N}_`），从冒烟重新开始。

## 必须遵守（违反即视为测试无效）

- 只新建、运行本轮自己的数据，名称带本轮前缀；**不修改、删除、重跑他人或已有的配置与数据**；他人产物不当作证据。
- **没测到的不写通过**；环境干扰造成的异常标“待复核”，不直接判产品缺陷。
- **需求写了明确禁止/要求的行为，以需求为准**（如“不静默替换数据”，被静默修正就是失败）。
- “找不到入口”先看现场截图和 trace，排除页面没加载完/悬停才出现/弹层遮挡，再下结论。
- 每个测试点（含失败、阻塞、各类报错）都要有截图，并用 Markdown 图片语法嵌入报告；确实不能截图写“无截图：原因”。
- 报告、脚本、提示词、命令行参数里不出现口令；登录态文件等同凭据，不进仓库、不进交付目录。
- 校验类用例不应创建数据；`wft run` 检测到非预期的数据创建会判失败并停止，此时先清理再继续。
- 冒烟失败不堆重试；需求方说“已修复”后从冒烟重新验证。
- 并行：每次 `wft run` 是独立浏览器上下文，可并行；但共用同一个手动操作的浏览器不能并行（平台不支持同一浏览器同时登录）。

## 文件地图

| 路径 | 用途 |
|---|---|
| `references/01-流程与分工.md` | 阶段、分工、并行/串行、三种执行方式、核对与交付 |
| `references/02-测试规范.md` | 命名、结果判定口径、缺陷等级、证据要求、禁止项 |
| `references/03-验收标准.md` | 功能验收结论取值；测试交付验收清单；汇报格式 |
| `references/04-用例DSL与wft命令参考.md` | 安装、全部子命令、用例 JSON 语法、UI 框架常见现象 |
| `references/05-踩坑与应对.md` | 真实测试沉淀的经验与自动化自身的坑 |
| `references/06-通用用例维度清单.md` | 防盲区的 11 个维度 |
| `references/07-为什么选Playwright.md` | 选型记录与真实环境试跑结果 |
| `references/08-PlaywrightMCP接入.md` | 可选：让 AI agent 通过 MCP 现场探索页面（含验证状态） |
| `cases/批量异步任务类功能用例库.md` | 可直接改用的用例库 |
| `specs/batch-task.example.spec.json` | 可执行的示例用例集（已在真实环境验证） |
| `templates/` | 需求输入单、测试计划、用例明细、报告、执行者提示词 |
| `config/pack-spec*.example.json` | 数据包规格示例 |
| `wft/` | 命令行源码（doctor、login、run、pack、init、report、check、deliver） |
| `AGENTS.md` | 给 AI agent 的简要入口（不支持 SKILL.md 的 agent 读这个） |

## 汇报格式

结论先行（通过/有条件通过/不通过/无法验收 + 最严重问题）→ 计数表 → 缺陷清单 → 未测项与原因 → 关键限制 → 本轮创建的数据清单 → 下一步。数字以明细为准。
