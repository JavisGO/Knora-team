#!/usr/bin/env python3
"""测试报告自动核对：交付前必须跑一遍，ERROR 清零才可交付。

用法：
  python -m wft check <报告.md> [--run run.json] [--prefix 任务名前缀]
                             [--forbid 正则 ...] [--secret 字符串 ...] [--json]

检查项（ERROR 阻止交付，WARN 需人工确认）：
  E1  引用的每张图片必须存在、非空、是真正的 PNG/JPEG/WEBP
  E2  必备章节：概述 / 汇总 / 明细 / 缺陷 / 未覆盖 / 结论 / 新建的任务
  E3  汇总表计数必须与明细一致（支持横向汇总表和竖向汇总表；支持“表格明细”和“### 标题｜结果”两种写法）
  E4  每条缺陷（D-xx 小节）必须带截图；确实无法截图的要写明原因
  E5  结果为 失败 的用例必须带截图，或写明“无截图：原因”
  E6  存在 失败/阻塞/未测/部分通过 时，结论里不得出现“全部通过/验收通过/无问题”等字样
  W1  通过 的用例没有截图
  W2  报告里出现“他人产物”关键词（forbid / run.json 的 forbidden_evidence），需确认只是边界声明
  W3  新建任务名称不以约定前缀开头
  W4  出现疑似口令（密码: xxx）或 --secret 指定的字符串
  W5  screenshots 目录里存在报告未引用的图片
"""
import argparse
import json
import os
import re
import sys
from urllib.parse import unquote

RESULT_ORDER = [("部分通过", "partial"), ("通过", "pass"), ("失败", "fail"), ("阻塞", "blocked"), ("未测", "untested")]
LABEL = {"pass": "通过", "fail": "失败", "blocked": "阻塞", "untested": "未测", "partial": "部分通过"}
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def classify(text):
    t = re.sub(r"[*`\s]", "", text)
    for key, val in RESULT_ORDER:
        if t.startswith(key):
            return val
    return None


def split_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def read_tables(lines):
    """返回 [(start_line_idx, header_cells, [(line_idx, cells)])]"""
    tables, i = [], 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1].replace("|", "", 1) if False else lines[i + 1].lstrip().lstrip("|")):
            header = split_row(lines[i])
            rows, j = [], i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append((j, split_row(lines[j])))
                j += 1
            tables.append((i, header, rows))
            i = j
        else:
            i += 1
    return tables


def sections(lines):
    """[(level, title, start, end)]  end 为下一同级或更高级标题前"""
    heads = []
    for i, l in enumerate(lines):
        m = HEAD_RE.match(l)
        if m:
            heads.append((len(m.group(1)), m.group(2).strip(), i))
    out = []
    for k, (lv, title, st) in enumerate(heads):
        en = len(lines)
        for lv2, _, st2 in heads[k + 1:]:
            if lv2 <= lv:
                en = st2
                break
        out.append((lv, title, st, en))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--run")
    ap.add_argument("--prefix")
    ap.add_argument("--forbid", action="append", default=[])
    ap.add_argument("--secret", action="append", default=[])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    errors, warns = [], []
    E = lambda m: errors.append(m)
    W = lambda m: warns.append(m)

    prefix = args.prefix
    forbid = list(args.forbid)
    if args.run and os.path.exists(args.run):
        run = json.load(open(args.run, encoding="utf-8"))
        prefix = prefix or run.get("task_prefix")
        forbid += run.get("forbidden_evidence", [])

    rp = os.path.abspath(args.report)
    base = os.path.dirname(rp)
    text = open(rp, encoding="utf-8").read()
    lines = text.split("\n")

    # ---- E1 图片 ----
    refs = []
    for i, l in enumerate(lines):
        for m in IMG_RE.finditer(l):
            refs.append((i + 1, unquote(m.group(1).strip().split(" ")[0])))
    seen = set()
    for ln, p in refs:
        if re.match(r"^[a-z]+://", p):
            W(f"第{ln}行 图片是网络地址，交付件应使用相对路径: {p}")
            continue
        full = os.path.join(base, p)
        if not os.path.isfile(full):
            E(f"第{ln}行 图片不存在: {p}")
            continue
        if p in seen:
            continue
        seen.add(p)
        size = os.path.getsize(full)
        if size < 2048:
            E(f"第{ln}行 图片疑似空白/损坏（{size} 字节）: {p}")
            continue
        head = open(full, "rb").read(12)
        if not (head.startswith(b"\x89PNG") or head.startswith(b"\xff\xd8") or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")):
            E(f"第{ln}行 文件不是有效图片: {p}")

    # ---- W5 未引用图片 ----
    sd = os.path.join(base, "screenshots")
    if os.path.isdir(sd):
        used = {os.path.normpath(p) for _, p in refs}
        # 同目录下其它 .md（如历史报告）引用的图片也算已引用
        for other in os.listdir(base):
            if other.endswith(".md") and os.path.join(base, other) != rp:
                for m in IMG_RE.finditer(open(os.path.join(base, other), encoding="utf-8").read()):
                    used.add(os.path.normpath(unquote(m.group(1).strip().split(" ")[0])))
        for fn in sorted(os.listdir(sd)):
            if not fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue
            if os.path.normpath(os.path.join("screenshots", fn)) not in used:
                W(f"screenshots/{fn} 未被报告引用")

    secs = sections(lines)
    titles = [s[1] for s in secs]

    # ---- E2 章节 ----
    need = [("概述", "测试概述"), ("汇总", "结果汇总"), ("明细", "用例明细"), ("缺陷", "缺陷清单"), ("未覆盖", "未覆盖项"), ("结论", "结论与建议"), ("任务", "本测试员新建的任务")]
    for kw, label in need:
        if not any(kw in t for t in titles):
            E(f"缺少章节：{label}（标题里需含「{kw}」）")

    # ---- 明细统计（表格 + 标题两种写法） ----
    detail = []  # (line, id, result, has_img, has_noimg_reason)
    tables = read_tables(lines)
    summary_tables = []
    for ti, header, rows in tables:
        hs = [re.sub(r"\s", "", h) for h in header]
        if "结果" in hs and any(h in hs for h in ("编号", "测试项", "用例")) and len(hs) >= 4:
            ri = hs.index("结果")
            si = next((k for k, h in enumerate(hs) if "截图" in h), None)
            for ln, cells in rows:
                if len(cells) <= ri:
                    continue
                r = classify(cells[ri])
                if not r:
                    continue
                shot = cells[si] if si is not None and si < len(cells) else ""
                row_text = " ".join(cells)
                detail.append((ln + 1, cells[0], r, "![" in shot or "![" in row_text, bool(re.search(r"无截图|无（|^无|无[:：（(]", shot)) or "无截图" in row_text))
        elif all(any(k == h for h in hs) for k in ("通过", "失败")) and ("阻塞" in hs or "未测" in hs):
            summary_tables.append(("h", header, rows))
        elif "结果" in hs and ("数量" in hs or "个数" in hs):
            summary_tables.append(("v", header, rows))
    for lv, title, st, en in secs:
        m = re.search(r"[｜|]\s*(部分通过|通过|失败|阻塞|未测)", title)
        if m and not re.match(r"^D-?\d+", title):
            block = "\n".join(lines[st:en])
            detail.append((st + 1, title.split("｜")[0].strip(), classify(m.group(1)), "![" in block, bool(re.search(r"无截图|无页面可截|无可进入", block))))

    counts = {k: 0 for k in LABEL}
    for _, _, r, _, _ in detail:
        counts[r] += 1
    total = sum(counts.values())

    # ---- E3 汇总核对 ----
    if not detail:
        W("没有识别到任何用例结果行（明细表需含「编号/测试项…/结果/截图」列，或用「### 编号 名称｜结果」小节）")
    for kind, header, rows in summary_tables:
        hs = [re.sub(r"\s", "", h) for h in header]
        if kind == "h" and rows:
            cells = rows[0][1]
            claimed = {}
            for k, h in enumerate(hs):
                for lab, key in (("部分通过", "partial"), ("通过", "pass"), ("失败", "fail"), ("阻塞", "blocked"), ("未测", "untested")):
                    if h == lab and k < len(cells) and re.match(r"^\d+", cells[k].replace("*", "").strip()):
                        claimed[key] = int(re.match(r"^\d+", cells[k].replace("*", "").strip()).group())
            for key, v in claimed.items():
                actual = counts[key]
                if key == "pass" and "partial" not in claimed:
                    pass
                if v != actual:
                    E(f"汇总表「{LABEL[key]}」={v}，但明细统计为 {actual}")
            if "partial" not in claimed and counts["partial"]:
                W(f"明细有 {counts['partial']} 项“部分通过”，汇总表没有对应列")
            for k, h in enumerate(hs):
                if h in ("合计", "总计") and k < len(cells) and cells[k].strip().isdigit() and int(cells[k]) != total:
                    E(f"汇总表合计={cells[k]}，但明细共 {total} 项")
        if kind == "v":
            for _, cells in rows:
                if len(cells) < 2:
                    continue
                key = classify(cells[0])
                num = re.match(r"^\d+", cells[1].replace("*", "").strip())
                if key and num and int(num.group()) != counts[key]:
                    E(f"汇总表「{LABEL[key]}」={num.group()}，但明细统计为 {counts[key]}")

    # ---- E5 / W1 截图要求 ----
    for ln, cid, r, has_img, noreason in detail:
        if r in ("fail", "partial") and not has_img and not noreason:
            E(f"第{ln}行 {cid}（{LABEL[r]}）没有截图，也没写“无截图：原因”")
        elif r == "pass" and not has_img:
            W(f"第{ln}行 {cid}（通过）没有截图")
        elif r in ("blocked", "untested") and not has_img and not noreason:
            W(f"第{ln}行 {cid}（{LABEL[r]}）没有截图，建议写明“无截图：原因”")

    # ---- E4 缺陷截图 ----
    ndef = 0
    for lv, title, st, en in secs:
        if re.match(r"^D-?\d+", title):
            ndef += 1
            block = "\n".join(lines[st:en])
            if "![" not in block:
                if re.search(r"未能|待复核|无法截|无截图", block):
                    W(f"缺陷「{title}」没有截图（已说明原因）")
                else:
                    E(f"缺陷「{title}」没有截图")
    if ndef == 0 and counts["fail"]:
        W("有失败用例但没有识别到缺陷小节（标题需形如「### D-01 …」）")

    # ---- E6 结论一致性 ----
    bad = counts["fail"] + counts["blocked"] + counts["untested"] + counts["partial"]
    if bad:
        for lv, title, st, en in secs:
            if "结论" in title:
                blk = "\n".join(lines[st:en])
                if re.search(r"全部通过|验收通过|可以验收|无任何问题|完全通过", blk) and not re.search(r"不能验收|不通过|未通过|无法验收|不构成", blk):
                    E("结论写了“通过/可验收”，但明细里仍有失败/阻塞/未测项")

    # ---- W2 他人产物 / W3 前缀 / W4 口令 ----
    for pat in forbid:
        for i, l in enumerate(lines):
            if re.search(pat, l):
                W(f"第{i+1}行 出现「{pat}」——确认这只是“未采用/未引用”的边界声明，而不是把他人产物当作证据")
    if prefix:
        for lv, title, st, en in secs:
            if "任务" in title and ("新建" in title or "创建" in title):
                for ti, header, rows in tables:
                    if st <= ti < en:
                        hs = [re.sub(r"\s", "", h) for h in header]
                        ni = next((k for k, h in enumerate(hs) if "任务名称" in h or h == "任务"), None)
                        if ni is None:
                            continue
                        for ln, cells in rows:
                            if ni < len(cells) and not re.sub(r"^\d+\s*", "", cells[ni]).startswith(prefix):
                                W(f"第{ln+1}行 任务名称不以约定前缀「{prefix}」开头: {cells[ni][:40]}")
    for i, l in enumerate(lines):
        if re.search(r"(密码|password|passwd)\s*[:：=]\s*[^\s，。；;）)]+", l, re.I):
            W(f"第{i+1}行 疑似写入了口令，请确认并删除")
        for s in args.secret:
            if s and s in l:
                E(f"第{i+1}行 出现了被禁止的敏感字符串（--secret）")

    result = {"report": rp, "images_ok": len(seen), "image_refs": len(refs), "detail": counts, "defects": ndef, "errors": errors, "warnings": warns}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"报告: {rp}")
        print(f"图片: 引用 {len(refs)} 处 / 去重 {len(seen)} 张")
        print("明细: " + "  ".join(f"{LABEL[k]}={v}" for k, v in counts.items()) + f"  合计={total}  缺陷小节={ndef}")
        for e in errors:
            print("ERROR", e)
        for w in warns:
            print("WARN ", w)
        print("核对未通过" if errors else "核对通过（WARN 请人工确认）")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
