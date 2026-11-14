# web-feature-test 使用说明（给测试同事）

> **第一次用？先看 [QUICKSTART.md](QUICKSTART.md)**：10 分钟用自带的本地演示站点把整套流程走一遍，不需要任何账号。

一套网页功能的自动化测试与验收流程：拆需求 → 写用例（JSON）→ 用 Playwright 自动执行、截图、抓接口 → 核对报告 → 整理交付。

- **不绑定任何 AI 产品**：核心是一个 Python 命令行 `wft`。你可以纯手工用它，也可以让任意能执行命令的 AI agent 来驱动。
- **不含任何环境地址、账号、口令**，每次测试时由你自己提供。
- 跨平台：macOS / Linux / Windows（只依赖 Python 和一个浏览器）。

## 1. 安装（一次性）

需要：Python 3.9+，以及本机已安装的 Chrome（或 Edge）。

**一条命令搞定**（建虚拟环境、装依赖、预检、浏览器自检）：`cd web-feature-test && python3 install.py`（Windows：`py install.py`）。想装进某个 AI agent 的 skills 目录，加 `--skills-dir <目录>`。下面是手动方式：

```bash
cd web-feature-test
python3 -m venv .venv
. .venv/bin/activate            # Windows：py -m venv .venv  然后  .venv\Scripts\activate
pip install -r requirements.txt
python -m wft doctor --url <被测地址> --out ./测试输出
```

`doctor` 全部 OK 就可以开始。没有 Chrome：`--channel msedge`，或 `python -m playwright install chromium` 后加 `--channel chromium`（也可设环境变量 `WFT_CHANNEL`）。

## 2. 跑一遍（15 分钟上手）

```bash
# ① 登录一次，保存登录态（口令走环境变量或交互输入，不会出现在命令行里）
export TEST_PASSWORD='你的口令'                       # Windows PowerShell：$env:TEST_PASSWORD='你的口令'
python -m wft login --url <被测页面地址> --account <账号> --state ./state.json
#   有验证码/MFA/单点登录：加 --headed，在弹出的浏览器里人工登录一次

# ② 造数据包：复制并修改 config/pack-spec.example.json（表头、必填列、附件列），然后
python -m wft pack good      --spec my-pack.json --out ./packs --name good_1 --rows 1
python -m wft pack anomalies --spec my-pack.json --out ./packs        # 14 类异常包 + manifest.json

# ③ 复制 specs/batch-task.example.spec.json 改成你的功能，然后执行
export TEST_URL='<入口页面地址>' TEST_OBJECT='<被测对象名称>'
python -m wft run my.spec.json --out ./out --state ./state.json --data-dir ./packs --prefix R1_
#   会新建数据的用例（creates:true）需要再加 --allow-create

# ④ 看结果：out/results.json、out/screenshots/、out/用例明细.generated.md；失败用例有“现场”截图
python -m playwright show-trace out/trace.zip              # 回放每一步

# ⑤ 写报告（templates/测试报告模板.md），核对并交付
python -m wft check 测试报告.md
python -m wft deliver --report 测试报告.md --src . --out ./交付/<对象名>
python -m wft pdf ./交付/<对象名>/测试报告.md                  # 可选：生成 PDF（图片内嵌）
```

示例用例集 `specs/batch-task.example.spec.json` 已在真实系统上跑通：入口、列表字段、必填、非 ZIP 拦截、6 类上传校验、4 个轮次边界、1 条创建并跑完的冒烟。

## 3. 让 AI agent 来驱动（可选）

把整个目录交给 agent，让它读 `SKILL.md`（或 `AGENTS.md`），它会按流程问你被测对象、环境、需求原文，然后写用例、执行、看截图、写报告。

| agent 类型 | 怎么接入 |
|---|---|
| 支持 `SKILL.md` 技能目录的（如 Claude Code） | 把 `web-feature-test` 目录放进该工具的 skills 目录（例如 `~/.claude/skills/`；其他工具的目录以其文档为准） |
| 读取 `AGENTS.md` 的 agent | 在该目录下启动 agent，它会读到 `AGENTS.md`；再让它去读 `SKILL.md` |
| 其他 agent / 聊天窗口 | 把 `AGENTS.md` 和 `SKILL.md` 的内容发给它；它只需要能在终端执行命令、读写文件 |
| 需要 agent 现场驱动浏览器探索新页面 | 配 Playwright MCP 服务，见 `references/08-PlaywrightMCP接入.md`；先 `python -m wft mcp-check` 自检；探索出的步骤固化成 JSON 后就不再依赖 agent。**已在本地页面和真实业务页面（校验链路）验证** |

要把一个对象的一轮测试交给 agent 的子任务/子智能体，用 `templates/执行者提示词模板.md`。

**口令只由你在终端里输入**（`TEST_PASSWORD` 或交互输入）。不要把口令贴进和 agent 的对话里，让它只使用你登录好的登录态文件。

## 4. 你需要知道的几条规矩

1. **被测对象由需求方指定**，执行者不会自己换。
2. **默认不修改共享配置、不碰别人的数据**；要改配置才能验证的项标“未测”。
3. **新建的数据名称都带前缀**（`wft init` 会给出本轮前缀）；创建类用例必须显式加 `--allow-create`；校验类用例若意外创建了数据，程序会判失败并停止。
4. **冒烟用例失败，后面的用例不再执行**，不会堆重试。
5. **没测到的不会写成通过**；环境干扰标“待复核”。
6. **每个测试点都有截图**，并嵌入报告；`wft check` 会核对图片是否存在、汇总与明细是否一致、缺陷是否带截图、结论是否与结果一致。
7. 平台通常不支持同一个浏览器里同时登录；`wft run` 每次是独立浏览器上下文，可以并行，但大家共用同一个手动浏览器就只能串行。
8. 登录态文件等同登录凭据：默认保存在 `~/.web-feature-test/`，权限 600，别提交仓库、别放进交付目录。

## 5. 目录

```
web-feature-test/
├── QUICKSTART.md                      10 分钟上手（含本地演示站点）
├── SKILL.md  AGENTS.md  README.md     入口与说明
├── wft/                               命令行源码（Python）
├── requirements.txt  pyproject.toml   依赖
├── examples/demo-site/                本地演示站点 + 演示用例（不需要账号，可直接体验）
├── specs/                             可执行的示例用例集（JSON）
├── config/                            数据包规格示例
├── cases/                             用例库
├── templates/                         需求输入单、计划、明细、报告、执行者提示词
└── references/                        流程、规范、验收标准、命令参考、踩坑、维度清单、选型记录
```

## 6. 适配你们的功能

- 数据包规格：复制 `config/pack-spec.example.json`，改表头、必填列、附件列、允许的扩展名。
- 用例：复制 `specs/batch-task.example.spec.json`，改 `vars` 里的文案和 `cases` 里的步骤；语法见 `references/04-用例DSL与wft命令参考.md`。
- 用例库：`cases/批量异步任务类功能用例库.md` 按你们的功能名词调整。
- 要回归：把验证过的 spec 放进 CI 或计划任务，`python -m wft run … --priority P0`，退出码非 0 就通知。

## 7. 反馈与沉淀

踩到新的坑补到 `references/05-踩坑与应对.md`；新的判定偏差补到 `references/02-测试规范.md`；新的用例补到 `cases/`。
