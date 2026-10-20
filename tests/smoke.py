#!/usr/bin/env python3
"""Headless smoke test (v2): serve the repo, play index.html (mobile + desktop), embed.html (640x480) and
   embed.html inside a sandboxed iframe. Exercises pinch / wheel / button zoom, pan-without-guess, tap-to-guess.
   Screenshots -> screens/v2-*.png.     /workspace/.pwenv/bin/python tests/smoke.py"""
import http.server, json, os, socketserver, sys, threading
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "screens"); os.makedirs(SHOTS, exist_ok=True)
DATE = json.load(open(os.path.join(ROOT, "puzzles/index.json")))["dates"][0]
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(s, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(s, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), Q); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{port}"
errors, fails = [], []
def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond: fails.append(msg)

def target_xy(fr, box, aim="answer"):
    """screen coords of the answer under the current zoom"""
    st = fr.evaluate("""() => { const g = AE_DEBUG.state, r = g.P.rounds[g.i], z = AE_DEBUG.zoom;
        return {a: r.s.answer, size: g.P.size, label: r.label, k: z.k, tx: z.tx, ty: z.ty}; }""")
    x, y = st["a"]
    if aim == "off": x = min(st["size"] - 5, x + 120)
    return (box["x"] + st["tx"] + x / st["size"] * box["width"] * st["k"],
            box["y"] + st["ty"] + y / st["size"] * box["height"] * st["k"]), st

def zoomstate(fr): return fr.evaluate("() => { const z = AE_DEBUG.zoom; return {k: z.k, tx: z.tx, ty: z.ty}; }")
def locked_disabled(fr): return fr.evaluate("document.getElementById('lock').disabled")

def pinch(page, cx, cy, d0=40, d1=140, steps=8):
    cdp = page.context.new_cdp_session(page)
    def tp(d): return [{"x": cx - d / 2, "y": cy, "id": 1}, {"x": cx + d / 2, "y": cy, "id": 2}]
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": tp(d0)})
    for i in range(1, steps + 1):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": tp(d0 + (d1 - d0) * i / steps)})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
def drag_touch(page, x, y, dx, dy, steps=8):
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for i in range(1, steps + 1):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x + dx * i / steps, "y": y + dy * i / steps, "id": 1}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})

def start(page, fr, tag, shot_howto=False):
    fr.locator("#gotit").wait_for(); 
    if shot_howto: page.wait_for_timeout(300); page.screenshot(path=f"{SHOTS}/v2-{tag}-howto.png")
    fr.locator("#gotit").click(); fr.locator("#go").click(); fr.locator("#lock").wait_for()
    fr.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)")

def finish_round(page, fr, tag, n, shot=False):
    fr.locator("#lock").click(); fr.locator("#next").wait_for(); page.wait_for_timeout(350)
    if shot: page.screenshot(path=f"{SHOTS}/v2-{tag}-round{n}-reveal.png")
    sc = int(fr.locator(".verdict .big").inner_text()); word = fr.locator(".verdict .word").inner_text()
    fr.locator("#next").click(); return sc, word

def play_rest(page, fr, tag, touch, first=2):
    out = []
    for n in range(first, 6):
        fr.locator("#lock").wait_for(); fr.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)")
        box = fr.locator("#scope").bounding_box(); (x, y), st = target_xy(fr, box, "off" if n == 3 else "answer")
        if n == 2: fr.locator("#hint").click()
        (page.touchscreen.tap if touch else page.mouse.click)(x, y)
        out.append((st["label"], *finish_round(page, fr, tag, n, shot=(n == 3))))
    return out

with sync_playwright() as p:
    b = p.chromium.launch()
    # ---------- mobile: pinch zoom, one-finger pan (no guess), tap guess ----------
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
    page = ctx.new_page(); page.on("pageerror", lambda e: errors.append("mobile: " + str(e)))
    page.goto(f"{BASE}/index.html?today={DATE}"); print("mobile 390x844")
    start(page, page, "mobile", shot_howto=True)
    box = page.locator("#scope").bounding_box(); (x, y), st = target_xy(page, box)
    pinch(page, x, y); page.wait_for_timeout(200); z = zoomstate(page)
    check(2.0 <= z["k"] <= 4.0, f"pinch zoom -> k={z['k']:.2f} (clamped 1..4)")
    drag_touch(page, box["x"] + 60, box["y"] + 60, 40, 30); page.wait_for_timeout(150); z2 = zoomstate(page)
    check((z2["tx"], z2["ty"]) != (z["tx"], z["ty"]) and locked_disabled(page), "one-finger drag pans and does NOT drop a pin")
    (x, y), st = target_xy(page, box); page.touchscreen.tap(x, y); page.wait_for_timeout(200)
    check(not locked_disabled(page), "tap (no movement) while zoomed drops a pin")
    page.screenshot(path=f"{SHOTS}/v2-mobile-round1-zoomed-pin.png")
    pinch(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, 200, 10, 10); page.wait_for_timeout(150)
    check(abs(zoomstate(page)["k"] - 1) < 1e-6, "pinch out clamps at 1x")
    r1 = (st["label"], *finish_round(page, page, "mobile", 1, shot=True))
    check(r1[1] >= 90, f"round 1 after zoom+tap scored {r1[1]} ({r1[2]})")
    rest = play_rest(page, page, "mobile", touch=True)
    page.locator("#sharex").wait_for(); page.wait_for_timeout(300)
    page.screenshot(path=f"{SHOTS}/v2-mobile-end.png", full_page=True)
    print("  rounds:", [r1] + rest)
    share = page.evaluate("decodeURIComponent(document.getElementById('sharex').href.split('text=')[1])")
    print("  share:", share.replace("\n", " | ")); check(page.get_attribute("#sharex", "target") == "_blank", "share opens new tab")
    page.reload(); page.locator("#sharex").wait_for(); check(page.locator("#howto").count() == 0, "reload: results shown, how-to not repeated")
    ctx.close()

    # ---------- desktop: wheel zoom, mouse drag pan (no guess), click guess ----------
    ctx = b.new_context(viewport={"width": 1280, "height": 900}); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("desktop: " + str(e)))
    page.goto(f"{BASE}/index.html?today={DATE}"); print("desktop 1280x900")
    start(page, page, "desktop")
    box = page.locator("#scope").bounding_box(); (x, y), st = target_xy(page, box)
    page.mouse.move(x, y)
    for _ in range(6): page.mouse.wheel(0, -200); page.wait_for_timeout(40)
    z = zoomstate(page); check(z["k"] == 4, f"wheel zoom clamps at 4x (k={z['k']:.2f})")
    page.mouse.move(box["x"] + 100, box["y"] + 100); page.mouse.down(); page.mouse.move(box["x"] + 180, box["y"] + 150, steps=6); page.mouse.up()
    z2 = zoomstate(page); check((z2["tx"], z2["ty"]) != (z["tx"], z["ty"]) and locked_disabled(page), "mouse drag pans and does NOT drop a pin")
    (x, y), st = target_xy(page, box); page.mouse.click(x, y); page.wait_for_timeout(150)
    check(not locked_disabled(page), "click while zoomed drops a pin")
    page.screenshot(path=f"{SHOTS}/v2-desktop-round1-zoomed-pin.png")
    page.click("[data-z=reset]"); page.wait_for_timeout(300); check(zoomstate(page)["k"] == 1, "reset button -> 1x")
    r1 = (st["label"], *finish_round(page, page, "desktop", 1, shot=True)); check(r1[1] >= 90, f"round 1 scored {r1[1]}")
    page.locator("#info").click(); page.wait_for_timeout(100)
    print("  rounds:", [r1] + play_rest(page, page, "desktop", touch=False))
    page.locator("#sharex").wait_for(); page.screenshot(path=f"{SHOTS}/v2-desktop-end.png", full_page=True)
    ctx.close()

    # ---------- embed 640x480: +/- buttons then click ----------
    ctx = b.new_context(viewport={"width": 640, "height": 480}); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("embed: " + str(e)))
    page.goto(f"{BASE}/embed.html?today={DATE}"); print("embed 640x480")
    start(page, page, "embed", shot_howto=True)
    page.wait_for_timeout(200); page.screenshot(path=f"{SHOTS}/v2-embed-round1.png")
    page.click("[data-z=in]"); page.click("[data-z=in]"); page.wait_for_timeout(300); z = zoomstate(page)
    check(abs(z["k"] - 2.56) < 0.01, f"+ button twice -> k={z['k']:.2f}"); check(locked_disabled(page), "zoom buttons do NOT drop a pin")
    box = page.locator("#scope").bounding_box(); (x, y), st = target_xy(page, box)
    inside = box["x"] <= x <= box["x"] + box["width"] and box["y"] <= y <= box["y"] + box["height"]
    if not inside:   # answer off-screen at this zoom: zoom out once and retry
        page.click("[data-z=out]"); page.wait_for_timeout(300); (x, y), st = target_xy(page, box)
    page.mouse.click(x, y); page.wait_for_timeout(150); page.screenshot(path=f"{SHOTS}/v2-embed-round1-zoomed-pin.png")
    page.click("[data-z=out]"); page.wait_for_timeout(300)
    r1 = (st["label"], *finish_round(page, page, "embed", 1, shot=True))
    print("  rounds:", [r1] + play_rest(page, page, "embed", touch=False))
    page.locator("#sharex").wait_for(); page.wait_for_timeout(300); page.screenshot(path=f"{SHOTS}/v2-embed-end.png")
    bb = page.locator("#sharex").bounding_box(); check(bb["y"] + bb["height"] <= 336, f"embed share button bottom {bb['y'] + bb['height']:.0f}px <= 336")
    ctx.close()

    # ---------- sandboxed iframe like X (no allow-same-origin): touch pinch + tap ----------
    ctx = b.new_context(viewport={"width": 700, "height": 520}, has_touch=True); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("sandbox: " + str(e)))
    page.set_content(f'<iframe sandbox="allow-scripts allow-popups" src="{BASE}/embed.html?today={DATE}" width="640" height="480" style="border:0"></iframe>')
    print("sandboxed iframe 640x480"); fr = page.frame_locator("iframe"); frame = page.frames[1]
    start(page, fr, "sandbox")
    box = fr.locator("#scope").bounding_box(); (x, y), st = target_xy(frame, box)
    pinch(page, x, y, 30, 90); page.wait_for_timeout(200); z = zoomstate(frame)
    check(z["k"] > 1.5, f"pinch inside sandboxed iframe -> k={z['k']:.2f}")
    (x, y), st = target_xy(frame, box); page.touchscreen.tap(x, y); page.wait_for_timeout(200)
    check(not locked_disabled(frame), "tap inside sandboxed iframe drops a pin")
    page.screenshot(path=f"{SHOTS}/v2-sandbox-zoomed-pin.png")
    sc, word = finish_round(page, fr, "sandbox", 1, shot=False); check(sc >= 90, f"sandbox round 1 scored {sc} ({word})")
    page.screenshot(path=f"{SHOTS}/v2-sandbox-round2.png")
    ctx.close()

    # ---------- practice + difficulty selector + prelaunch ----------
    ctx = b.new_context(viewport={"width": 1100, "height": 900}); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("practice: " + str(e)))
    page.goto(f"{BASE}/index.html?today=2026-10-25&date={DATE}"); page.locator("#gotit").wait_for()
    check(page.locator(".tag.practice").count() == 1 and page.locator(".seg a").count() == 4, "practice day shows Mixed/Easy/Medium/Hard selector")
    page.locator("#gotit").click(); page.locator(".seg a", has_text="Hard").click(); page.locator("#go").wait_for()
    tiers = page.evaluate("AE_DEBUG.state.P.rounds.map(r => r.tier)")
    check(len(tiers) >= 1 and set(tiers) == {"hard"}, f"Hard practice set = {len(tiers)} hard rounds from past days")
    page.wait_for_timeout(300); page.screenshot(path=f"{SHOTS}/v3-practice-hard-intro.png")
    page.click("#go"); page.locator("#lock").wait_for(); page.wait_for_timeout(300)
    check(page.locator(".tier.t-hard").count() == 1, "round shows Hard tier label")
    page.screenshot(path=f"{SHOTS}/v3-practice-hard-round1.png")
    # any same-type feature counts: clicking an alternate scores like the main target
    alt = page.evaluate("""() => { for (const d of AE_INDEX.dates) { const P = AE_PUZZLES[d]; if (!P) continue;
        for (const r of P.rounds) { const s = r.s || AE_DEBUG.decode(r.secret, d); if ((s.alts || []).length)
          return [r.label, AE_DEBUG.score(s.alts[0].answer, s, r.radius_px, 3, false).score, AE_DEBUG.score(s.answer, s, r.radius_px, 3, false).score]; } } return null; }""")
    if alt: check(alt[1] >= 90 and alt[2] >= 90, f"alternate {alt[0]} scores {alt[1]} (main {alt[2]})")
    page.goto(f"{BASE}/index.html?today=2026-10-18"); page.wait_for_timeout(400); check("No puzzle" in page.locator(".task").first.inner_text(), "pre-launch screen")
    # daily sets ramp easy -> medium -> hard and are the same file for everyone
    for d in json.load(open(os.path.join(ROOT, "puzzles/index.json")))["dates"]:
        t = [r["tier"] for r in json.load(open(os.path.join(ROOT, f"puzzles/{d}.json")))["rounds"]]
        check(t == ["easy", "easy", "medium", "medium", "hard"], f"{d} ramp {t}")
    b.close()
print("JS errors:", errors or "none"); print("FAILED:" if fails else "ALL CHECKS PASSED", fails or "")
sys.exit(1 if errors or fails else 0)
