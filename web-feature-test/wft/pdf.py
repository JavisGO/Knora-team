"""把 Markdown 测试报告渲染成 PDF（图片内嵌，表格与中文正常显示）。

用法：python -m wft pdf <报告.md> [--out 报告.pdf] [--channel chrome]
图片按报告里的相对路径从报告所在目录读取。用 Playwright 驱动浏览器打印，所以不需要 pandoc/LaTeX。
"""
import argparse
import html
import os
import re
import sys

CSS = """
@page { size: A4; margin: 14mm 12mm; }
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; font-size: 12px; line-height: 1.6; color: #1f2329; }
h1 { font-size: 22px; border-bottom: 2px solid #3370ff; padding-bottom: 6px; }
h2 { font-size: 17px; margin-top: 22px; border-left: 4px solid #3370ff; padding-left: 8px; }
h3 { font-size: 14px; margin-top: 16px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; page-break-inside: auto; font-size: 11px; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #d0d3d9; padding: 4px 6px; vertical-align: top; overflow-wrap: anywhere; }
td:first-child, th:first-child { white-space: nowrap; }
th { background: #f2f4f8; }
img { max-width: 100%; max-height: 130mm; border: 1px solid #e5e6eb; margin: 3px 0; display: block; }
td img { max-width: 70mm; max-height: 55mm; }
code { background: #f2f4f8; padding: 1px 4px; border-radius: 3px; font-size: 11px; }
pre { background: #f6f7f9; padding: 8px; overflow-x: auto; }
blockquote { margin: 8px 0; padding: 4px 12px; border-left: 3px solid #c9cdd4; color: #4e5969; background: #fafafa; }
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("--out")
    ap.add_argument("--channel", default=os.environ.get("WFT_CHANNEL", "chrome"))
    args = ap.parse_args()
    try:
        import markdown
    except ImportError:
        sys.exit("缺少 markdown：pip install markdown")
    from playwright.sync_api import sync_playwright

    from .browser import launch

    src = os.path.abspath(args.report)
    out = os.path.abspath(args.out or os.path.splitext(src)[0] + ".pdf")
    text = open(src, encoding="utf-8").read()
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    base = os.path.dirname(src)
    page_html = (f'<!doctype html><html><head><meta charset="utf-8"><base href="file://{base}/">'
                 f"<style>{CSS}</style><title>{html.escape(os.path.basename(src))}</title></head><body>{body}</body></html>")
    tmp = os.path.join(base, ".wft_pdf_tmp.html")
    open(tmp, "w", encoding="utf-8").write(page_html)
    try:
        with sync_playwright() as p:
            b = launch(p, channel=args.channel, headless=True)
            pg = b.new_page()
            pg.goto("file://" + tmp, wait_until="load")
            pg.wait_for_timeout(500)
            broken = pg.evaluate("[...document.images].filter(i => !i.complete || i.naturalWidth === 0).map(i => i.getAttribute('src'))")
            pg.pdf(path=out, format="A4", print_background=True, margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"},
                   display_header_footer=True, header_template="<span></span>",
                   footer_template='<div style="font-size:9px;width:100%;text-align:center;color:#86909c"><span class="pageNumber"></span> / <span class="totalPages"></span></div>')
            n_img = pg.evaluate("document.images.length")
            b.close()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    print(f"已生成：{out}（{os.path.getsize(out) // 1024} KB，内嵌图片 {n_img} 张）")
    if broken:
        print(f"警告：{len(broken)} 张图片没能加载：{broken[:5]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
