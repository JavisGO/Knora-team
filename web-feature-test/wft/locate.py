"""定位器与变量替换。"""
import os
import re

_VAR = re.compile(r"\$\{([^}]+)\}")


def subst(value, variables, env=os.environ):
    """递归替换 ${NAME} 与 ${env:NAME}。未定义的变量原样保留并在日志里暴露。"""
    if isinstance(value, str):
        def rep(m):
            key = m.group(1)
            if key.startswith("env:"):
                return env.get(key[4:], m.group(0))
            if key in variables:
                return str(variables[key])
            return m.group(0)

        prev = None
        out = value
        for _ in range(5):  # 允许变量引用变量
            if out == prev:
                break
            prev, out = out, _VAR.sub(rep, out)
        return out
    if isinstance(value, list):
        return [subst(v, variables, env) for v in value]
    if isinstance(value, dict):
        return {k: subst(v, variables, env) for k, v in value.items()}
    return value


def unresolved(value):
    """返回 value 里仍未替换的 ${...} 列表。"""
    found = []
    if isinstance(value, str):
        found += _VAR.findall(value)
    elif isinstance(value, list):
        for v in value:
            found += unresolved(v)
    elif isinstance(value, dict):
        for v in value.values():
            found += unresolved(v)
    return found


def _xp(s):
    if "'" not in s:
        return f"'{s}'"
    if '"' not in s:
        return f'"{s}"'
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in s.split("'")) + ")"


def resolve(page, t):
    """把目标描述解析成 Playwright Locator（未取第几个）。

    目标字段（可组合）：
      within   : 另一个目标，限定在其范围内
      card     : {"contains": 文字A, "has": 文字B} 找“同时包含 A 和 B 的最近 div”（列表卡片/行常用）
      selector : CSS/XPath
      text     : 按文字匹配（exact 默认 true）
      role+name: 按 ARIA 角色与名称（name_re=true 时 name 视为正则）
      placeholder / by_label / test_id
      after_text: 取某段文字之后的第一个输入控件（tag 可改为 textarea 等）
      （注意：步骤里的 label 是给人看的描述，不参与定位；按表单标签定位用 by_label）
    """
    scope = page
    if t.get("within"):
        scope = resolve(page, t["within"]).first
    if t.get("card"):
        c = t["card"]
        xp = (f"xpath=//*[normalize-space(text())={_xp(c['contains'])}]"
              f"/ancestor::div[.//*[normalize-space(text())={_xp(c['has'])}]][1]")
        scope = scope.locator(xp).first
    if t.get("after_text"):
        # 取“最后一处出现该文字”之后的第一个输入控件（表单里标签与输入框没有关联时用；最后一处可避开列表表头同名文字）
        tag = t.get("tag", "input")
        return scope.locator(f"xpath=(//*[normalize-space(text())={_xp(t['after_text'])}])[last()]/following::{tag}[1]")
    if t.get("selector"):
        loc = scope.locator(t["selector"])
        if t.get("has_text"):
            loc = loc.filter(has_text=t["has_text"])
        return loc
    if t.get("text") is not None:
        return scope.get_by_text(t["text"], exact=t.get("exact", True))
    if t.get("role"):
        name = t.get("name")
        if name is not None and t.get("name_re"):
            name = re.compile(name)
        kw = {}
        if name is not None:
            kw["name"] = name
        return scope.get_by_role(t["role"], **kw)
    if t.get("placeholder"):
        return scope.get_by_placeholder(t["placeholder"])
    if t.get("by_label"):
        return scope.get_by_label(t["by_label"])
    if t.get("test_id"):
        return scope.get_by_test_id(t["test_id"])
    if scope is not page:
        return scope
    raise ValueError("目标描述里没有 selector/text/role/placeholder/by_label/test_id/card")


def pick(loc, t):
    """按 nth / last 选出一个元素，默认第一个。"""
    if "nth" in t:
        return loc.nth(int(t["nth"]))
    if t.get("last"):
        return loc.last
    return loc.first
