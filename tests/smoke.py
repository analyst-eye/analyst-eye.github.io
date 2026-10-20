#!/usr/bin/env python3
"""Headless smoke test (v2): serve the repo, play index.html (mobile + desktop), embed.html (640x480) and
   embed.html inside a sandboxed iframe. Exercises pinch / wheel / button zoom, pan-without-guess, tap-to-guess.
   Screenshots -> screens/v6-*.png.     /workspace/.pwenv/bin/python tests/smoke.py"""
import datetime, http.server, json, os, socketserver, sys, threading
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "screens"); os.makedirs(SHOTS, exist_ok=True)
DATE = json.load(open(os.path.join(ROOT, "puzzles/index.json")))["dates"][0]
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(s, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(s, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), Q); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = os.environ.get("AE_BASE", f"http://127.0.0.1:{port}").rstrip("/")   # AE_BASE=https://analyst-eye.github.io to test live
LOCAL = BASE.startswith(("http://127.0.0.1", "http://localhost"))
# The live site ignores ?today= dates in the future (security fix), so off-localhost use the real US Central date.
REAL_TODAY = datetime.datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
PRACTICE_TODAY = "2026-10-25" if LOCAL else REAL_TODAY
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
    if shot_howto: page.wait_for_timeout(300); page.screenshot(path=f"{SHOTS}/v6-{tag}-howto.png")
    fr.locator("#gotit").click(); fr.locator("#go").click(); fr.locator("#lock").wait_for()
    fr.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)")

def finish_round(page, fr, tag, n, shot=False):
    fr.locator("#lock").click(); fr.locator("#next").wait_for(); page.wait_for_timeout(350)
    if shot: page.screenshot(path=f"{SHOTS}/v6-{tag}-round{n}-reveal.png")
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
    page.screenshot(path=f"{SHOTS}/v6-mobile-round1-zoomed-pin.png")
    pinch(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, 200, 10, 10); page.wait_for_timeout(150)
    check(abs(zoomstate(page)["k"] - 1) < 1e-6, "pinch out clamps at 1x")
    r1 = (st["label"], *finish_round(page, page, "mobile", 1, shot=True))
    check(r1[1] >= 90, f"round 1 after zoom+tap scored {r1[1]} ({r1[2]})")
    rest = play_rest(page, page, "mobile", touch=True)
    page.locator("#sharex").wait_for(); page.wait_for_timeout(300)
    page.screenshot(path=f"{SHOTS}/v6-mobile-end.png", full_page=True)
    check(page.locator(".rtable li").count() == 5 and page.locator("#sharetext").count() == 0 and page.locator("#scope").count() == 0,
          "end screen: one 5-row results table, no photo / share-text box")
    print("  stats line:", page.locator("#stats").inner_text())
    page.locator(".rbtn").nth(4).click(); page.wait_for_timeout(250)
    check(page.locator(".rdetail:not([hidden]) .rthumb img").count() == 1, "tapping a row shows its answer thumbnail")
    page.screenshot(path=f"{SHOTS}/v6-mobile-end-expanded.png", full_page=True)
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
    page.screenshot(path=f"{SHOTS}/v6-desktop-round1-zoomed-pin.png")
    page.click("[data-z=reset]"); page.wait_for_timeout(300); check(zoomstate(page)["k"] == 1, "reset button -> 1x")
    r1 = (st["label"], *finish_round(page, page, "desktop", 1, shot=True)); check(r1[1] >= 90, f"round 1 scored {r1[1]}")
    page.locator("#info").click(); page.wait_for_timeout(100)
    print("  rounds:", [r1] + play_rest(page, page, "desktop", touch=False))
    page.locator("#sharex").wait_for(); page.screenshot(path=f"{SHOTS}/v6-desktop-end.png", full_page=True)
    ctx.close()

    # ---------- embed 640x480: +/- buttons then click ----------
    ctx = b.new_context(viewport={"width": 640, "height": 480}); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("embed: " + str(e)))
    page.goto(f"{BASE}/embed.html?today={DATE}"); print("embed 640x480")
    start(page, page, "embed", shot_howto=True)
    page.wait_for_timeout(200); page.screenshot(path=f"{SHOTS}/v6-embed-round1.png")
    page.click("[data-z=in]"); page.click("[data-z=in]"); page.wait_for_timeout(300); z = zoomstate(page)
    check(abs(z["k"] - 2.56) < 0.01, f"+ button twice -> k={z['k']:.2f}"); check(locked_disabled(page), "zoom buttons do NOT drop a pin")
    box = page.locator("#scope").bounding_box(); (x, y), st = target_xy(page, box)
    inside = box["x"] <= x <= box["x"] + box["width"] and box["y"] <= y <= box["y"] + box["height"]
    if not inside:   # answer off-screen at this zoom: zoom out once and retry
        page.click("[data-z=out]"); page.wait_for_timeout(300); (x, y), st = target_xy(page, box)
    page.mouse.click(x, y); page.wait_for_timeout(150); page.screenshot(path=f"{SHOTS}/v6-embed-round1-zoomed-pin.png")
    page.click("[data-z=out]"); page.wait_for_timeout(300)
    r1 = (st["label"], *finish_round(page, page, "embed", 1, shot=True))
    print("  rounds:", [r1] + play_rest(page, page, "embed", touch=False))
    page.locator("#sharex").wait_for(); page.wait_for_timeout(300); page.screenshot(path=f"{SHOTS}/v6-embed-end.png")
    page.locator(".rbtn").nth(0).click(); page.wait_for_timeout(250); page.screenshot(path=f"{SHOTS}/v6-embed-end-expanded.png")
    page.locator(".rbtn").nth(0).click(); page.wait_for_timeout(150)
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
    page.screenshot(path=f"{SHOTS}/v6-sandbox-zoomed-pin.png")
    sc, word = finish_round(page, fr, "sandbox", 1, shot=False); check(sc >= 90, f"sandbox round 1 scored {sc} ({word})")
    page.screenshot(path=f"{SHOTS}/v6-sandbox-round2.png")
    ctx.close()

    # ---------- real "today" (no overrides) ----------
    ctx = b.new_context(viewport={"width": 390, "height": 844}); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("today: " + str(e)))
    page.goto(f"{BASE}/"); page.wait_for_timeout(1500)
    check(page.locator("#go").count() == 1, "today's puzzle loads at " + BASE + "/ : " + page.locator(".kicker").first.inner_text())
    title = page.locator(".ititle").inner_text(); body = page.locator("#app").inner_text()
    check(title.endswith("Things to Spy from the Sky") and "One set" not in body, f"start screen title: {title!r}")
    check(page.locator(".lineup li").count() == 5, "start screen shows a 5-step difficulty lineup")
    labels = page.evaluate("AE_DEBUG.state.P.rounds.map(r => r.label)")
    check(not any(l and l in body for l in labels), "start screen does not reveal any target names")
    ctx.close()
    # ---------- practice + difficulty selector + prelaunch ----------
    ctx = b.new_context(viewport={"width": 1100, "height": 900}); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("practice: " + str(e)))
    if PRACTICE_TODAY > DATE:
        page.goto(f"{BASE}/index.html?today={PRACTICE_TODAY}&date={DATE}"); page.locator("#gotit").wait_for()
        check(page.locator(".tag.practice").count() == 1 and page.locator(".seg a").count() == 4, "practice day shows Mixed/Easy/Medium/Hard selector")
        page.locator("#gotit").click(); page.locator(".seg a", has_text="Hard").click(); page.locator("#go").wait_for()
        tiers = page.evaluate("AE_DEBUG.state.P.rounds.map(r => r.tier)")
        check(len(tiers) >= 1 and set(tiers) == {"hard"}, f"Hard practice set = {len(tiers)} hard rounds from past days")
        page.wait_for_timeout(300); page.screenshot(path=f"{SHOTS}/v6-practice-hard-intro.png")
        page.click("#go"); page.locator("#lock").wait_for(); page.wait_for_timeout(300)
        check(page.locator(".tier.t-hard").count() == 1, "round shows Hard tier label")
        page.screenshot(path=f"{SHOTS}/v6-practice-hard-round1.png")
    else:
        print(f"  skip practice checks: no past puzzle yet on {BASE} (today {PRACTICE_TODAY})")
        page.goto(f"{BASE}/index.html?today={DATE}"); page.locator("#go").wait_for()
    # any same-type feature counts: clicking an alternate scores like the main target
    alt = page.evaluate("""() => { for (const d of AE_INDEX.dates) { const P = AE_PUZZLES[d]; if (!P) continue;
        for (const r of P.rounds) { const s = r.s || AE_DEBUG.decode(r.secret, d); if ((s.alts || []).length)
          return [r.label, AE_DEBUG.score(s.alts[0].answer, s, r.radius_px, 3, false).score, AE_DEBUG.score(s.answer, s, r.radius_px, 3, false).score]; } } return null; }""")
    if alt: check(alt[1] >= 90 and alt[2] >= 90, f"alternate {alt[0]} scores {alt[1]} (main {alt[2]})")
    page.goto(f"{BASE}/index.html?today=2026-10-18"); page.wait_for_timeout(400); check("No puzzle" in page.locator(".task").first.inner_text(), "pre-launch screen")
    ctx.close()
    # ---------- decoy rounds: a pin on a look-alike scores 0 and explains the difference ----------
    found = None
    for d in json.load(open(os.path.join(ROOT, "puzzles/index.json")))["dates"]:
        if not (LOCAL or d <= REAL_TODAY): continue
        for r in json.load(open(os.path.join(ROOT, f"puzzles/{d}.json")))["rounds"]:
            if r.get("caution"): found = (d, r["round"]); break
        if found: break
    if not found: print("  skip decoy checks: no decoy round reachable on", BASE)
    for vp, tag, embed in (({"width": 390, "height": 844}, "mobile", False), ({"width": 640, "height": 480}, "embed", True)):
        if not found: break
        d, n = found
        ctx = b.new_context(viewport=vp, device_scale_factor=2 if not embed else 1, has_touch=not embed, is_mobile=not embed); page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(f"decoy-{tag}: " + str(e)))
        prev = [{"d": 0, "acc": 80, "speed": 10, "hint": False, "score": 90, "t": 6, "ti": 0, "click": [100, 100], "dk": -1}] * (n - 1)
        page.add_init_script(f"localStorage.setItem('ae:howto','1'); localStorage.setItem('ae:day:{d}', JSON.stringify({json.dumps({'results': prev, 'done': False})}));")
        page.goto(f"{BASE}/{'embed' if embed else 'index'}.html?today={d}"); page.locator("#lock").wait_for()
        page.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)"); page.wait_for_timeout(300)
        cau = page.locator(".caution").inner_text(); check(cau.startswith("Careful:"), f"{tag}: decoy round shows caution line: {cau!r}")
        page.screenshot(path=f"{SHOTS}/v8-{tag}-decoy-round.png")
        box = page.locator("#scope").bounding_box()
        st = page.evaluate("() => { const g = AE_DEBUG.state, r = g.P.rounds[g.i]; return {a: r.s.decoys[0].answer, size: g.P.size, clue: r.s.decoys[0].clue}; }")
        x = box["x"] + st["a"][0] / st["size"] * box["width"]; y = box["y"] + st["a"][1] / st["size"] * box["height"]
        (page.touchscreen.tap if not embed else page.mouse.click)(x, y); page.wait_for_timeout(200)
        page.locator("#lock").click(); page.locator("#next").wait_for(); page.wait_for_timeout(400)
        word = page.locator(".verdict .word").inner_text(); sc = int(page.locator(".verdict .big").inner_text())
        check(word == "Decoy!" and sc == 0 and st["clue"] in page.locator(".side").inner_text(), f"{tag}: tapping the decoy -> {word} {sc} with clue")
        page.screenshot(path=f"{SHOTS}/v8-{tag}-decoy-hit.png")
        ctx.close()
    # the real target still scores in a decoy round (pure function check)
    ctx = b.new_context(); page = ctx.new_page(); page.goto(f"{BASE}/index.html?today={found[0] if found else DATE}"); page.wait_for_timeout(500)
    if found:
        res = page.evaluate(f"""() => {{ const P = AE_PUZZLES['{found[0]}'], r = P.rounds[{found[1] - 1}], s = AE_DEBUG.decode(r.secret, '{found[0]}');
            return [AE_DEBUG.score(s.answer, s, r.radius_px, 3, false), AE_DEBUG.score(s.decoys[0].answer, s, r.radius_px, 3, false)]; }}""")
        check(res[0]["score"] >= 90 and res[0]["dk"] == -1 and res[1]["score"] == 0 and res[1]["dk"] == 0, f"decoy round: target scores {res[0]['score']}, decoy scores {res[1]['score']}")
    # today's live (pre-decoy) Oct 20 file still loads and plays with the decoy-aware app
    page.goto(f"{BASE}/index.html?today=2026-10-20"); page.wait_for_timeout(600)
    r20 = page.evaluate("() => { const P = AE_PUZZLES['2026-10-20']; if (!P) return null; const r = P.rounds[0], s = AE_DEBUG.decode(r.secret, '2026-10-20'); return [P.rounds.length, AE_DEBUG.score(s.answer, s, r.radius_px, 3, false).score, (s.decoys || []).length]; }")
    check(bool(r20) and r20[0] == 5 and r20[1] >= 90 and r20[2] == 0, f"Oct 20 old-format puzzle loads and scores: {r20}")
    ctx.close()
    # ---------- relaunch: Oct 20 is Puzzle #1 (start, embed, result title, share text); old Oct 19 saves don't break stats ----------
    L = json.load(open(os.path.join(ROOT, "puzzles/index.json")))
    check(L["launch"] == "2026-10-20" and L["dates"][0] == "2026-10-20" and "2026-10-19" not in L["dates"], f"index launch {L['launch']}, first {L['dates'][0]}")
    for d in L["dates"]:
        n = json.load(open(os.path.join(ROOT, f"puzzles/{d}.json")))["number"]
        want = (datetime.date.fromisoformat(d) - datetime.date(2026, 10, 20)).days + 1
        check(n == want, f"{d} number {n} (want {want})")
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("n1: " + str(e)))
    page.add_init_script("localStorage.setItem('ae:howto','1')")
    page.goto(f"{BASE}/index.html?today=2026-10-20"); page.locator("#go").wait_for(); page.wait_for_timeout(500)
    k = page.locator(".kicker").first.inner_text(); check(k.upper().startswith("PUZZLE #1 ·"), f"start kicker {k!r}")
    page.screenshot(path=f"{SHOTS}/n1-today.png")
    ctx.close()
    ctx = b.new_context(viewport={"width": 640, "height": 480}); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("n1-embed: " + str(e)))
    page.goto(f"{BASE}/embed.html?today=2026-10-20"); page.locator("#go").wait_for(); page.wait_for_timeout(300)
    k = page.locator(".kicker").first.inner_text(); check(k.upper().startswith("PUZZLE #1 ·"), f"embed kicker {k!r}")
    ctx.close()
    # a player who played the never-announced Oct 19 set: saved stats + day record, then finishes Oct 20
    legacy = {"played": 1, "streak": 1, "maxStreak": 1, "best": 320, "bestDate": "2026-10-19", "last": "2026-10-19", "hist": {"2026-10-19": 320}}
    res = [{"d": 0, "acc": 80, "speed": 10, "hint": False, "score": 90, "t": 6, "ti": 0, "click": [100, 100], "dk": -1}] * 4
    ctx = b.new_context(viewport={"width": 390, "height": 844}); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("n1-legacy: " + str(e)))
    page.add_init_script(f"if (!sessionStorage.getItem('seeded')) {{ sessionStorage.setItem('seeded','1'); localStorage.setItem('ae:howto','1'); localStorage.setItem('ae:stats', {json.dumps(json.dumps(legacy))}); localStorage.setItem('ae:day:2026-10-19', JSON.stringify({{results: [], done: true}})); localStorage.setItem('ae:day:2026-10-20', JSON.stringify({{results: {json.dumps(res)}, done: false}})); }}")
    page.goto(f"{BASE}/index.html?today=2026-10-20"); page.locator("#lock").wait_for()   # resumes at round 5
    page.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)"); page.wait_for_timeout(300)
    box = page.locator("#scope").bounding_box(); page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2); page.wait_for_timeout(200)
    page.locator("#lock").click(); page.locator("#next").wait_for(); page.locator("#next").click(); page.locator(".rhead .kicker").wait_for()
    t = page.locator(".rhead .kicker").inner_text(); check(t.upper().startswith("ANALYST EYE #1 ·"), f"result title {t!r}")
    href = page.locator("#sharex").get_attribute("href"); from urllib.parse import unquote
    check("Analyst Eye #1 " in unquote(href) and "#0" not in unquote(href), f"share text {unquote(href).split('text=')[1].splitlines()[0]!r}")
    st = page.evaluate("() => JSON.parse(localStorage.getItem('ae:stats'))")
    check(st["played"] == 2 and st["streak"] == 2 and st["last"] == "2026-10-20", f"legacy Oct 19 stats carry on: played {st['played']} streak {st['streak']}")
    check("#0 " not in page.locator("body").inner_text(), "no #0 in the results page text")
    ctx.close()
    # ---------- v9 layout: landscape split (photo beside panel), square photo everywhere ----------
    VIS = """sel => { const el = document.querySelector(sel); if (!el) return false; const b = el.getBoundingClientRect();
        return b.width > 0 && b.top >= 0 && b.left >= 0 && b.bottom <= innerHeight + 0.5 && b.right <= innerWidth + 0.5; }"""
    OVER = "() => ({sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, vw: innerWidth, vh: innerHeight, split: document.body.classList.contains('split')})"
    SQ = "() => { const b = document.getElementById('scope').getBoundingClientRect(); return [b.width, b.height]; }"
    for kind, w, h, mob, want_split in [("embed", 640, 480, False, True), ("embed", 560, 420, False, True), ("embed", 915, 412, True, True), ("embed", 844, 390, True, True),
                                        ("embed", 412, 860, True, False), ("site", 844, 390, True, True), ("site", 915, 412, True, True),
                                        ("site", 412, 860, True, False), ("site", 1280, 800, False, False)]:
        kw = dict(viewport={"width": w, "height": h})
        if mob: kw.update(has_touch=True, is_mobile=True)
        ctx = b.new_context(**kw); page = ctx.new_page(); tag = f"{kind} {w}x{h}"
        page.on("pageerror", lambda e, tag=tag: errors.append(tag + ": " + str(e)))
        page.add_init_script("localStorage.setItem('ae:howto','1')")
        page.goto(f"{BASE}/{'embed' if kind == 'embed' else 'index'}.html?today={REAL_TODAY if not LOCAL else '2026-10-20'}")
        page.locator("#go").wait_for(); page.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)"); page.wait_for_timeout(250)
        o = page.evaluate(OVER); sw, sh = page.evaluate(SQ)
        check(o["split"] == want_split, f"{tag}: {'split' if want_split else 'stacked'} layout")
        check(o["sw"] <= o["vw"], f"{tag}: no horizontal overflow ({o['sw']} <= {o['vw']})")
        if kind == "embed" and want_split: check(o["sh"] <= o["vh"], f"{tag}: fills the frame, no vertical scroll ({o['sh']} <= {o['vh']})")
        check(abs(sw - sh) < 1.5, f"{tag}: photo is square ({sw:.0f}x{sh:.0f})")
        check(page.evaluate(VIS, "#go"), f"{tag}: Play button visible without scrolling")
        if kind == "embed" and not want_split:
            lb = page.locator(".lineup").bounding_box(); check(abs(lb["x"] + lb["width"] / 2 - w / 2) < 3, f"{tag}: difficulty strip centered")
        if want_split:
            check(page.evaluate(VIS, ".lineup") and page.evaluate(VIS, ".ititle"), f"{tag}: title + strip visible")
            sd = page.evaluate("() => { const s = document.querySelector('.side'); return [s.scrollWidth, s.clientWidth, s.scrollHeight, s.clientHeight]; }")
            check(sd[0] <= sd[1] and sd[2] <= sd[3], f"{tag}: start panel content fits, nothing clipped ({sd})")
            page.locator("#go").click(); page.locator("#lock").wait_for(); page.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)"); page.wait_for_timeout(300)
            check(all(page.evaluate(VIS, s_) for s_ in ("#scope", "#lock", "#hint", ".timer")), f"{tag}: round: photo, timer, Hint, Lock in all on screen")
            bx = page.locator("#scope").bounding_box(); cx, cy = bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2
            if mob: pinch(page, cx, cy); page.wait_for_timeout(150)
            else:
                page.mouse.move(cx, cy)
                for _ in range(3): page.mouse.wheel(0, -200); page.wait_for_timeout(40)
            check(zoomstate(page)["k"] > 1.5, f"{tag}: zoom works ({zoomstate(page)['k']:.2f}x)")
            page.click("[data-z=reset]"); page.wait_for_timeout(350)
            (x, y), st = target_xy(page, bx); (page.touchscreen.tap if mob else page.mouse.click)(x, y); page.wait_for_timeout(200)
            check(not locked_disabled(page), f"{tag}: tap drops a pin")
            if (kind, w) == ("site", 844): page.screenshot(path=f"{SHOTS}/v9-site-844x390-round-zoomed.png")
            page.locator("#lock").click(); page.locator("#next").wait_for(); page.wait_for_timeout(300)
            sc = int(page.locator(".verdict .big").inner_text())
            check(sc >= 80 and page.evaluate(VIS, "#next"), f"{tag}: result {sc} with Next on screen")
            for _ in range(4):
                page.locator("#next").click(); page.locator("#lock").wait_for(); page.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)")
                bx = page.locator("#scope").bounding_box(); page.mouse.click(bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2)
                page.locator("#lock").click(); page.locator("#next").wait_for()
            page.locator("#next").click(); page.locator("#sharex").wait_for(); page.wait_for_timeout(200)
            o = page.evaluate(OVER)
            check(page.locator(".rtable li").count() == 5 and o["sw"] <= o["vw"] and page.evaluate(VIS, "#sharex"), f"{tag}: end screen 5 rows, Share visible, no sideways scroll")
        ctx.close()
    # daily sets ramp easy -> medium -> hard and are the same file for everyone
    for d in json.load(open(os.path.join(ROOT, "puzzles/index.json")))["dates"]:
        t = [r["tier"] for r in json.load(open(os.path.join(ROOT, f"puzzles/{d}.json")))["rounds"]]
        check(t == ["easy", "easy", "medium", "medium", "hard"], f"{d} ramp {t}")
    b.close()
print("JS errors:", errors or "none"); print("FAILED:" if fails else "ALL CHECKS PASSED", fails or "")
sys.exit(1 if errors or fails else 0)
