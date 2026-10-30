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
    CH = "/opt/ungoogled-chromium/chrome"; b = p.chromium.launch(executable_path=CH, args=["--no-sandbox"]) if os.path.exists(CH) else p.chromium.launch()
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
    # Oct 21 fix: footprint scoring. Marina = multipolygon outline + its docks; "sports field" also accepts the baseball diamonds
    page.goto(f"{BASE}/index.html?today=2026-10-21"); page.wait_for_timeout(600)
    fp = page.evaluate("""() => { const P = AE_PUZZLES['2026-10-21']; if (!P) return null; const dc = i => AE_DEBUG.decode(P.rounds[i].secret, '2026-10-21');
        const m = dc(0), f = dc(1), R = i => P.rounds[i].radius_px, sc = (p, s, i) => AE_DEBUG.score(p, s, R(i), 3, false).score;
        const dock = m.parts.find(q => q.gtype === 'line'), ball = (f.alts || []).find(a => a.kind === 'baseball');
        return [m.gtype, m.geom.length, sc(dock.geom[0], m, 0), sc(m.answer, m, 0), ball ? sc(ball.answer, f, 1) : -1, sc([700, 700], f, 1)]; }""")
    check(bool(fp) and fp[0] == "polygon" and fp[1] > 3 and fp[2] >= 90 and fp[3] >= 90 and fp[4] >= 90 and fp[5] == 0,
          f"Oct 21 footprint scoring (marina polygon + docks, baseball diamond counts as sports field, empty spot misses): {fp}")
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
    # ---------- v10: Home + unscored "Play again" of today's set ----------
    TD = REAL_TODAY if not LOCAL else "2026-10-20"
    TOMORROW = (datetime.date.fromisoformat(TD) + datetime.timedelta(days=1)).isoformat()
    SAVED = "() => [localStorage.getItem('ae:stats'), localStorage.getItem('ae:day:%s')]" % TD
    def play5(page, aim=True):
        for n in range(5):
            page.locator("#lock").wait_for(); page.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)")
            bx = page.locator("#scope").bounding_box()
            if aim: (x, y), _ = target_xy(page, bx)
            else: x, y = bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2
            page.mouse.click(x, y); page.locator("#lock").click(); page.locator("#next").wait_for(); page.locator("#next").click()
        page.locator("#sharex").wait_for(); page.wait_for_timeout(200)
    for kind, w, h, mob in [("site", 390, 844, True), ("site", 844, 390, True), ("embed", 640, 480, False)]:
        kw = dict(viewport={"width": w, "height": h})
        if mob: kw.update(has_touch=True, is_mobile=True, device_scale_factor=2)
        ctx = b.new_context(**kw); page = ctx.new_page(); tag = f"replay {kind} {w}x{h}"; sfx = f"{kind}-{w}x{h}"
        page.on("pageerror", lambda e, tag=tag: errors.append(tag + ": " + str(e)))
        page.add_init_script("localStorage.setItem('ae:howto','1')")
        url = f"{BASE}/{'embed' if kind == 'embed' else 'index'}.html?today={TD}"
        # scored game: no Home mid-round (no peek-and-restart), Home on the reveal -> start screen offers Continue
        page.goto(url); page.locator("#go").wait_for(); page.locator("#go").click(); page.locator("#lock").wait_for()
        check(page.locator("#home").count() == 0, f"{tag}: no Home link mid-round of the scored game")
        bx = page.locator("#scope").bounding_box(); (x, y), _ = target_xy(page, bx); page.mouse.click(x, y)
        page.locator("#lock").click(); page.locator("#next").wait_for()
        page.locator("#home").click(); page.locator("#go").wait_for()
        check("Continue" in page.locator("#go").inner_text() and page.evaluate("AE_DEBUG.state.results.length") == 1, f"{tag}: Home after a round -> start screen, {page.locator('#go').inner_text()!r}")
        page.locator("#go").click(); page.locator("#lock").wait_for()
        check(page.evaluate("AE_DEBUG.state.i") == 1, f"{tag}: Continue resumes at round 2")
        page.locator("#next").count() or None
        # finish the scored game (rounds 2-5)
        for n in range(4):
            page.locator("#lock").wait_for(); page.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)")
            bx = page.locator("#scope").bounding_box(); (x, y), _ = target_xy(page, bx); page.mouse.click(x, y)
            page.locator("#lock").click(); page.locator("#next").wait_for(); page.locator("#next").click()
        page.locator("#sharex").wait_for(); page.wait_for_timeout(250)
        before = page.evaluate(SAVED); st0 = json.loads(before[0]); total0 = int(page.locator(".total b").inner_text())
        check(st0["played"] == 1 and page.locator("#homebtn").is_visible() and page.locator("#again").is_visible(), f"{tag}: end screen has Home + Play again (scored {total0}, played {st0['played']})")
        if kind == "embed": check(page.evaluate(VIS, "#homebtn"), f"{tag}: Home visible without scrolling in the 640x480 frame")
        page.screenshot(path=f"{SHOTS}/v10-{sfx}-end.png", full_page=(kind != "embed"))
        # Home -> start screen in the done state; reload still opens the results
        page.locator("#homebtn").click(); page.locator("#results").wait_for(); page.wait_for_timeout(300)
        check(page.locator("#go").count() == 0 and page.locator(".ititle").is_visible() and page.locator(".lineup li").count() == 5,
              f"{tag}: Home -> start screen (title, strip), Play replaced by See results / Play again")
        check(page.evaluate(VIS, "#results") and page.evaluate(VIS, "#again"), f"{tag}: See results + Play again visible without scrolling")
        if kind == "site" and h > w: check(page.locator(".istats").is_visible(), f"{tag}: stats shown on the start screen")
        page.screenshot(path=f"{SHOTS}/v10-{sfx}-start-done.png")
        page.locator("#results").click(); page.locator("#sharex").wait_for()
        check(int(page.locator(".total b").inner_text()) == total0, f"{tag}: See results shows the saved score {total0}")
        page.reload(); page.locator("#sharex").wait_for(); check(page.locator(".tag.practice").count() == 0, f"{tag}: reload after finishing still opens the scored results")
        # Play again: unscored replay of all 5 rounds
        page.locator("#again").click(); page.locator("#lock").wait_for(); page.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)"); page.wait_for_timeout(250)
        g = page.evaluate("({p: AE_DEBUG.state.practice, ds: AE_DEBUG.state.ds, i: AE_DEBUG.state.i, n: AE_DEBUG.state.results.length})")
        check(g["p"] and g["ds"] == TD and g["i"] == 0 and g["n"] == 0 and page.locator(".hud .tag.practice").count() == 1, f"{tag}: Play again starts round 1 of today's set as practice {g}")
        page.screenshot(path=f"{SHOTS}/v10-{sfx}-replay-round1.png")
        # brand Home mid-replay returns to the start screen; Play again from there
        page.locator("#home").click(); page.locator("#again").wait_for(); page.locator("#again").click(); page.locator("#lock").wait_for()
        play5(page, aim=False)
        share = page.evaluate("decodeURIComponent(document.getElementById('sharex').href.split('text=')[1])")
        check("(practice)" in share.splitlines()[0] and "🔥" not in share, f"{tag}: replay share text marked practice: {share.splitlines()[0]!r}")
        check("Practice" in page.locator("#stats").inner_text(), f"{tag}: replay results say practice doesn't count")
        after = page.evaluate(SAVED)
        check(after == before, f"{tag}: saved results, score, streak, best, played unchanged after replay")
        page.locator("#homebtn").click(); page.locator("#results").wait_for(); page.locator("#results").click(); page.locator("#sharex").wait_for()
        check(int(page.locator(".total b").inner_text()) == total0 and page.locator(".tag.practice").count() == 0, f"{tag}: Home -> See results still shows scored {total0}")
        ctx.close()
    # URL guards: ?date=today is a replay only once finished; the future never unlocks
    ctx = b.new_context(viewport={"width": 390, "height": 844}); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("guards: " + str(e)))
    page.add_init_script("localStorage.setItem('ae:howto','1')")
    page.goto(f"{BASE}/index.html?today={TD}&date={TD}"); page.locator("#go").wait_for()
    check(not page.evaluate("AE_DEBUG.state.practice"), "?date=today before finishing -> the scored game, not a practice peek")
    page.goto(f"{BASE}/index.html?today={TD}&date={TOMORROW}"); page.locator("#go").wait_for()
    check(page.evaluate("AE_DEBUG.state.ds") == TD, f"?date={TOMORROW} (future) is ignored")
    if not LOCAL:
        page.goto(f"{BASE}/index.html?today={TOMORROW}&date={TOMORROW}"); page.locator("#go").wait_for()
        check(page.evaluate("AE_DEBUG.state.ds") == TD, "live: ?today=<future> is ignored")
    seed = json.dumps(json.dumps({"results": [{"d": 0, "acc": 80, "speed": 10, "hint": False, "score": 90, "t": 6, "ti": 0, "click": [100, 100], "dk": -1}] * 5, "done": True}))
    page.evaluate(f"localStorage.setItem('ae:day:{TD}', {seed})")
    page.goto(f"{BASE}/index.html?today={TD}&date={TD}"); page.locator("#lock, #go").first.wait_for()
    check(page.evaluate("AE_DEBUG.state.practice") and page.evaluate("AE_DEBUG.state.ds") == TD, "?date=today after finishing -> unscored replay")
    page.goto(f"{BASE}/index.html?today={TD}&practice=easy"); page.wait_for_timeout(800)
    txt = page.locator("#app").inner_text()
    check(page.locator("#go").count() == 1 or "No easy rounds to practice yet" in txt, "practice-by-difficulty URL still renders: " + " ".join(txt.split())[:70])
    ctx.close()
    # ---------- v11: challenge links (?c=) + per-day pages (p/DATE.html) ----------
    import base64, struct
    from urllib.parse import urlparse, parse_qs
    def mkc(total, rounds, ver=1):
        b_ = bytes([ver]) + struct.pack(">H", total) + b"".join(bytes([sc]) + struct.pack(">H", t) for sc, t in rounds)
        return base64.urlsafe_b64encode(b_).decode().rstrip("=")
    C430 = mkc(430, [(95, 31), (90, 52), (85, 120), (80, 88), (80, 300)])
    ctx = b.new_context(viewport={"width": 390, "height": 844}); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("chal-parse: " + str(e)))
    page.goto(f"{BASE}/index.html?today={TD}"); page.locator("#go").wait_for()
    got = page.evaluate(f"AE_DEBUG.parseChal('{C430}')")
    check(got and got["total"] == 430 and [r["t"] for r in got["rounds"]] == [3.1, 5.2, 12, 8.8, 30] and got["rounds"][0]["score"] == 95, f"parseChal decodes total + per-round times: {got}")
    rt = page.evaluate("""() => { const res = [{score: 100, t: 3.14}, {score: 0, t: 45}, {score: 77, t: 0}, {score: 40, t: 999}, {score: 63, t: 12.3}];
        return AE_DEBUG.parseChal(AE_DEBUG.encChal(res)); }""")
    check(rt["total"] == 280 and [r["t"] for r in rt["rounds"]] == [3.1, 45, 0, 600, 12.3], f"encChal -> parseChal round trip (times clamped to 600s): {rt}")
    clamp = page.evaluate(f"AE_DEBUG.parseChal('{mkc(65535, [(255, 65535)] * 5)}')")
    check(clamp["total"] == 500 and all(r["score"] == 100 and r["t"] == 600 for r in clamp["rounds"]), f"out-of-range values are clamped: total {clamp['total']}")
    bad = ["", "abc", "!!!!!!!!", "A" * 65, mkc(430, [(90, 30)] * 5, ver=2), mkc(430, []), mkc(430, [(90, 30)] * 11), "AQGuX", "AQGuXw-_AQ", "<script>alert(1)</script>", "AQGu%00%00", None, 12345]
    res = page.evaluate("bad => bad.map(v => AE_DEBUG.parseChal(v))", bad)
    check(all(r is None for r in res), f"malformed ?c= values are ignored: {res}")
    ctx.close()
    # challenged start screen + comparison end screen on today's per-day page
    PN = (datetime.date.fromisoformat(TD) - datetime.date(2026, 10, 20)).days + 1
    for kind, w, h, mob in [("site", 390, 844, True), ("site", 844, 390, True)]:
        kw = dict(viewport={"width": w, "height": h})
        if mob: kw.update(has_touch=True, is_mobile=True, device_scale_factor=2)
        ctx = b.new_context(**kw); page = ctx.new_page(); tag = f"challenge {w}x{h}"
        page.on("pageerror", lambda e, tag=tag: errors.append(tag + ": " + str(e)))
        page.add_init_script("localStorage.setItem('ae:howto','1')")
        page.goto(f"{BASE}/p/{TD}.html?today={TD}&c={C430}"); page.locator("#go").wait_for()
        page.locator("#img").evaluate("i => i.complete || new Promise(r => i.onload = r)"); page.wait_for_timeout(300)
        chal = page.locator("#chal").inner_text() if page.locator("#chal").count() else ""
        check(chal == "A friend scored 430. Can you beat it?", f"{tag}: start screen shows the challenge: {chal!r}")
        g = page.evaluate("({p: AE_DEBUG.state.practice, ds: AE_DEBUG.state.ds})")
        check(not g["p"] and g["ds"] == TD and page.locator(".kicker").first.inner_text().upper().startswith(f"PUZZLE #{PN} "), f"{tag}: today's per-day page opens the normal scored game {g}")
        check(page.evaluate(VIS, "#go") and page.evaluate(VIS, "#chal"), f"{tag}: Play + challenge line visible without scrolling")
        if w > h:
            sd = page.evaluate("() => { const s = document.querySelector('.side'); return [s.scrollWidth, s.clientWidth, s.scrollHeight, s.clientHeight]; }")
            check(sd[0] <= sd[1] and sd[2] <= sd[3], f"{tag}: start panel still fits with the challenge line ({sd})")
        page.screenshot(path=f"{SHOTS}/v11-{w}x{h}-challenge-start.png")
        page.locator("#go").click(); play5(page, aim=True)
        total = int(page.locator(".total b").inner_text()); vs = page.locator("#vs").inner_text()
        want = f"You beat them by {total - 430}" if total > 430 else f"{430 - total} short" if total < 430 else "Tied"
        check(vs == f"Friend: 430 · {want}", f"{tag}: end screen compares: {vs!r} (scored {total})")
        page.screenshot(path=f"{SHOTS}/v11-{w}x{h}-challenge-end.png", full_page=(w < h))
        share = page.evaluate("decodeURIComponent(document.getElementById('sharex').href.split('text=')[1])")
        lines = share.splitlines(); link = lines[-1]; body = "\n".join(lines[:-1])
        print("  share:", share.replace("\n", " | "))
        check(lines[0].startswith(f"Analyst Eye #{PN} 🛰️ {total}/500") and lines[-2].endswith("Beat me:") and lines[-2].startswith("I found the "), f"{tag}: share is a dare: {lines[-2]!r}")
        check(len(body) <= 200, f"{tag}: share text before the link is {len(body)} chars (<= 200)")
        u = urlparse(link); c = parse_qs(u.query).get("c", [""])[0]
        check(u.path.endswith(f"/p/{TD}.html") and bool(c), f"{tag}: share link is the per-day page with ?c=: {link}")
        dec = page.evaluate("c => AE_DEBUG.parseChal(c)", c)
        check(bool(dec) and dec["total"] == total and len(dec["rounds"]) == 5, f"{tag}: share link encodes this score ({dec and dec['total']})")
        if w < h:
            # reopening the challenge after finishing -> straight to results with the comparison; Home -> site root
            page.goto(f"{BASE}/p/{TD}.html?today={TD}&c={C430}"); page.locator("#sharex").wait_for()
            check(page.locator("#vs").count() == 1 and page.locator(".tag.practice").count() == 0, f"{tag}: challenge link after finishing opens scored results + comparison")
            page.locator("#homebtn").click(); page.locator("#results").wait_for()
            check(urlparse(page.url).path in ("/", "/index.html") and "c=" not in page.url, f"{tag}: Home from a per-day page goes to the site root: {page.url}")
            # replay of today shares a plain per-day link (no dare: the answers were already seen)
            page.locator("#again").click(); play5(page, aim=False)
            sh = page.evaluate("decodeURIComponent(document.getElementById('sharex').href.split('text=')[1])")
            check("c=" not in sh and "Beat me" not in sh and sh.splitlines()[-1].endswith(f"/p/{TD}.html"), f"replay share: plain per-day link, no challenge: {sh.splitlines()[-1]}")
        ctx.close()
    # malformed ?c= on a per-day page: no challenge line, no errors, game still works
    ctx = b.new_context(viewport={"width": 390, "height": 844}); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append("chal-bad: " + str(e)))
    page.add_init_script("localStorage.setItem('ae:howto','1')")
    for v in ["%3Cimg%20src%3Dx%3E", "AQGu", "____________", mkc(430, [(90, 30)] * 5, ver=7)]:
        page.goto(f"{BASE}/p/{TD}.html?today={TD}&c={v}"); page.locator("#go").wait_for()
        check(page.locator("#chal").count() == 0 and page.locator("img[src=x]").count() == 0, f"bad c={v[:16]}: ignored")
    ctx.close()
    # past day page -> the past day (as practice, like ?date=), with the challenge; future day page -> today, no challenge
    if LOCAL:
        ctx = b.new_context(viewport={"width": 390, "height": 844}); page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append("day-pages: " + str(e)))
        page.add_init_script("localStorage.setItem('ae:howto','1')")
        page.goto(f"{BASE}/p/2026-10-20.html?today=2026-10-22&c={C430}"); page.locator("#go").wait_for()
        g = page.evaluate("({p: AE_DEBUG.state.practice, ds: AE_DEBUG.state.ds})")
        check(g == {"p": True, "ds": "2026-10-20"} and page.locator("#chal").count() == 1, f"past per-day page opens that day as practice, with challenge {g}")
        page.locator("#go").click(); play5(page, aim=False)
        check(page.locator("#vs").count() == 1, "past day: end screen compares too: " + (page.locator("#vs").inner_text() if page.locator("#vs").count() else ""))
        sh = page.evaluate("decodeURIComponent(document.getElementById('sharex').href.split('text=')[1])")
        check("/p/2026-10-20.html?c=" in sh, "past day share links back to its own page with ?c=")
        page.goto(f"{BASE}/p/2026-10-27.html?today=2026-10-20&c={C430}"); page.locator("#go").wait_for()
        g = page.evaluate("({p: AE_DEBUG.state.practice, ds: AE_DEBUG.state.ds})")
        check(g == {"p": False, "ds": "2026-10-20"} and page.locator("#chal").count() == 0, f"future per-day page opens today's game, no challenge {g}")
        ctx.close()
    # per-day pages: right meta, card exists, no answers, no other round targets
    from PIL import Image
    L = json.load(open(os.path.join(ROOT, "puzzles/index.json")))
    for d in L["dates"]:
        P = json.load(open(os.path.join(ROOT, f"puzzles/{d}.json"))); r1 = P["rounds"][0]
        f = os.path.join(ROOT, f"p/{d}.html"); ok = os.path.exists(f)
        hh = open(f).read() if ok else ""
        others = {r["label"].lower() for r in P["rounds"][1:]} - {r1["label"].lower()}
        card = os.path.join(ROOT, f"assets/cards/{d}.jpg")
        check(ok and '<meta name="twitter:card" content="player">' in hh and f'content="https://analyst-eye.github.io/embed.html?date={d}"' in hh
              and f"Analyst Eye #{P['number']}: can you find the {r1['label'].lower()}?" in hh and f'data-day="{d}"' in hh
              and f"assets/cards/{d}.jpg?v=" in hh and os.path.exists(card) and Image.open(card).size == (1200, 900)
              and "secret" not in hh and not any(o in hh.lower() for o in others), f"p/{d}.html: player card meta, title names round 1 only, card 1200x900")
    if not LOCAL:
        import urllib.request
        for d in (TD, L["dates"][-1]):
            hh = urllib.request.urlopen(f"{BASE}/p/{d}.html?c={C430}").read().decode()
            check(f"embed.html?date={d}" in hh and 'twitter:card" content="player"' in hh and f"/assets/cards/{d}.jpg" in hh, f"live p/{d}.html serves its meta")
            img = urllib.request.urlopen(f"{BASE}/assets/cards/{d}.jpg"); check(img.status == 200 and img.headers["Content-Type"] == "image/jpeg", f"live card {d}.jpg served")
    # daily sets ramp easy -> medium -> hard and are the same file for everyone
    for d in json.load(open(os.path.join(ROOT, "puzzles/index.json")))["dates"]:
        t = [r["tier"] for r in json.load(open(os.path.join(ROOT, f"puzzles/{d}.json")))["rounds"]]
        check(t == ["easy", "easy", "medium", "medium", "hard"], f"{d} ramp {t}")
    b.close()
print("JS errors:", errors or "none"); print("FAILED:" if fails else "ALL CHECKS PASSED", fails or "")
sys.exit(1 if errors or fails else 0)
