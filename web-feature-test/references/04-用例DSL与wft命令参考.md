# 04 用例 DSL 与 wft 命令参考

`wft` 是随 skill 一起提供的命令行（Python + Playwright）。**用例写成 JSON，由程序执行**，不依赖任何 AI agent：agent 或测试同事负责写用例、看结果；重复执行、截图、抓接口、判定都是确定性的程序行为。

## 1. 安装与自检

```bash
cd web-feature-test
python3 -m venv .venv && . .venv/bin/activate      # Windows：py -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m wft doctor --url <被测地址> --out ./测试输出
```

- 默认使用本机已装的 Chrome（`--channel chrome`）；用 Edge 加 `--channel msedge`；两者都没有就 `python -m playwright install chromium` 后用 `--channel chromium`。也可设环境变量 `WFT_CHANNEL`。
- 所有子命令：`python -m wft --help`。

## 2. 子命令

| 命令 | 作用 |
|---|---|
| `doctor` | 环境预检 |
| `login` | 登录一次，保存登录态（storageState）到 `~/.web-feature-test/`，权限 600 |
| `run` | 执行用例 JSON，产出 `results.json`、截图、`trace.zip`、`用例明细.generated.md` |
| `pack` | 生成正常/异常测试数据包（Excel + 附件目录的 ZIP） |
| `init` | 建本轮目录与约定（任务前缀、截图前缀），拷入报告模板 |
| `report` | 把 `results.json` 渲染成“用例明细”表 |
| `pdf` | 把 Markdown 报告渲染成 PDF（图片内嵌，给不看 Markdown 的同事） |
| `mcp-check` | 验证 Playwright MCP 服务可用（可选） |
| `check` | 交付前核对报告（图片、章节、计数、缺陷截图、结论一致性） |
| `deliver` | 整理交付目录，只含报告引用的截图与测试数据 |

### 登录

```bash
# 口令只来自环境变量或交互输入（不回显），不接受命令行参数
export TEST_PASSWORD='…'                       # Windows PowerShell：$env:TEST_PASSWORD='…'
python -m wft login --url <被测地址> --account <账号> --state ./state-a.json
# 有验证码 / MFA / 单点登录：弹出浏览器，人工完成一次，脚本检测到离开登录页后保存
python -m wft login --url <被测地址> --headed --state ./state-a.json
```

登录态文件等同凭据：不要提交仓库，不要放进交付目录，别人要用就让他自己登录一次。

### 运行

```bash
python -m wft run specs/my.spec.json --out ./out --state ./state-a.json \
    --data-dir ./packs --prefix R1_ [--var K=V] [--only TC-01,TC-02] [--priority P0,P1] \
    [--allow-create] [--headed] [--timeout 15000]
python -m wft run specs/my.spec.json --out ./out --list      # 只列用例
```

内置规则（写在代码里，不靠自觉）：
- 每个用例结束自动截图；失败/阻塞时再截一张“现场”图；全程录 trace（`python -m playwright show-trace out/trace.zip` 可回放每一步）。
- 标了 `"smoke": true` 的用例失败/阻塞 → 后面的用例不再执行，标“未测（冒烟未通过）”（`--no-smoke-gate` 可关闭）。
- 标了 `"creates": true` 的用例会在被测系统里新建数据，**必须加 `--allow-create` 才执行**。
- **数据创建护栏**：`watch` 里标了 `"mutating": true` 的接口，如果在没声明 `creates` 的用例里返回了成功，该用例判失败并**立即停止后续用例**（防止校验类用例误把数据建出来）。
- 断言失败 → 失败；动作异常（找不到元素/超时）→ 阻塞；没有任何断言 → “未测（待人工判定）”。
- 页面被带到登录页 → 立即停止并提示重新登录。
- 内网瞬断（`net::ERR_*`）自动重试 3 次。

退出码：全部通过/待判定/未测 → 0；有失败或阻塞 → 1。

## 3. 用例文件（JSON）

```jsonc
{
  "name": "说明",
  "vars":   { "URL": "${env:TEST_URL}", "OBJECT": "${env:TEST_OBJECT}", "BTN": "新建" },   // ${env:X} 读环境变量
  "watch":  [ { "name": "create", "url_re": "/tasks/create", "mutating": true, "success_body_contains": "\"statusCode\":200" } ],
  "macros": { "open_feature": [ /* 步骤… */ ] },           // 可复用步骤组
  "before": "open_feature",                                // 每个用例前先执行的宏（用例里可覆盖，null 表示不执行）
  "cases": [
    { "id": "TC-01", "title": "…", "priority": "P0", "requirement": "条款", "expect": "预期（会写进明细）",
      "smoke": true, "creates": false, "before": null, "steps": [ /* 步骤 */ ] },
    { "id": "TC-V", "title": "校验：${title}", "for_each": [ {"id":"TC-V1","title":"缺列","pack":"a.zip"}, … ],
      "steps": [ {"do":"upload","file":"${pack}"} ] }     // for_each：一个模板展开成多个用例，参数里必须有 id
  ]
}
```

变量：`${NAME}`（`vars` / `--var` / `read` 读到的值）、`${env:NAME}`（环境变量）；`--var` 覆盖 `vars`；自动提供环境变量 `WFT_RUN_ID`（时间戳，造唯一名称用）。**账号、口令、地址、对象名都不要写进用例文件**，用环境变量或 `--var` 传入。

### 目标（定位元素）

动作和断言里描述“操作哪个元素”的字段，可组合：

| 字段 | 含义 |
|---|---|
| `text` | 按文字（`exact` 默认 true；设 false 为包含） |
| `selector` / `has_text` | CSS/XPath；`has_text` 再按包含文字过滤 |
| `role` + `name`（`name_re:true` 时为正则） | 按 ARIA 角色，如 `button`、`textbox`、`spinbutton` |
| `placeholder` / `by_label` / `test_id` | 按占位符 / 表单标签 / data-testid |
| `after_text` (+`tag`) | 取某段文字之后的第一个输入控件；表单标签没有关联输入框时用 |
| `card` `{contains, has}` | 同时包含 A 和 B 的最近 div（列表里“某对象的卡片”） |
| `within` | 另一个目标，限定在其范围内 |
| `nth` / `last` | 取第几个 / 最后一个（默认第一个） |

注意：步骤里的 `label` 只是给人看的描述，不参与定位。

### 动作

| do | 参数 | 说明 |
|---|---|---|
| `goto` | `url` | 打开页面，等待网络空闲，检查是否被带到登录页 |
| `click` / `dblclick` / `hover` / `check` | 目标 | `after_ms` 点击后等待，默认 600 |
| `fill` | 目标, `value` | 设值（空串=清空） |
| `press` | `key`（可带目标） | 按键，如 `Tab`、`Enter` |
| `upload` | `file`, `selector`(默认 `input[type=file]`), `nth` | 原生上传，相对路径从 `--data-dir`/用例目录找 |
| `wait` | `ms` | 固定等待 |
| `wait_text` | `text`, `gone`, `regex`, `within`, `timeout_ms` | 等文字出现/消失 |
| `wait_response` | `watch` | 等某个被监听的接口响应 |
| `screenshot` | `name` | 额外截图（每个用例已自动截图） |
| `read` | 目标, `as`, `attr`(text/value/count/all_text/属性名) | 把值读进变量 |
| `read_table` | `selector`, `as` | 把表格行读成二维数组 |
| `sum_col` | `var`, `col`, `as` | 对某列求和（自动去千分位逗号） |
| `eval` | `js`, `as` | 在页面里执行只读 JS，结果存变量 |
| `note` | `text` | 记一条观察，写进“实际” |
| `manual` | `text` | 标记“需人工判定”，写明看什么 |
| `macro` | `name` | 执行宏 |

任意步骤可加 `"optional": true`（失败不阻塞）、`"timeout_ms"`、`"label"`。

### 断言（失败判“失败”，继续执行以收集更多信息）

| do | 参数 |
|---|---|
| `expect_text` | `text`, `regex`, `exact`, `present`(默认 true), `within` |
| `expect_visible` | 目标, `present` |
| `expect_value` / `expect_var` | `equals` / `contains` / `matches` / `gte` / `lte` |
| `expect_count` | 目标, `equals` / `min` / `max` |
| `expect_url` | `contains` / `not_contains` |
| `expect_response` | `watch`, `status`, `body_contains`, `body_not_contains` |

## 4. 一个完整例子：核对“汇总等于各行之和”

```json
[
  {"do": "read_table", "selector": "tr.ant-table-row", "as": "rows"},
  {"do": "sum_col", "var": "rows", "col": 4, "as": "sum_in"},
  {"do": "read", "text": "输入 Token：", "attr": "text", "as": "head"},
  {"do": "expect_var", "var": "sum_in", "equals": "647427", "label": "各行输入 Token 之和等于任务汇总"}
]
```

## 5. 探索新页面（还不知道怎么写用例时）

- 录制：`python -m playwright codegen --load-storage=<登录态文件> <地址>`，边点边生成代码，据此翻译成 JSON 步骤。
- 让 AI agent 现场驱动浏览器：用 Playwright MCP 服务器，接入方法、已验证的参数与用法要点见 `08-PlaywrightMCP接入.md`；先用 `python -m wft mcp-check` 自检。探索出来的步骤再固化成 JSON，之后回归直接 `wft run`，不再需要 agent。
- 排查页面：`python -m wft run … --headed`；失败后看 `out/screenshots/*现场.png`；`python -m playwright show-trace out/trace.zip`。

## 6. UI 框架常见现象（Ant Design 等）

| 现象 | 原因 | 应对 |
|---|---|---|
| 悬停才出现的操作按钮（编辑/更多） | 按钮在悬停时才渲染或可见 | 先 `hover` 卡片，再点；`card` 目标已处理“卡片范围” |
| 下拉/弹出菜单点了没反应 | 标签页在后台时动画停在“进入准备”态 | Playwright 无头模式不存在该问题；有头模式保持窗口在前台 |
| 页面里有多个同名文字（列表表头 + 弹窗里的同名标签） | 弹窗叠在列表之上 | 用 `last` / `after_text` / `within` 限定到弹窗 |
| 输入框失焦后值被改 | 组件有格式化/范围修正 | `fill` → `press Tab` → `read attr=value` 取修正后的值再断言 |
| 选了筛选项列表没变 | 需要再点“查询” | 记录为交互问题；用例里补一步点击查询再断言 |
| 日期框手输无效 | 只接受日历点选 | 两种方式都试，记录差异 |
| 任务秒级完成，抓不到“执行中” | 数据量太小 | 加大用例数×轮次，创建后立即读取；仍抓不到写“未捕捉到” |
| 页面加载转圈很久 | 内网/环境慢 | 提高 `timeout_ms`；反复出现时先看环境，不要判产品缺陷 |
