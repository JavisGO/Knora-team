#!/usr/bin/env python3
"""整理交付目录：只保留“报告引用到的截图”和测试数据，自动剔除他人/中间产物。

用法：
  python -m wft deliver --report <工作目录>/测试报告.md \
      --src <工作目录> [--src <补测目录> ...] --out <交付目录>/<名称> \
      [--testdata <数据包目录> ...] [--extra-report <历史报告.md> ...]

行为：
  1. 报告拷到 <out>/测试报告.md（--extra-report 一并拷入并同样处理其图片引用）
  2. 报告里每个 ![](screenshots/x.png) 依次在各 --src 的 screenshots/ 下查找并拷到 <out>/screenshots/
  3. --testdata 目录整体拷到 <out>/testdata/
  4. 找不到的图片列出来并返回非 0——此时要么补拍，要么在报告里改为“无截图：原因”
  5. 不删除任何源文件
"""
import argparse
import os
import re
import shutil
import sys
from urllib.parse import unquote

IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--src", action="append", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--testdata", action="append", default=[])
    ap.add_argument("--extra-report", action="append", default=[])
    args = ap.parse_args()

    os.makedirs(os.path.join(args.out, "screenshots"), exist_ok=True)
    reports = [(args.report, "测试报告.md")] + [(p, os.path.basename(p)) for p in args.extra_report]
    missing, copied = [], set()
    for rp, dst in reports:
        shutil.copyfile(rp, os.path.join(args.out, dst))
        text = open(rp, encoding="utf-8").read()
        for m in IMG_RE.finditer(text):
            rel = unquote(m.group(1).strip().split(" ")[0])
            if rel in copied or re.match(r"^[a-z]+://", rel):
                continue
            name = os.path.basename(rel)
            found = None
            for s in args.src + [os.path.dirname(rp)]:
                for cand in (os.path.join(s, rel), os.path.join(s, "screenshots", name)):
                    if os.path.isfile(cand) and os.path.getsize(cand) > 0:
                        found = cand
                        break
                if found:
                    break
            if found:
                shutil.copyfile(found, os.path.join(args.out, "screenshots", name))
                copied.add(rel)
            else:
                missing.append(rel)

    for td in args.testdata:
        if os.path.isdir(td):
            shutil.copytree(td, os.path.join(args.out, "testdata", os.path.basename(td.rstrip("/"))), dirs_exist_ok=True)

    print(f"已整理到 {args.out}：报告 {len(reports)} 份，截图 {len(copied)} 张")
    if missing:
        print("以下引用的图片没找到，请补拍或在报告中改为“无截图：原因”：")
        for m in sorted(set(missing)):
            print("  MISSING", m)
        sys.exit(1)


if __name__ == "__main__":
    main()
