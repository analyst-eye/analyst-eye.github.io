#!/usr/bin/env python3
"""Layout screenshots at portrait / landscape / desktop sizes, plus a landscape mid-round shot.
   /workspace/.pwenv/bin/python tools/layout_shots.py <prefix>     -> screens/<prefix>-*.png
   Also prints overflow metrics (scrollWidth/scrollHeight vs viewport) for each shot."""
import http.server, os, socketserver, sys, threading
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "screens"); os.makedirs(SHOTS, exist_ok=True)
PRE = sys.argv[1] if len(sys.argv) > 1 else "layout"
DATE = "2026-10-20"
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(s, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(s, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), Q); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{port}"
METRIC = """() => { const e = document.documentElement, g = id => { const el = document.getElementById(id); if (!el) return null; const b = el.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.right), Math.round(b.bottom)]; };
  return {sw: e.scrollWidth, sh: e.scrollHeight, vw: innerWidth, vh: innerHeight, scope: g('scope'), go: g('go'), lock: g('lock'), next: g('next')}; }"""
SIZES = [("embed", 412, 860, True), ("embed", 640, 480, False), ("embed", 560, 420, False), ("embed", 915, 412, True), ("embed", 844, 390, True),
         ("site", 412, 860, True), ("site", 915, 412, True), ("site", 844, 390, True), ("site", 1280, 800, False), ("site", 640, 480, False)]
with sync_playwright() as p:
    b = p.chromium.launch()
    def ctx(w, h, mob):
        kw = dict(viewport={"width": w, "height": h}, device_scale_factor=2)
        if mob: kw.update(has_touch=True, is_mobile=True)
        c = b.new_context(**kw); c.add_init_script("localStorage.setItem('ae:howto','1')"); return c
    for kind, w, h, mob in SIZES:
        c = ctx(w, h, mob); pg = c.new_page(); page_name = "embed.html" if kind == "embed" else "index.html"
        pg.goto(f"{BASE}/{page_name}?today={DATE}"); pg.locator("#go").wait_for()
        pg.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)"); pg.wait_for_timeout(300)
        out = f"{SHOTS}/{PRE}-{kind}-{w}x{h}.png"; pg.screenshot(path=out); print(out, pg.evaluate(METRIC))
        if (w, h) in ((915, 412), (844, 390)) or (kind == "embed" and (w, h) == (640, 480)):
            pg.locator("#go").click(); pg.locator("#lock").wait_for()
            pg.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)"); pg.wait_for_timeout(1500)
            bx = pg.locator("#scope").bounding_box(); pg.mouse.click(bx["x"] + bx["width"] * .4, bx["y"] + bx["height"] * .55); pg.wait_for_timeout(200)
            out = f"{SHOTS}/{PRE}-{kind}-{w}x{h}-round.png"; pg.screenshot(path=out); print(out, pg.evaluate(METRIC))
            pg.locator("#lock").click(); pg.locator("#next").wait_for(); pg.wait_for_timeout(500)
            out = f"{SHOTS}/{PRE}-{kind}-{w}x{h}-reveal.png"; pg.screenshot(path=out); print(out, pg.evaluate(METRIC))
            for _ in range(4):
                pg.locator("#next").click(); pg.locator("#lock").wait_for(); pg.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)")
                bx = pg.locator("#scope").bounding_box(); pg.mouse.click(bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2)
                pg.locator("#lock").click(); pg.locator("#next").wait_for()
            pg.locator("#next").click(); pg.locator("#sharex").wait_for(); pg.wait_for_timeout(300)
            out = f"{SHOTS}/{PRE}-{kind}-{w}x{h}-end.png"; pg.screenshot(path=out); print(out, pg.evaluate(METRIC))
        c.close()
    b.close()
