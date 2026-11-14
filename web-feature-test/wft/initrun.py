#!/usr/bin/env python3
"""初始化一次测试运行的目录骨架，并拷入报告模板。

用法：
  python -m wft init --object "订单导入" --kind feature --round 1 --out ./测试输出
生成：
  <out>/测试-<日期>-<对象>-R<轮次>/
      screenshots/   截图（文件名以 R<轮次>_ 开头）
      testdata/      本轮用到的数据包
      测试计划.md  用例明细.md  测试报告.md  run.json
run.json 记录本轮约定（session 名、任务前缀、截图前缀），测试员与核对脚本都以它为准。
"""
import argparse
import datetime
import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "..", "templates")


def slug(s):
    return re.sub(r"[^0-9A-Za-z一-鿿]+", "-", s).strip("-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--object", required=True, help="被测对象名称（用于目录名与任务前缀）")
    ap.add_argument("--kind", default="feature", help="对象类型标签：agent / logic / feature …")
    ap.add_argument("--round", type=int, default=1, help="第几轮（补测/复测递增）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tester", default="tester1", help="测试员标识（人或 agent 的名字），写入 run.json")
    ap.add_argument("--forbid", action="append", default=[], help="他人产物的特征（正则），报告里出现会被 check_report 提醒；可多次")
    args = ap.parse_args()

    today = datetime.date.today().strftime("%Y%m%d")
    name = f"测试-{today}-{slug(args.object)}-R{args.round}"
    root = os.path.join(args.out, name)
    for d in ("screenshots", "testdata"):
        os.makedirs(os.path.join(root, d), exist_ok=True)

    run = {
        "object": args.object,
        "kind": args.kind,
        "round": args.round,
        "date": today,
        "tester": args.tester,
        "task_prefix": f"【自动化测试-{args.object}R{args.round}】",
        "screenshot_prefix": f"R{args.round}_",
        "forbidden_evidence": args.forbid,
    }
    with open(os.path.join(root, "run.json"), "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=2)

    for tpl, dst in (("测试计划模板.md", "测试计划.md"), ("用例明细模板.md", "用例明细.md"), ("测试报告模板.md", "测试报告.md")):
        src = os.path.join(TPL, tpl)
        if os.path.exists(src):
            text = open(src, encoding="utf-8").read()
            text = text.replace("{{对象}}", args.object).replace("{{日期}}", today).replace("{{轮次}}", str(args.round))
            with open(os.path.join(root, dst), "w", encoding="utf-8") as f:
                f.write(text)
    print(root)
    print(json.dumps(run, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
