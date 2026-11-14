# 08 Playwright MCP 接入（可选：让 AI agent 现场探索页面）

用途：还不知道某个页面怎么写用例时，让 AI agent 通过 MCP 直接驱动浏览器探索，探索出的步骤再固化成 `spec.json`，之后回归直接 `wft run`，不再需要 agent。**MCP 用来探索，不用来回归。**

## 验证状态（诚实版）

| 项 | 状态 | 说明 |
|---|---|---|
| 服务能启动、握手、列工具 | ✅ 已实测 | `@playwright/mcp` 0.0.85（Playwright 1.66 alpha），25 个工具；`python -m wft mcp-check` 可自行复现 |
| 加载登录态并进入真实业务页面 | ✅ 已实测 | `--storage-state` 加载有效登录态后直接进入业务页（标题为业务系统，不是登录页）；登录态失效时落在登录页，`mcp-check` 能识别 |
| 悬停 → 点击菜单 → 点击入口 → 填表 → 上传 → 提交 → 抓接口 → 截图 → 执行脚本 | ✅ 已实测（**本地页面**） | 完整链路通过，细节见下 |
| 在**真实业务页面**上走校验链路 | ✅ 已实测 | 进入对象 → 悬停卡片 → 点“更多” → 点入口 → 点“新建” → 点上传区并选文件 → 点“开始运行” → 读到报错“共 1 处错误：缺少必需列「用户输入」” → 抓到创建接口请求 → 截图。**只做了校验类，未创建数据**，事后核对任务总数未变 |
| 其他 MCP 客户端（各家 agent）的配置方式 | ⏳ 未验证（本次用自写的最小 MCP 客户端验证，没有用任何现成 AI 产品的客户端） | 下面给的是通用写法，各客户端配置文件位置与格式以其文档为准 |
| `--secrets`、`--caps`、`--cdp-endpoint` 等其他参数 | 未验证 | 仅确认参数存在 |

## 启动命令（已验证的参数组合）

```bash
npx -y @playwright/mcp@latest --headless --isolated --browser chrome \
    --storage-state <登录态文件> --output-dir <输出目录>
```

- `--isolated`：浏览器配置只在内存里，不污染本机 Chrome 的资料，也不会和别的会话共用登录态。
- `--storage-state`：加载 `wft login` 保存的登录态；登录态文件等同凭据，别提交仓库。
- `--browser chrome`：用本机 Chrome；`msedge` 同理。去掉 `--headless` 就是有头模式，方便你看着它操作。
- 需要 Node.js 和网络（首次会下载）。

多数 MCP 客户端的配置形如（文件位置和外层字段以该客户端文档为准）：

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest", "--headless", "--isolated", "--browser", "chrome",
               "--storage-state", "/绝对路径/state.json", "--output-dir", "/绝对路径/mcp-out"]
    }
  }
}
```

接入后先运行自检：`python -m wft mcp-check --url <被测页面> --state <登录态文件>`。

## 在真实业务页面上额外踩到的点

| 现象 | 应对 |
|---|---|
| `browser_wait_for` 的文字等待默认只有 5 秒，卡片还没渲染就超时 | 循环：`browser_snapshot` 看文字在不在，不在就 `browser_wait_for {time:3}`，最多等约 60 秒 |
| 页面加载中短暂显示“目前未找到智能体”的空态，随后才出现卡片 | 同上，不要把空态当结论 |
| 悬停后按钮要过约 1 秒才进入无障碍树，立刻取快照看不到“更多” | 悬停后先等 1～2 秒再取快照 |
| 点“新建”后表单出现有延迟，立刻取快照仍是列表页 | 轮询快照，直到出现“开始运行”再继续 |
| 上传区是一个没有名字的按钮，文字“点击选择文件”在它的子节点里 | 在快照里找到含该文字的行，往上找最近的 `button` 的 `ref`，点它再调用文件上传 |
| 校验不通过时创建接口也返回 **HTTP 200**，错误在响应体里 | 判断校验结果要读页面提示或响应体，不能只看状态码 |
| 刷新或重新进入后 `ref` 全变 | 每次都重新取快照，不要缓存 `ref` |
| 被测系统的用户服务 502 时，登录无提示、无跳转 | 先用 `curl` 看相关接口是不是 502，再判断是工具问题还是环境问题 |

## 实测得到的用法要点

1. **以“快照”为中心**：`browser_snapshot` 返回页面的无障碍树，每个节点带 `ref`；之后的 `browser_click`、`browser_hover`、`browser_type` 都用 `target` 参数传这个 `ref`（0.0.85 里参数名是 `target`，旧文章里的 `ref`/`element` 写法会报“Invalid arguments”）。每次页面变化后重新取快照，`ref` 会变。
2. **悬停才出现的按钮**：先对“卡片”这个节点 `browser_hover`，再取快照，按钮才会出现在树里。如果页面结构太“平”（卡片没有独立节点），悬停会落到整个 body 上，按钮出不来——这时让 agent 换一个更具体的节点悬停，或改用 `wft` 的 `card` 目标定位。
3. **文件上传分两步**：先点击页面上的上传控件（快照里通常是 `Choose File` 按钮或上传区域）触发文件选择，再调用 `browser_file_upload` 传 `paths`。直接调用会报“can only be used when there is related modal state present”。
4. **上传路径限制**：默认只允许工作目录和输出目录里的文件，否则报“outside allowed roots”。要用别处的文件，要么把文件拷进工作目录，要么加 `--allow-unrestricted-file-access`（会放开整个文件系统和 `file://`，慎用）。
5. **`browser_type`** 是替换式填写（实测默认值被覆盖），不是追加。
6. **接口取证**：`browser_network_requests`（必须传 `static`，传 `false` 只看接口）列出请求并带序号，再用 `browser_network_request` 按序号看详情；与 `wft run` 的 `watch`/`expect_response` 作用相同。
7. **其他**：`browser_take_screenshot` 保存截图；`browser_evaluate` 执行只读 JS 取值；`browser_wait_for` 等文字出现/消失；`browser_find` 在快照里按文字或正则搜索。
8. 单点登录/验证码：先用 `wft login --headed` 人工登录并保存登录态，再让 MCP 加载。

## 从探索到固化

1. agent 用 MCP 走一遍：入口 → 新建 → 上传 → 提交，记录每一步操作的**文字和角色**（不是 `ref`，`ref` 每次都变）。
2. 按 `04-用例DSL与wft命令参考.md` 翻译成 JSON 步骤：悬停/点击用 `card`+`text`，输入框用 `after_text`/`role`，上传用 `upload`。
3. 用 `wft run --only <用例>` 验证，通过后纳入用例集。

## 安全

- MCP 会真的点击、提交，探索时同样遵守 `02-测试规范.md`：只动自己的数据、不改共享配置、新建数据带前缀。
- 不要把口令交给 agent；让它只使用登录态文件。
- 探索产生的数据同样要登记并在交付时说明。
