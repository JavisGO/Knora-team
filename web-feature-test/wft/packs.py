#!/usr/bin/env python3
"""构造「Excel + 附件目录」ZIP 用例包：正常包 + 一整套异常包。

适用：任何“上传 ZIP（根目录 xlsx + attachments/ 附件目录）批量导入用例”的功能，
例如“批量评测/批量导入任务”这类功能。

用法：
  python -m wft pack good      --spec spec.json --out ./packs --name good_3cases --rows 3
  python -m wft pack anomalies --spec spec.json --out ./packs
  python -m wft pack list-anomalies

spec.json 字段（见 ../config/pack-spec.example.json）：
  sheet            用例工作表名，默认「用例」
  excel_name       ZIP 根目录下的 Excel 文件名，默认 cases.xlsx
  attach_dir       附件目录名，默认 attachments
  headers          表头列表（顺序即列顺序）
  required         必填列
  attach_columns   文件类型列（单元格填文件名）
  multi_file_columns  支持多文件（逗号分隔）的列
  allowed_ext      {列名: ["xls","xlsx"]}，限定扩展名；缺省不限制
  good_rows        正常用例行（二维数组），行数不足时循环复用
  attachments      {文件名: 文本内容}，正常附件
  long_text_len    长文本异常包的字符数，默认 20000

每个异常包会连同期望结果写入 manifest.json，便于测试时对照：
  expect = reject  -> 应在上传/提交阶段被拦截并给出可定位的原因
  expect = accept  -> 应被接受（用于验证“不静默替换/不误拦”）
  expect = observe -> 需求未规定，记录实际行为即可
"""
import argparse
import io
import json
import os
import sys
import zipfile

try:
    import openpyxl
except ImportError:  # pragma: no cover
    sys.exit("缺少 openpyxl：pip install --user openpyxl")

DEFAULT_SPEC = {
    "sheet": "用例",
    "excel_name": "cases.xlsx",
    "attach_dir": "attachments",
    "headers": ["输入内容", "附件"],
    "required": ["输入内容"],
    "attach_columns": ["附件"],
    "multi_file_columns": ["附件"],
    "allowed_ext": {},
    "good_rows": [["示例用例一", ""], ["示例用例二", ""], ["示例用例三", ""]],
    "attachments": {},
    "long_text_len": 20000,
}

ANOMALIES = {
    "missing_col": ("缺少必填列", "reject", "应指出缺少哪一列"),
    "dup_col": ("表头重复列", "reject", "应指出重复的列名"),
    "no_cases": ("仅表头无用例", "reject", "应提示无有效用例，且不能运行"),
    "all_blank": ("全空行", "reject", "全空行不计入用例；若全为空行应提示无有效用例"),
    "missing_value": ("第2行必填值缺失", "reject", "应定位到第 2 行 + 列名"),
    "attach_missing": ("附件文件不存在", "reject", "应定位到行列并给出文件名"),
    "dup_name": ("不同目录同名附件", "reject", "应提示文件名重复，最好带行列"),
    "wrong_type": ("附件扩展名不符", "reject", "应说明允许的类型"),
    "multi_file": ("多文件逗号分隔", "observe", "仅对支持多文件的列生效；记录是否接受及附件挂载情况"),
    "multi_xlsx": ("根目录多个 xlsx", "observe", "应提示根目录只能有一个 xlsx，或明确忽略规则"),
    "wrapped": ("外层多包一层目录", "accept", "文档若允许唯一一层外层目录则应接受"),
    "not_zip": ("非 ZIP 文件", "reject", "应在选择文件时拦截"),
    "long_text": ("超长文本用例", "observe", "记录是否成功；常用于尝试构造失败项"),
    "bad_file": ("内容不是有效文件的附件", "observe", "常用于尝试构造失败项；记录执行结果与错误信息"),
}


def load_spec(path):
    spec = dict(DEFAULT_SPEC)
    if path:
        with open(path, encoding="utf-8") as f:
            spec.update(json.load(f))
    return spec


def rows_of(spec, n):
    base = spec["good_rows"]
    return [list(base[i % len(base)]) for i in range(n)]


def make_xlsx(spec, headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = spec["sheet"]
    ws.append(headers)
    for r in rows:
        ws.append(r)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def write_zip(path, files):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data if isinstance(data, bytes) else data.encode("utf-8"))


def good_files(spec, rows):
    files = {spec["excel_name"]: make_xlsx(spec, spec["headers"], rows)}
    for fname, content in spec["attachments"].items():
        if fname.lower().endswith(".xlsx") and not content:
            # 内容留空的 xlsx 附件自动生成一个有效的小表格，避免“文件本身损坏”干扰测试
            wb = openpyxl.Workbook()
            wb.active.append(["序号"])
            wb.active.append([1])
            wb.active.append([2])
            bio = io.BytesIO()
            wb.save(bio)
            content = bio.getvalue()
        files[f'{spec["attach_dir"]}/{fname}'] = content
    return files


def valid_attachment(ext):
    """生成一个格式有效的小附件（xlsx 用真实表格，其余用文本）。"""
    if ext.lower() in ("xlsx", "xlsm"):
        wb = openpyxl.Workbook()
        wb.active.append(["序号"])
        wb.active.append([1])
        bio = io.BytesIO()
        wb.save(bio)
        return bio.getvalue()
    return "ok"


def first_attach_col(spec):
    cols = spec.get("attach_columns") or []
    return cols[0] if cols and cols[0] in spec["headers"] else None


def build_good(spec, out, name, n):
    rows = rows_of(spec, n)
    path = os.path.join(out, f"{name}.zip")
    write_zip(path, good_files(spec, rows))
    return path


def build_anomalies(spec, out):
    manifest = {}
    h = list(spec["headers"])
    ad = spec["attach_dir"]
    req = (spec.get("required") or [h[0]])[0]
    req_i = h.index(req)
    ac = first_attach_col(spec)
    ac_i = h.index(ac) if ac else None
    base_rows = rows_of(spec, 2)

    def put(key, files, fname=None):
        title, expect, hint = ANOMALIES[key]
        fname = fname or f"A_{key}.zip"
        write_zip(os.path.join(out, fname), files)
        manifest[fname] = {"anomaly": key, "title": title, "expect": expect, "hint": hint}

    # 缺必填列
    hh = [x for x in h if x != req]
    put("missing_col", {spec["excel_name"]: make_xlsx(spec, hh, [[r[i] for i, x in enumerate(h) if x != req] for r in base_rows])})
    # 重复列
    put("dup_col", {spec["excel_name"]: make_xlsx(spec, h + [req], [r + [r[req_i]] for r in base_rows])})
    # 仅表头
    put("no_cases", {spec["excel_name"]: make_xlsx(spec, h, [])})
    # 全空行
    put("all_blank", {spec["excel_name"]: make_xlsx(spec, h, [[""] * len(h), [""] * len(h)])})
    # 第 2 行必填缺失。注意：该行其余单元格必须有内容，否则整行是“全空行”会被系统忽略，
    # 变成一条有效数据而被真的创建出来（一次真实试跑踩过的坑）。
    rows = rows_of(spec, 2)
    rows[1][req_i] = ""
    extra = {}
    for i, col in enumerate(h):
        if i == req_i:
            continue
        if col in (spec.get("attach_columns") or []):
            ext = (spec.get("allowed_ext", {}).get(col) or ["txt"])[0]
            fname = f"ok.{ext}"
            rows[1][i] = fname
            extra[f"{ad}/{fname}"] = valid_attachment(ext)
        else:
            rows[1][i] = "x"
    files = {spec["excel_name"]: make_xlsx(spec, h, rows)}
    files.update(extra)
    put("missing_value", files)

    if ac:
        # 附件不存在
        rows = rows_of(spec, 2)
        rows[1][ac_i] = "不存在的文件.txt"
        put("attach_missing", {spec["excel_name"]: make_xlsx(spec, h, rows), f"{ad}/README.txt": "x"})
        # 不同目录同名
        rows = rows_of(spec, 2)
        rows[0][ac_i] = "dup.txt"
        put("dup_name", {spec["excel_name"]: make_xlsx(spec, h, rows), f"{ad}/dup.txt": "A", f"{ad}/sub/dup.txt": "B"})
        # 扩展名不符
        rows = rows_of(spec, 2)
        rows[1][ac_i] = "tool.exe"
        put("wrong_type", {spec["excel_name"]: make_xlsx(spec, h, rows), f"{ad}/tool.exe": b"MZ\x00\x00"})
        # 多文件逗号
        rows = rows_of(spec, 1)
        rows[0][ac_i] = "a.txt,b.txt"
        put("multi_file", {spec["excel_name"]: make_xlsx(spec, h, rows), f"{ad}/a.txt": "文件A内容", f"{ad}/b.txt": "文件B内容"})
        # 内容无效的附件
        rows = rows_of(spec, 1)
        rows[0][ac_i] = "坏文件.pdf"
        put("bad_file", {spec["excel_name"]: make_xlsx(spec, h, rows), f"{ad}/坏文件.pdf": b"this is not a real pdf"})

    # 根目录多个 xlsx
    gf = good_files(spec, rows_of(spec, 1))
    gf["cases2.xlsx"] = make_xlsx(spec, h, rows_of(spec, 1))
    put("multi_xlsx", gf)
    # 外层包一层
    wrapped = {f"外层目录/{k}": v for k, v in good_files(spec, rows_of(spec, 1)).items()}
    put("wrapped", wrapped)
    # 超长文本
    rows = rows_of(spec, 1)
    rows[0][req_i] = ("请阅读以下内容并用一句话概括：" + "这是一段用于测试超长输入的填充文本。" * 4000)[: int(spec.get("long_text_len", 20000))]
    put("long_text", {spec["excel_name"]: make_xlsx(spec, h, rows)})
    # 非 zip
    title, expect, hint = ANOMALIES["not_zip"]
    with open(os.path.join(out, "A_not_zip.txt"), "w", encoding="utf-8") as f:
        f.write("这不是 zip 文件")
    manifest["A_not_zip.txt"] = {"anomaly": "not_zip", "title": title, "expect": expect, "hint": hint}

    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("good")
    g.add_argument("--spec")
    g.add_argument("--out", required=True)
    g.add_argument("--name", default="good")
    g.add_argument("--rows", type=int, default=3)
    a = sub.add_parser("anomalies")
    a.add_argument("--spec")
    a.add_argument("--out", required=True)
    sub.add_parser("list-anomalies")
    args = ap.parse_args()

    if args.cmd == "list-anomalies":
        for k, (t, e, h) in ANOMALIES.items():
            print(f"{k:15s} expect={e:8s} {t} —— {h}")
        return
    spec = load_spec(args.spec)
    os.makedirs(args.out, exist_ok=True)
    if args.cmd == "good":
        print(build_good(spec, args.out, args.name, args.rows))
    else:
        m = build_anomalies(spec, args.out)
        for k, v in m.items():
            print(f"{k:28s} {v['expect']:8s} {v['title']}")


if __name__ == "__main__":
    main()
