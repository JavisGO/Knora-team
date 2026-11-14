"""本地演示站点（仅用于体验 wft 流程，不是被测系统）。
用法：python server.py [端口，默认 8801]
提供：页面 index.html；GET /api/tasks；POST /api/create?name=..&runs=..（请求体是 zip 文件）。
校验规则模仿真实的“上传用例包创建任务”类功能：缺列/重复列/无有效用例/必填缺失/附件缺失/重名。
"""
import http.server
import io
import json
import os
import sys
import time
import urllib.parse
import zipfile
from email.parser import BytesParser
from email import policy

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = []
REQUIRED = "用户输入"
ATTACH = "附件"


def validate(data):
    errs = []
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return ["不是有效的 zip 文件"], 0
    names = z.namelist()
    xlsx = [n for n in names if "/" not in n and n.lower().endswith(".xlsx")]
    if len(xlsx) != 1:
        return [f"zip 根目录必须有且仅有一个 .xlsx 文件，当前有 {len(xlsx)} 个"], 0
    wb = openpyxl.load_workbook(io.BytesIO(z.read(xlsx[0])))
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    header = [str(c).strip() if c is not None else "" for c in (rows[0] if rows else [])]
    dup = sorted({h for h in header if h and header.count(h) > 1})
    if dup:
        errs.append("表头存在重复列：" + "、".join(dup))
    if REQUIRED not in header:
        errs.append(f"缺少必需列「{REQUIRED}」")
    if errs:
        return errs, 0
    ri = header.index(REQUIRED)
    ai = header.index(ATTACH) if ATTACH in header else None
    att = [n for n in names if n.startswith("attachments/") and not n.endswith("/")]
    base = {}
    for n in att:
        base.setdefault(os.path.basename(n).lower(), []).append(n)
    for k, v in base.items():
        if len(v) > 1:
            errs.append(f"附件重名（不区分大小写，含不同目录）：{os.path.basename(v[0])}")
    valid = 0
    for i, r in enumerate(rows[1:], start=2):  # i 就是 Excel 里的实际行号
        cells = list(r) + [None] * (len(header) - len(r))
        if all(c in (None, "") for c in cells):
            continue
        valid += 1
        if cells[ri] in (None, ""):
            errs.append(f"第{i}行「{REQUIRED}」：不能为空")
        if ai is not None and cells[ai] not in (None, ""):
            for f in str(cells[ai]).replace("，", ",").split(","):
                f = f.strip()
                if f and f.lower() not in base:
                    errs.append(f"第{i}行「{ATTACH}」：文件 {f} 不存在")
    if valid == 0 and not errs:
        errs.append("Excel 中没有有效用例")
    return errs, valid


class H(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # 带 Content-Length 的持久连接，和真实网关行为一致
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/api/tasks"):
            now = time.time()
            for t in TASKS:
                t["status"] = "已完成" if now - t["at"] > 3 else "运行中"
            return self._json({"statusCode": 200, "data": list(reversed(TASKS))})
        return super().do_GET()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path != "/api/create":
            return self._json({"statusCode": 404}, 404)
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        msg = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + raw)
        fields = {}
        for part in msg.iter_parts():
            fields[part.get_param("name", header="content-disposition")] = part.get_payload(decode=True)
        data = fields.get("file") or b""
        errs, n = validate(data)
        if errs:
            return self._json({"statusCode": 400, "errors": errs})  # 和不少真实系统一样：校验失败也返回 HTTP 200
        TASKS.append({"name": fields.get("name", b"").decode(), "cases": n, "runs": int(fields.get("runs", b"1") or 1),
                      "at": time.time(), "status": "运行中"})
        return self._json({"statusCode": 200, "message": "成功"})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8801
    print(f"演示站点：http://127.0.0.1:{port}/index.html  （Ctrl-C 退出）")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
