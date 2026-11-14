# INSTALL（写给 AI Agent 看的）

你读到这份文档，是因为用户希望你**安装并学会 `web-feature-test`**：一套用 Playwright 自动测试网页功能、并交付带截图测试报告的工具和流程。请按顺序执行，每一步成功再进入下一步。**不要向用户索要任何账号或口令，不要执行与安装无关的命令；遇到需要用户决定的事先问用户。**

## 0. 它是什么（先有个概念）

- 核心是命令行 `wft`（Python + Playwright）：把测试用例写成 JSON，由程序执行、截图、抓接口、判定。
- 配套有流程、规范、模板、验收标准，以及一个**本地演示站点**（不需要任何账号即可完整体验）。
- 不绑定任何 AI 产品。你的角色：拆需求、写用例、执行、看结果、判定、写缺陷与结论；用户的角色：指定被测对象、提供环境与需求、自己在终端输入口令。

## 1. 先检查环境

```bash
python3 --version        # Windows：py --version，需要 3.9 或更高
git --version            # 没有 git 也可以，见第 2 步的备选
```

- 本机需要有 **Chrome 或 Edge**（没有也行，第 3 步有备选）。
- 需要能访问 GitHub 和 pip 源。

## 2. 获取代码

在用户指定的目录（没指定就用当前目录）执行：

```bash
git clone https://github.com/JavisGO/Knora-team.git
cd Knora-team/web-feature-test
```

如果 `git clone` 连不上或没有 git，用压缩包：

```bash
# macOS / Linux
curl -L -o Knora-team.zip https://github.com/JavisGO/Knora-team/archive/refs/heads/main.zip && unzip -q Knora-team.zip
cd Knora-team-main/web-feature-test
# Windows PowerShell：Invoke-WebRequest https://github.com/JavisGO/Knora-team/archive/refs/heads/main.zip -OutFile Knora-team.zip; Expand-Archive Knora-team.zip .; cd Knora-team-main\web-feature-test
```

两种都不行：告诉用户“这台机器访问不了 GitHub”，请用户手动下载并解压，把路径告诉你，然后从第 3 步继续。

## 3. 安装并自检

```bash
python3 install.py            # Windows：py install.py
```

它会：建 `.venv`、装依赖、检查浏览器能否启动、**启动本地演示站点并用浏览器真的点一遍**（自检）。成功的标志是末尾输出 `安装完成`，并打印两行：

```
WFT_PYTHON=<解释器路径>
WFT_HOME=<安装目录>
```

**记下这两个值**。之后所有命令都用 `<WFT_PYTHON> -m wft <子命令>`（比如 `<WFT_PYTHON> -m wft --help`）。

可选参数：
- `--skills-dir <目录>`：把本目录复制到你所在 AI 工具的 skills 目录（会生成 `<目录>/web-feature-test`）。**只有在你明确知道自己的 skills 目录在哪时才传**；不确定就不要猜，装完后告诉用户即可。
- `--channel msedge`：用 Edge；`--no-selftest`：跳过自检；`--no-venv`：装进当前 Python 环境。

## 4. 学会怎么用（按顺序读，不必一次读完）

1. `SKILL.md`：流程、必须遵守的红线、文件地图。**这是主文档。**
2. `QUICKSTART.md`：10 分钟用演示站点走一遍的步骤。
3. `references/02-测试规范.md`：命名、结果判定口径、缺陷等级、证据要求。
4. 真正写用例时再读 `references/04-用例DSL与wft命令参考.md`（用例 JSON 的语法）和 `references/06-通用用例维度清单.md`（防漏测）。

## 5. 装好后向用户汇报（不超过 5 句话）

用你自己的话说清楚这几件事，不要贴文档原文：
1. 装好了，自检通过（或哪一步没通过、卡在哪）。
2. 它能做什么：把网页功能的测试变成可重复执行的用例，自动截图、抓接口，最后核对并交付带截图的报告。
3. 用户要测一个功能时，需要给你：**被测对象在哪（入口路径）、环境地址、账号、需求原文、不能碰什么、能否造失败数据**；口令不要贴给你。
4. 想先体验：说一声，你按 `QUICKSTART.md` 带用户用演示站点跑一遍。
5. 如果没传 `--skills-dir`：告诉用户你已装在 `<WFT_HOME>`，之后让你“用 web-feature-test 测试 XX”时你会去读这个目录。

## 6. 之后用户让你测试某个功能时

- 先按 `SKILL.md` 的“开始之前先问清”问齐信息，**缺哪项问哪项，不要自己猜**。
- **口令**：让用户在**他自己的终端**里执行（你把命令给他）：
  ```bash
  export TEST_PASSWORD='口令'                  # Windows PowerShell：$env:TEST_PASSWORD='口令'
  <WFT_PYTHON> -m wft login --url <被测页面> --account <账号> --state <登录态文件>
  ```
  你之后只使用登录态文件。登录态文件等同凭据：不要读出内容、不要提交仓库、不要放进交付件。
- 红线（完整版见 `SKILL.md`）：
  1. 只新建、运行本轮自己的数据，名称带本轮前缀；**不改、不删、不重跑他人或已有的配置与数据**。
  2. **没测到的不写“通过”**；环境干扰标“待复核”，不直接判产品缺陷。
  3. 需求写明禁止的行为以需求为准（如“不得静默替换数据”）。
  4. 每个测试点都要有截图并嵌进报告；交付前跑 `wft check`，ERROR 清零。
  5. 冒烟失败最多再试 2 次，不堆重试；用户说“已修复”后从冒烟重新验证。
  6. 会新建数据的用例要显式加 `--allow-create`；程序报“产生了非预期的数据”要立刻停下告诉用户。

## 7. 故障处理

| 现象 | 处理 |
|---|---|
| `python3` 找不到 / 版本低于 3.9 | Windows 用 `py`；仍不行就告诉用户需要先安装 Python 3.9+ |
| 创建虚拟环境失败 | Linux 先 `apt install python3-venv`；或加 `--no-venv` |
| `pip install` 失败或很慢 | 让用户提供公司 pip 镜像并配置；不要换成来源不明的源 |
| 预检提示“无法启动浏览器” | 没有 Chrome/Edge：`<WFT_PYTHON> -m playwright install chromium`，然后 `python3 install.py --channel chromium`，之后所有 `wft` 命令也加 `--channel chromium`（或设环境变量 `WFT_CHANNEL=chromium`） |
| 自检失败，浏览器能启动但交互没通过 | 把自检输出原样告诉用户，不要自行改代码绕过；可先 `python3 install.py --no-selftest` 完成安装，再按 `QUICKSTART.md` 手动跑演示定位 |
| 在受限沙箱里不能启动浏览器或不能开本地端口 | 告诉用户需要放开浏览器启动与 127.0.0.1 端口访问，或换到可用的终端 |
