# Quickstart：10 分钟跑通一遍（不需要任何账号和被测系统）

目标：在你自己的电脑上，用自带的**本地演示站点**把整套流程完整走一遍——造数据、自动执行、看结果、生成报告、核对、导出 PDF。走完你会清楚每一步产出什么，再换成自己的功能。

> 需要：**Python 3.9+** 和一个 **Chrome（或 Edge）**。没有 Chrome 见文末 FAQ。
> 所有命令都在 `web-feature-test` 目录下执行。**macOS / Linux 用左边写法，Windows 用括号里的写法。**

---

## 第 1 步：安装（约 2 分钟）

**最省事：一条命令**（建虚拟环境、装依赖、预检，并启动演示站点用浏览器跑一个用例做自检）：

```bash
cd web-feature-test
python3 install.py                          # Windows：py install.py
. .venv/bin/activate                        # 激活虚拟环境；Windows：.venv\Scripts\activate
```

看到“安装完成”即可。也可以手动装：

```bash
cd web-feature-test
python3 -m venv .venv                       # Windows：py -m venv .venv
. .venv/bin/activate                        # Windows：.venv\Scripts\activate
pip install -r requirements.txt
python -m wft doctor --out ./out-demo
```

`doctor` 应该输出一串 `[OK]`，最后一行是“预检通过”。出现 `[FAIL]` 先看 FAQ。

## 第 2 步：启动演示站点（单独开一个终端窗口）

```bash
cd web-feature-test
. .venv/bin/activate                        # Windows：.venv\Scripts\activate
python examples/demo-site/server.py 8801
```

看到“演示站点：http://127.0.0.1:8801/index.html”即可。这个窗口保持打开。
可以顺手用浏览器打开这个地址玩一下：悬停卡片 → 更多 → 评测管理 → 新建评测任务 → 选文件 → 开始运行。后面的自动化做的就是这些事。

## 第 3 步：造测试数据包（回到第一个终端）

```bash
python -m wft pack good      --spec examples/demo-site/pack-spec.json --out ./out-demo/packs --name good_1 --rows 1
python -m wft pack anomalies --spec examples/demo-site/pack-spec.json --out ./out-demo/packs
```

得到 1 个正常包和 14 个异常包（缺必填列、重复列、全空行、附件不存在、附件重名……），每个异常包的“期望结果”记录在 `out-demo/packs/manifest.json` 里。

## 第 4 步：自动执行（约 1 分钟）

```bash
python -m wft run examples/demo-site/demo.spec.json --out ./out-demo/run --no-login \
    --data-dir ./out-demo/packs --allow-create
```

你会看到类似输出：

```
TC-01    通过   功能入口：悬停卡片后能展开“更多”并进入功能面板
TC-02    通过   任务列表字段齐全
TC-03    通过   任务名称必填
TC-04    通过   非 ZIP 文件在选择时被拦截
TC-V1 … TC-V6   通过   上传校验：缺列 / 重复列 / 无用例 / 必填缺失 / 附件缺失 / 附件重名
TC-R1    失败   执行轮次边界：输入 0 应给出提示（不得静默替换）
         ✗ 出现范围/非法值提示：未找到文本：范围|不能|必须|不合法
TC-R2    失败   执行轮次边界：输入 11 …
TC-C1    通过   主链路冒烟：1 用例×1 轮创建并跑完
汇总：通过=11  失败=2  合计=13
```

**这 2 个“失败”是演示站点故意埋的缺陷**：输入 0 或 11 时，页面悄悄把它改成合法值，没有任何提示。很多需求明确要求“校验失败要给出原因，不得静默替换”，这种情况就应该判失败——程序替你判了。

## 第 5 步：看结果

| 看什么 | 在哪 |
|---|---|
| 每个用例的结果、步骤、实际现象 | `out-demo/run/results.json` |
| 现成的“用例明细”表（可直接粘进报告） | `out-demo/run/用例明细.generated.md` |
| 每个用例的截图；失败的还有“现场”截图 | `out-demo/run/screenshots/` |
| 每一步的回放（含页面快照） | `python -m playwright show-trace out-demo/run/trace.zip` |

打开 `screenshots/R1_TC-R1_现场.png`，能直接看到“输入 0 失焦后变成 1”的现场。

## 第 6 步：生成报告、核对、导出 PDF（约 3 分钟）

```bash
# 建本轮目录，拷入报告模板
python -m wft init --object 演示功能 --out ./out-demo/report

# 把明细表粘进报告，补上缺陷清单与结论（模板里有提示）。这里先用示例：
cp out-demo/run/用例明细.generated.md out-demo/report/*/用例明细.md        # Windows：copy
cp -r out-demo/run/screenshots out-demo/report/*/                          # Windows：xcopy /E

# 核对：图片是否存在、汇总与明细是否一致、缺陷是否带截图、结论是否与结果一致
python -m wft check out-demo/report/*/测试报告.md
```

此时 `check` 会报 `ERROR`——因为模板里的占位内容还没填。**这正是它该做的事：没填完就不让交付。** 把模板里 `〔…〕` 提示替换成你的内容后再核对，ERROR 清零才算合格。

```bash
python -m wft pdf out-demo/report/*/测试报告.md          # 填完后：生成 PDF，截图内嵌
```

## 第 7 步：换成你自己的功能

1. **需求方给你**：被测对象在哪、环境地址、账号、需求原文。填 `templates/测试需求输入单.md`。
2. **登录一次**（口令只在终端里输入，不会出现在命令行或文件里）：
   ```bash
   export TEST_PASSWORD='你的口令'                                  # Windows PowerShell：$env:TEST_PASSWORD='你的口令'
   python -m wft login --url <被测页面地址> --account <账号> --state ./state.json
   ```
   有验证码/单点登录：加 `--headed`，在弹出的浏览器里人工登录一次。
3. **复制并改数据包规格** `config/pack-spec.example.json`（表头、必填列、附件列），重新 `wft pack`。
4. **复制并改用例** `examples/demo-site/demo.spec.json`（改 `vars` 里的文案和 `cases` 里的步骤）。语法速查：`references/04-用例DSL与wft命令参考.md`。
5. **先只跑冒烟**，通了再全量：
   ```bash
   python -m wft run my.spec.json --out ./out/run --state ./state.json --data-dir ./packs --only TC-01
   python -m wft run my.spec.json --out ./out/run --state ./state.json --data-dir ./packs --prefix R1_
   ```
   会新建数据的用例要显式加 `--allow-create`；新建的数据名称一律带前缀，方便事后清理。
6. 看结果、写报告、`wft check`、`wft deliver`、`wft pdf`。流程细节：`references/01-流程与分工.md`。

## 三条要记住的规矩

1. **没测到的不写“通过”**；环境干扰（页面一直转圈、网络瞬断）标“待复核”，不直接判产品缺陷。
2. **需求写明禁止的行为以需求为准**：输入非法值被悄悄改掉，哪怕“能用”也是失败。
3. **每个测试点都要有截图**并嵌进报告；`wft check` 过不了就别交付。

完整规则见 `references/02-测试规范.md` 和 `references/03-验收标准.md`。

---

## FAQ

**`doctor` 报“无法启动浏览器”**：没装 Chrome 就 `python -m playwright install chromium`，之后所有命令加 `--channel chromium`（或设环境变量 `WFT_CHANNEL=chromium`）；用 Edge 则 `--channel msedge`。

**端口 8801 被占用**：换端口 `python examples/demo-site/server.py 8802`，并给第 4 步加 `--var ENTRY_URL=http://127.0.0.1:8802/index.html`。

**`pip install` 很慢或失败**：内网环境配置公司的 pip 镜像；Playwright 默认**不需要**下载浏览器（用你本机的 Chrome）。

**第 4 步全部“阻塞”**：先确认第 2 步的演示站点还开着，浏览器能打开 http://127.0.0.1:8801/index.html。

**想让 AI agent 帮你做**：把整个目录交给 agent，让它读 `SKILL.md`（或 `AGENTS.md`）。口令只由你在终端里输入，不要贴给 agent。详见 `README.md` 第 3 节。

**测真实系统时登录一直失败/页面没反应**：先用 `curl` 看相关接口是不是 502/超时——可能是被测环境的问题而不是工具的问题（`references/05-踩坑与应对.md` 有一次真实经历）。
