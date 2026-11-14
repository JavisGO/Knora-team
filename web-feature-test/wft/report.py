"""把 results.json 渲染成报告里的“用例明细”表（Markdown）。

用法：python -m wft report <results.json> [--out 文件]
生成的是“草稿”：结果为“未测（待人工判定）”的行需要人工/agent 看截图后改成通过/失败；
缺陷清单、结论、未覆盖项仍由人写，写完用 python -m wft check 核对。
"""
import argparse
import json
import sys

LABEL = {"pass": "通过", "fail": "失败", "blocked": "阻塞", "manual": "未测（待人工判定）", "skipped": "未测"}


def _cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def render(data):
    lines = [
        f"<!-- 由 wft run 生成：{data.get('spec', '')}，{data.get('started', '')} ~ {data.get('finished', '')} -->",
        "",
        "| 编号 | 测试项 | 步骤与预期 | 实际 | 结果 | 截图 |",
        "|---|---|---|---|---|---|",
    ]
    for c in data["cases"]:
        steps = "；".join(s["label"] for s in c["steps"] if not s["label"].startswith(("wait", "screenshot")))[:160]
        exp = c.get("expect") or ""
        step_col = _cell(steps + (f"。预期：{exp}" if exp else ""))
        actual = []
        for s in c["steps"]:
            if s["status"] == "fail":
                actual.append("✗ " + s["detail"])
            elif s["do"].startswith("expect_") and s["detail"]:
                actual.append("✓ " + s["detail"])
        if c["error"]:
            actual.append("异常：" + c["error"])
        actual += c.get("notes", []) + [f"待判定：{m}" for m in c.get("manual", [])]
        actual_col = _cell("；".join(actual)[:400])
        status = LABEL[c["status"]]
        if c["status"] == "skipped":
            shots = "无截图：冒烟未通过，用例未执行"
        else:
            shots = " ".join(f"![{c['id']}](screenshots/{fn})" for fn in c["screenshots"])
        lines.append(f"| {c['id']} | {_cell(c['title'])} | {step_col} | {actual_col} | {status} | {shots} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--out")
    args = ap.parse_args()
    md = render(json.load(open(args.results, encoding="utf-8")))
    if args.out:
        open(args.out, "w", encoding="utf-8").write(md)
        print(args.out)
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
