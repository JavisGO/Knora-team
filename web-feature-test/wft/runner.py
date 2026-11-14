"""声明式用例执行器。

用法：
  python -m wft run <spec.json> --out <输出目录> --state <登录态文件> [--var K=V ...]
                    [--only TC-01,TC-02] [--priority P0,P1] [--prefix R1_] [--headed]
                    [--data-dir 数据包目录] [--no-smoke-gate]

规则（写死在代码里，不靠自觉）：
  * 每个用例结束自动截图；失败/阻塞时额外截一张现场图
  * 标了 "smoke": true 的用例失败或阻塞，后续用例不再执行，标“未测（冒烟未通过）”
  * 断言（expect_*）失败 → 失败；动作异常（找不到元素/超时）→ 阻塞；没有任何断言 → 待人工判定
  * 登录态失效（被带到登录页）→ 立即停止，提示重新登录
  * 全程只在页面里操作，不读写被测系统以外的东西
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

from .browser import launch, new_context
from .locate import pick, resolve, subst, unresolved

ASSERT_PREFIX = "expect_"


class StepFail(Exception):
    """断言失败（用例判失败）。"""


class StepError(Exception):
    """动作异常（用例判阻塞）。"""


def _num(s):
    return float(re.sub(r"[,，\s]", "", str(s)))


class Runner:
    def __init__(self, spec, args, page_factory, out_dir):
        self.spec = spec
        self.args = args
        self.new_page = page_factory
        self.out = out_dir
        self.shots_dir = os.path.join(out_dir, "screenshots")
        os.makedirs(self.shots_dir, exist_ok=True)
        self.vars = {}
        self.macros = spec.get("macros", {})
        self.watch = spec.get("watch", [])
        self.page = None
        self.responses = []
        self.case = None

    # ---------- 变量 ----------
    def s(self, v):
        out = subst(v, self.vars)
        return out

    # ---------- 截图 ----------
    def shot(self, name):
        fn = f"{self.args.prefix}{name}.png"
        self.page.screenshot(path=os.path.join(self.shots_dir, fn))
        if fn not in self.case["screenshots"]:
            self.case["screenshots"].append(fn)
        return fn

    # ---------- 响应监听 ----------
    def attach(self, page):
        import re as _re

        def on_resp(r):
            for w in self.watch:
                if _re.search(w["url_re"], r.url):
                    unreadable = ""
                    try:
                        body = r.text()[:2000]
                    except Exception as e:  # noqa: BLE001
                        body = ""
                        unreadable = f"{type(e).__name__}: {str(e).splitlines()[0][:100]}"
                    self.responses.append({"name": w["name"], "url": r.url, "status": r.status, "body": body,
                                           "body_unreadable": unreadable, "at": datetime.now().isoformat(timespec="seconds")})

        page.on("response", on_resp)

    def is_mutation_success(self, r):
        for w in self.watch:
            if w["name"] == r["name"] and w.get("mutating"):
                marker = w.get("success_body_contains")
                return 200 <= r["status"] < 300 and (marker is None or marker in r["body"])
        return False

    # ---------- 步骤 ----------
    def run_steps(self, steps, log):
        for st in steps:
            self.run_step(st, log)

    def run_step(self, raw, log):
        st = self.s(raw)
        do = st.get("do")
        miss = unresolved(st)
        if miss:
            raise StepError(f"变量未定义：{', '.join(sorted(set(miss)))}（用 --var 或环境变量 ${{env:X}} 提供）")
        entry = {"do": do, "label": st.get("label") or self.describe(st), "status": "ok", "detail": ""}
        log.append(entry)
        timeout = st.get("timeout_ms", self.args.timeout)
        p = self.page
        try:
            if do == "macro":
                log.pop()
                self.run_steps(self.macros[st["name"]], log)
                return
            elif do == "goto":
                for attempt in range(3):  # 内网偶发网络切换/瞬断，重试 3 次
                    try:
                        p.goto(st["url"], wait_until=st.get("wait_until", "domcontentloaded"), timeout=60000)
                        break
                    except Exception as e:  # noqa: BLE001
                        if attempt == 2 or "net::ERR" not in str(e):
                            raise
                        p.wait_for_timeout(2000)
                self.settle()
                self.check_login()
            elif do in ("click", "dblclick", "hover", "check"):
                loc = pick(resolve(p, st), st)
                getattr(loc, {"click": "click", "dblclick": "dblclick", "hover": "hover", "check": "check"}[do])(timeout=timeout)
                p.wait_for_timeout(st.get("after_ms", 600))
            elif do == "fill":
                pick(resolve(p, st), st).fill(str(st["value"]), timeout=timeout)
            elif do == "press":
                if st.get("text") or st.get("selector") or st.get("role") or st.get("placeholder") or st.get("by_label"):
                    pick(resolve(p, st), st).press(st["key"], timeout=timeout)
                else:
                    p.keyboard.press(st["key"])
                p.wait_for_timeout(st.get("after_ms", 300))
            elif do == "upload":
                f = self.file_path(st["file"])
                sel = st.get("selector", "input[type=file]")
                p.locator(sel).nth(int(st.get("nth", 0))).set_input_files(f, timeout=timeout)
                p.wait_for_timeout(st.get("after_ms", 800))
            elif do == "wait":
                p.wait_for_timeout(int(st.get("ms", 1000)))
            elif do == "wait_text":
                self.wait_text(st, timeout)
            elif do == "wait_response":
                self.wait_response(st, timeout)
            elif do == "screenshot":
                entry["detail"] = self.shot(st["name"])
            elif do == "read":
                self.vars[st["as"]] = self.read(st)
                entry["detail"] = f"{st['as']}={self.vars[st['as']]!r}"[:200]
            elif do == "read_table":
                rows = pick_all_rows(p, st)
                self.vars[st["as"]] = rows
                entry["detail"] = f"{st['as']}: {len(rows)} 行"
            elif do == "sum_col":
                rows = self.vars[st["var"]]
                total = sum(_num(r[int(st["col"])]) for r in rows if len(r) > int(st["col"]) and re.search(r"\d", r[int(st["col"])]))
                self.vars[st["as"]] = int(total) if total == int(total) else total
                entry["detail"] = f"{st['as']}={self.vars[st['as']]}"
            elif do == "eval":
                self.vars[st["as"]] = p.evaluate(st["js"])
                entry["detail"] = f"{st['as']}={str(self.vars[st['as']])[:160]}"
            elif do == "note":
                self.case["notes"].append(st["text"])
                entry["detail"] = st["text"]
            elif do == "manual":
                self.case["manual"].append(st["text"])
                entry["detail"] = st["text"]
            elif do.startswith(ASSERT_PREFIX):
                self.assertion(do, st, entry)
            else:
                raise StepError(f"未知动作：{do}")
        except StepFail as e:
            entry["status"] = "fail"
            entry["detail"] = str(e)
            self.case["asserts_failed"] += 1
            self.case["asserts_total"] += 1
        except StepError as e:
            entry["status"] = "error"
            entry["detail"] = str(e)
            raise
        except Exception as e:  # noqa: BLE001
            msg = str(e).strip().splitlines()[0][:300] if str(e).strip() else type(e).__name__
            if st.get("optional"):
                entry["status"] = "skipped"
                entry["detail"] = f"可选步骤未执行：{msg}"
            else:
                entry["status"] = "error"
                entry["detail"] = msg
                raise StepError(f"[{entry['label']}] {msg}")
        else:
            if do.startswith(ASSERT_PREFIX):
                self.case["asserts_total"] += 1

    def describe(self, st):
        parts = [st.get("do", "?")]
        for k in ("text", "selector", "role", "name", "placeholder", "label", "value", "file", "key", "url"):
            if st.get(k) not in (None, ""):
                parts.append(f"{k}={st[k]}")
        return " ".join(str(x) for x in parts)[:120]

    def settle(self):
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:  # noqa: BLE001
            pass

    def check_login(self):
        if self.args.login_keyword in self.page.url:
            raise StepError("登录态已失效（被带到登录页），请重新执行 python -m wft login")

    def file_path(self, f):
        if os.path.isabs(f) and os.path.exists(f):
            return f
        for base in (self.args.data_dir, os.path.dirname(os.path.abspath(self.args.spec)), os.getcwd()):
            if base and os.path.exists(os.path.join(base, f)):
                return os.path.join(base, f)
        raise StepError(f"找不到文件：{f}（可用 --data-dir 指定数据目录）")

    def read(self, st):
        loc = pick(resolve(self.page, st), st)
        attr = st.get("attr", "text")
        if attr == "text":
            return loc.inner_text(timeout=self.args.timeout).strip()
        if attr == "value":
            return loc.input_value(timeout=self.args.timeout)
        if attr == "count":
            return resolve(self.page, st).count()
        if attr == "all_text":
            return [t.strip() for t in resolve(self.page, st).all_inner_texts()]
        return loc.get_attribute(attr, timeout=self.args.timeout)

    def wait_text(self, st, timeout):
        text = st["text"]
        gone = st.get("gone", False)
        scope = pick(resolve(self.page, st["within"]), st["within"]) if st.get("within") else self.page
        pat = re.compile(text) if st.get("regex") else text
        loc = scope.get_by_text(pat, exact=False).first
        loc.wait_for(state="hidden" if gone else "visible", timeout=timeout)

    def wait_response(self, st, timeout):
        end = time.time() + timeout / 1000
        while time.time() < end:
            if any(r["name"] == st["watch"] for r in self.responses):
                return
            self.page.wait_for_timeout(300)
        raise StepError(f"{timeout}ms 内没有捕获到接口 {st['watch']}")

    # ---------- 断言 ----------
    def assertion(self, do, st, entry):
        p = self.page
        t = st.get("timeout_ms", min(self.args.timeout, 6000))
        if do == "expect_text":
            scope = pick(resolve(p, st["within"]), st["within"]) if st.get("within") else p
            pat = re.compile(st["text"]) if st.get("regex") else st["text"]
            loc = scope.get_by_text(pat, exact=st.get("exact", False))
            present = st.get("present", True)
            end = time.time() + t / 1000
            found = False
            while time.time() < end:
                found = loc.count() > 0
                if found == present:
                    break
                p.wait_for_timeout(250)
            if found != present:
                raise StepFail(f"{'未找到' if present else '不应出现却出现了'}文本：{st['text']}")
            entry["detail"] = f"{'出现' if present else '未出现'}：{st['text']}"
        elif do == "expect_visible":
            loc = resolve(p, st)
            present = st.get("present", True)
            end = time.time() + t / 1000
            vis = False
            while time.time() < end:
                vis = loc.count() > 0 and pick(loc, st).is_visible()
                if vis == present:
                    break
                p.wait_for_timeout(250)
            if vis != present:
                raise StepFail(f"元素{'不可见' if present else '仍可见'}：{entry['label']}")
            entry["detail"] = "可见" if present else "不可见"
        elif do == "expect_value":
            v = pick(resolve(p, st), st).input_value(timeout=t)
            self.compare(v, st, entry, what="输入框的值")
        elif do == "expect_var":
            self.compare(self.vars.get(st["var"]), st, entry, what=f"变量 {st['var']}")
        elif do == "expect_count":
            n = resolve(p, st).count()
            ok = True
            if "equals" in st:
                ok = n == int(st["equals"])
            if "min" in st:
                ok = ok and n >= int(st["min"])
            if "max" in st:
                ok = ok and n <= int(st["max"])
            entry["detail"] = f"数量={n}"
            if not ok:
                raise StepFail(f"元素数量不符：实际 {n}，期望 {({k: st[k] for k in ('equals', 'min', 'max') if k in st})}")
        elif do == "expect_url":
            u = p.url
            if st.get("contains") and st["contains"] not in u:
                raise StepFail(f"地址不含 {st['contains']}：{u}")
            if st.get("not_contains") and st["not_contains"] in u:
                raise StepFail(f"地址不应含 {st['not_contains']}：{u}")
            entry["detail"] = u
        elif do == "expect_response":
            end = time.time() + t / 1000
            hits = []
            while time.time() < end:
                hits = [r for r in self.responses if r["name"] == st["watch"]]
                if hits:
                    break
                p.wait_for_timeout(250)
            if not hits:
                raise StepFail(f"没有捕获到接口响应：{st['watch']}")
            r = hits[-1]
            entry["detail"] = f"HTTP {r['status']} {r['body'][:160]}" + (f"（响应体读不到：{r['body_unreadable']}；改用页面提示断言）" if r.get("body_unreadable") else "")
            if "status" in st and r["status"] != int(st["status"]):
                raise StepFail(f"HTTP 状态 {r['status']}，期望 {st['status']}")
            if st.get("body_contains") and st["body_contains"] not in r["body"]:
                raise StepFail(f"响应体不含：{st['body_contains']}（实际 {r['body'][:160]}）")
            if st.get("body_not_contains") and st["body_not_contains"] in r["body"]:
                raise StepFail(f"响应体不应含：{st['body_not_contains']}（实际 {r['body'][:160]}）")
        else:
            raise StepError(f"未知断言：{do}")

    def compare(self, actual, st, entry, what):
        entry["detail"] = f"{what}={actual!r}"[:200]
        if "equals" in st and str(actual).strip() != str(st["equals"]).strip():
            raise StepFail(f"{what}应为 {st['equals']!r}，实际 {actual!r}")
        if "contains" in st and str(st["contains"]) not in str(actual):
            raise StepFail(f"{what}应包含 {st['contains']!r}，实际 {actual!r}")
        if "matches" in st and not re.search(st["matches"], str(actual)):
            raise StepFail(f"{what}应匹配 {st['matches']}，实际 {actual!r}")
        if "gte" in st and not _num(actual) >= _num(st["gte"]):
            raise StepFail(f"{what}应 ≥ {st['gte']}，实际 {actual!r}")
        if "lte" in st and not _num(actual) <= _num(st["lte"]):
            raise StepFail(f"{what}应 ≤ {st['lte']}，实际 {actual!r}")

    # ---------- 用例 ----------
    def run_case(self, case, ctx):
        self.case = {
            "id": case["id"], "title": case.get("title", ""), "priority": case.get("priority", ""),
            "requirement": case.get("requirement", ""), "expect": case.get("expect", ""),
            "status": "pass", "steps": [], "screenshots": [], "notes": [], "manual": [],
            "asserts_total": 0, "asserts_failed": 0, "error": "", "seconds": 0,
        }
        self.responses = []
        self.page = self.new_page()
        self.attach(self.page)
        t0 = time.time()
        before = case.get("before", self.spec.get("before"))
        try:
            if before:
                self.run_steps([{"do": "macro", "name": before}], self.case["steps"])
            self.run_steps(case.get("steps", []), self.case["steps"])
        except StepError as e:
            self.case["status"] = "blocked"
            self.case["error"] = str(e)
        if self.case["status"] == "pass":
            if self.case["asserts_failed"]:
                self.case["status"] = "fail"
            elif self.case["manual"] or self.case["asserts_total"] == 0:
                self.case["status"] = "manual"
        try:
            if self.case["status"] in ("fail", "blocked"):
                self.shot(f"{case['id']}_现场")
            self.shot(f"{case['id']}_结束")
        except Exception:  # noqa: BLE001
            self.case["notes"].append("截图失败（页面已关闭或崩溃）")
        # 护栏：没声明 creates 的用例如果让系统真的创建了数据，立即判失败并通知主流程停止
        if not case.get("creates"):
            made = [r for r in self.responses if self.is_mutation_success(r)]
            if made:
                self.case["status"] = "fail"
                self.case["side_effect"] = True
                self.case["notes"].append("⚠ 该用例未声明 creates，却让系统创建了数据：" + made[-1]["body"][:120])
                self.case["error"] = "产生了非预期的数据（请清理，并检查用例是否真的被拦截）"
        self.case["seconds"] = round(time.time() - t0, 1)
        self.case["responses"] = self.responses[-5:]
        try:
            self.page.close()
        except Exception:  # noqa: BLE001
            pass
        return self.case


def skipped_case(c, why):
    return {"id": c["id"], "title": c.get("title", ""), "priority": c.get("priority", ""),
            "requirement": c.get("requirement", ""), "expect": c.get("expect", ""),
            "status": "skipped", "steps": [], "screenshots": [], "notes": [why],
            "manual": [], "asserts_total": 0, "asserts_failed": 0, "error": "", "seconds": 0}


def expand_cases(cases):
    """for_each：一个用例模板 + 多组参数 → 多个用例。参数里必须有 id。"""
    import copy

    out = []
    for c in cases:
        if "for_each" not in c:
            out.append(c)
            continue
        for item in c["for_each"]:
            one = copy.deepcopy({k: v for k, v in c.items() if k != "for_each"})
            one = subst(one, {k: v for k, v in item.items()}, env={})
            one["id"] = item["id"]
            out.append(one)
    return out


def pick_all_rows(page, st):
    sel = st.get("selector", "tr")
    js = """(sel) => [...document.querySelectorAll(sel)].map(tr => [...tr.querySelectorAll('td')].map(td => td.innerText.trim()))"""
    rows = page.evaluate(js, sel)
    return [r for r in rows if r]


LABEL = {"pass": "通过", "fail": "失败", "blocked": "阻塞", "manual": "未测（待人工判定）", "skipped": "未测"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    ap.add_argument("--state", help="登录态文件（wft login 生成）")
    ap.add_argument("--no-login", action="store_true", help="被测页面不需要登录（如本地演示站点），不加载登录态")
    ap.add_argument("--var", action="append", default=[], help="覆盖/新增变量，K=V，可多次")
    ap.add_argument("--only", help="只跑这些用例编号，逗号分隔")
    ap.add_argument("--priority", help="只跑这些优先级，如 P0,P1")
    ap.add_argument("--prefix", default="R1_", help="截图文件名前缀")
    ap.add_argument("--data-dir", help="数据包目录（upload 的相对路径从这里找）")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--channel", default=os.environ.get("WFT_CHANNEL", "chrome"))
    ap.add_argument("--timeout", type=int, default=15000, help="单步超时毫秒")
    ap.add_argument("--login-keyword", default="login", help="登录页地址关键词，用于识别登录态失效")
    ap.add_argument("--no-smoke-gate", action="store_true", help="冒烟失败也继续执行（默认停止）")
    ap.add_argument("--allow-create", action="store_true", help="允许执行 creates=true 的用例（会在被测系统里新建数据）")
    ap.add_argument("--no-trace", action="store_true")
    ap.add_argument("--list", action="store_true", help="只列出用例")
    args = ap.parse_args()

    spec = json.load(open(args.spec, encoding="utf-8"))
    os.environ.setdefault("WFT_RUN_ID", datetime.now().strftime("%m%d%H%M%S"))
    cases = expand_cases(spec["cases"])
    if args.only:
        want = {x.strip() for x in args.only.split(",")}
        cases = [c for c in cases if c["id"] in want]
    if args.priority:
        want = {x.strip() for x in args.priority.split(",")}
        cases = [c for c in cases if c.get("priority") in want]
    if args.list:
        for c in cases:
            print(f"{c['id']:8s} {c.get('priority', ''):3s} {'[冒烟] ' if c.get('smoke') else '       '}{c.get('title', '')}")
        return 0
    if not cases:
        sys.exit("没有要执行的用例")
    if args.no_login:
        args.state = None
    elif not args.state:
        sys.exit("需要 --state（先 python -m wft login）；被测页面不需要登录时加 --no-login")
    elif not os.path.exists(args.state):
        sys.exit(f"登录态文件不存在：{args.state}")

    os.makedirs(args.out, exist_ok=True)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = launch(pw, channel=args.channel, headless=not args.headed)
        ctx = new_context(browser, state=args.state, trace=not args.no_trace)
        runner = Runner(spec, args, ctx.new_page, args.out)
        for kv in args.var:
            k, _, v = kv.partition("=")
            runner.vars[k] = v
        for k, v in spec.get("vars", {}).items():
            runner.vars.setdefault(k, subst(v, runner.vars))
        results, gate_closed = [], False
        started = datetime.now().isoformat(timespec="seconds")
        for c in cases:
            if gate_closed:
                results.append(skipped_case(c, "冒烟未通过，未执行"))
                print(f"{c['id']:8s} 未测（冒烟未通过）")
                continue
            if c.get("creates") and not args.allow_create:
                results.append(skipped_case(c, "会新建数据，需加 --allow-create 才执行"))
                print(f"{c['id']:8s} 未测（会新建数据，未加 --allow-create）")
                continue
            try:
                ctx.tracing.group(c["id"])
            except Exception:  # noqa: BLE001
                pass
            r = runner.run_case(c, ctx)
            try:
                ctx.tracing.group_end()
            except Exception:  # noqa: BLE001
                pass
            results.append(r)
            print(f"{r['id']:8s} {LABEL[r['status']]:10s} {r['seconds']:>5}s  {r['title']}"
                  + (f"\n         ↳ {r['error']}" if r["error"] else ""))
            for s in r["steps"]:
                if s["status"] == "fail":
                    print(f"         ✗ {s['label']}：{s['detail']}")
            if c.get("smoke") and r["status"] in ("fail", "blocked") and not args.no_smoke_gate:
                gate_closed = True
                print("         ⛔ 冒烟用例未通过，后续用例不再执行（--no-smoke-gate 可忽略）")
            if r["error"] and "登录态已失效" in r["error"]:
                gate_closed = True
            if r.get("side_effect"):
                gate_closed = True
                print("         ⛔ 检测到非预期的数据创建，已停止后续用例；请先清理并修正用例")
        finished = datetime.now().isoformat(timespec="seconds")
        if not args.no_trace:
            ctx.tracing.stop(path=os.path.join(args.out, "trace.zip"))
        browser.close()

    data = {"spec": os.path.basename(args.spec), "name": spec.get("name", ""), "started": started, "finished": finished,
            "prefix": args.prefix, "cases": results}
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    from .report import render

    md = render(data)
    with open(os.path.join(args.out, "用例明细.generated.md"), "w", encoding="utf-8") as f:
        f.write(md)
    counts = {}
    for r in results:
        counts[LABEL[r["status"]]] = counts.get(LABEL[r["status"]], 0) + 1
    print("\n汇总：" + "  ".join(f"{k}={v}" for k, v in counts.items()) + f"  合计={len(results)}")
    print(f"结果：{os.path.join(args.out, 'results.json')}\n明细：{os.path.join(args.out, '用例明细.generated.md')}")
    return 0 if all(r["status"] in ("pass", "manual", "skipped") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
