#!/usr/bin/env python3
"""Headless test of hidden.html (weekly bonus) + the banner on the daily page.  /workspace/.pwenv/bin/python tests/hidden_smoke.py"""
import http.server, json, os, socketserver, sys, threading
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); SHOTS = os.path.join(ROOT, "screens"); os.makedirs(SHOTS, exist_ok=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(s, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(s, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), Q); BASE = f"http://127.0.0.1:{srv.server_address[1]}"
threading.Thread(target=srv.serve_forever, daemon=True).start()
DAY = json.loads(open(os.path.join(ROOT, "hidden/index.js")).read().split("=", 1)[1].rstrip(";\n"))["dates"][-1]
fails, errors = [], []
def check(c, m):
    print(("  ok   " if c else "  FAIL ") + m)
    if not c: fails.append(m)
def day_after(n):
    import datetime; return (datetime.date.fromisoformat(DAY) + datetime.timedelta(days=n)).isoformat()
def tap_at(page, x, y):   # photo units -> screen
    b = page.locator("#hs").bounding_box(); page.mouse.click(b["x"] + x / 768 * b["width"], b["y"] + y / 768 * b["height"])
with sync_playwright() as p:
    CH = "/opt/ungoogled-chromium/chrome"; br = p.chromium.launch(executable_path=CH, args=["--no-sandbox"]) if os.path.exists(CH) else p.chromium.launch()
    for name, ctxkw in (("mobile", dict(viewport={"width": 390, "height": 800}, has_touch=True, is_mobile=True)), ("desktop", dict(viewport={"width": 1100, "height": 900}))):
        print("==", name)
        ctx = br.new_context(**ctxkw); page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e))); page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        # before the day: nothing leaks
        reqs = []; page.on("request", lambda r: reqs.append(r.url))
        for label, url in (("day before unlock", f"{BASE}/hidden.html?today={day_after(-1)}"), ("direct ?date= before unlock", f"{BASE}/hidden.html?today={day_after(-1)}&date={DAY}")) + ((("real clock (no mock)", f"{BASE}/hidden.html"),) if __import__("datetime").date.today().isoformat() < DAY else ()):
            reqs.clear(); page.goto(url); page.wait_for_timeout(400); body = page.inner_text("#app")
            check("No hidden round yet" in body and "Hidden #1 unlocks" in body, f"{label}: teaser only ({body[:70]!r})")
            check(not any(("hidden/" + DAY) in u or "-lidar" in u or "-photo" in u for u in reqs), f"{label}: round data/images never requested")
            check(page.locator("#hs").count() == 0 and page.locator("img").count() == 0, f"{label}: no round DOM")
        # the actual midnight boundary with a faked browser clock (no ?today=): 23:59:30 CST Nov 7 = 05:59:30Z, 00:00:30 CST = 06:00:30Z
        import datetime as _dt
        _u = _dt.datetime.fromisoformat(DAY + "T06:00:00+00:00") if _dt.date.fromisoformat(DAY).month >= 11 and (_dt.date.fromisoformat(DAY).month > 11 or _dt.date.fromisoformat(DAY).day > 1) else _dt.datetime.fromisoformat(DAY + "T05:00:00+00:00")  # CST after Nov 1, else CDT
        for lbl, t, want in (("30 s before midnight Central", _u - _dt.timedelta(seconds=30), False), ("30 s after midnight Central", _u + _dt.timedelta(seconds=30), True)):
            c3 = br.new_context(**ctxkw); q = c3.new_page(); q.clock.set_fixed_time(t); q.on("pageerror", lambda e: errors.append(str(e)))
            q.goto(f"{BASE}/hidden.html"); q.wait_for_timeout(500)
            check((q.locator("#hs").count() == 1) == want, f"clock {lbl} ({t.isoformat()}): round {'shown' if want else 'hidden'}")
            if not want: check("Hidden #1 unlocks" in q.inner_text("#app"), "  teaser text")
            q2 = c3.new_page(); q2.clock.set_fixed_time(t); q2.goto(f"{BASE}/index.html"); q2.wait_for_timeout(500)
            nb = q2.locator(".bonusbar").count(); nopuz = "No puzzle" in q2.inner_text("#app")
            check(nb == 0 if not want else (nb == 1 or nopuz), f"clock {lbl}: daily-page banner {nb} (no daily puzzle that day in this checkout: {nopuz})")
            c3.close()
        page.goto(f"{BASE}/hidden.html?today={day_after(-1)}"); page.wait_for_timeout(300)
        page.goto(f"{BASE}/index.html?today={day_after(-1)}"); page.wait_for_timeout(500)
        check(page.locator(".bonusbar").count() == 0, "day before: no banner on daily page")
        # on the day
        page.goto(f"{BASE}/hidden.html?today={DAY}"); page.wait_for_selector("#hs"); page.wait_for_timeout(400)
        check("Something is hidden under here" in page.inner_text("#prompt"), "prompt shown: " + page.inner_text("#prompt"))
        check(not page.eval_on_selector("#hl", "e => e.getAttribute('src')"), "LiDAR image not requested before a pin is dropped")
        check(page.locator("#lock").is_disabled(), "Lock in disabled until a tap")
        page.screenshot(path=f"{SHOTS}/hidden-{name}-1-photo.png")
        st = page.evaluate("() => AE_DEBUG.state"); a = st["S"]["answers"][0]; R = st["S"]["radius_px"]
        gx, gy = a["geom"][len(a["geom"]) // 2]; noun = st["S"]["noun"]
        # a wrong pin first (move it later)
        tap_at(page, 120, 120); check(page.locator("#lock").is_enabled(), "tap enables Lock in")
        tap_at(page, gx + R * 3, gy); page.wait_for_timeout(100)
        page.screenshot(path=f"{SHOTS}/hidden-{name}-2-pin.png")
        check(bool(page.eval_on_selector("#hl", "e => e.getAttribute('src')")), "LiDAR preloads after the first pin")
        tap_at(page, gx, gy)
        page.click("#lock"); page.wait_for_timeout(600)
        mid = page.evaluate("() => parseFloat(document.getElementById('hs').style.getPropertyValue('--p'))")
        check(0 < mid < 106, f"wipe in progress (--p={mid:.0f})")
        page.screenshot(path=f"{SHOTS}/hidden-{name}-3-wipe.png")
        page.wait_for_timeout(2400)
        sc = int(page.inner_text(".hverdict .big")); check(sc == 100, f"pin on the feature scores 100 (got {sc})")
        check(page.locator("#hs.shown .ans").count() == 1 and page.locator("#sharex").count() == 1, "answer overlay + share button shown")
        page.screenshot(path=f"{SHOTS}/hidden-{name}-4-revealed.png")
        href = page.get_attribute("#sharex", "href"); txt = __import__("urllib.parse").parse.unquote(href.split("text=")[1])
        print("     share:", txt.replace("\n", " | "))
        check(href.startswith("https://x.com/intent/tweet?text=") and "100/100" in txt and "hidden.html" in txt and noun in txt, "share link text ok")
        # compare slider
        page.fill("#slider", "0") if False else page.evaluate("() => { const s = document.getElementById('slider'); s.value = 40; s.dispatchEvent(new Event('input')); }")
        pv = page.evaluate("() => parseFloat(document.getElementById('hs').style.getPropertyValue('--p'))"); check(40 < pv < 45, f"slider moves the divider (--p={pv:.1f})")
        page.screenshot(path=f"{SHOTS}/hidden-{name}-5-slider.png")
        # no re-guess after the lock
        tap_at(page, 50, 50); page.wait_for_timeout(100); check(page.inner_text(".hverdict .big") == "100", "taps ignored after lock")
        # reload -> saved result, no second try
        page.goto(f"{BASE}/hidden.html?today={DAY}"); page.wait_for_selector(".hverdict"); check(page.inner_text(".hverdict .big") == "100" and page.locator("#lock").count() == 0, "reload shows saved result (no replay)")
        # daily page banner. Daily puzzles only exist up to 11-05 in this scratch clone, so fake the hidden index to a past Sunday
        def banner(sunday, today, saved=None, path="index.html"):
            c2 = br.new_context(**ctxkw); q = c2.new_page(); q.on("pageerror", lambda e: errors.append(str(e)))
            q.route("**/hidden/index.js", lambda r: r.fulfill(content_type="application/javascript", body='window.AE_HIDDEN_INDEX={"dates":["%s"]};' % sunday))
            if saved: q.add_init_script("localStorage.setItem('ae:hidden:%s', JSON.stringify(%s))" % (sunday, saved))
            q.goto(f"{BASE}/{path}?today={today}"); q.wait_for_timeout(700); t = q.locator(".bonusbar"); r = (t.count(), t.inner_text() if t.count() else "")
            if r[0] and path == "index.html" and not saved: q.screenshot(path=f"{SHOTS}/hidden-{name}-6-banner.png")
            c2.close(); return r
        n, t = banner("2026-11-01", "2026-11-05"); check(n == 1 and "Weekly bonus: Hidden" in t, "banner on daily intro: " + t.replace("\n", " / "))
        n, t = banner("2026-11-01", "2026-11-05", '{"score":87}'); check(n == 1 and "you scored 87/100" in t, "banner shows saved score")
        n, t = banner("2026-10-25", "2026-11-05"); check(n == 0, "banner gone after 7 days")
        n, t = banner("2026-11-01", "2026-11-05", path="embed.html"); check(n == 0, "no banner in the embed")
        ctx.close()
        # fresh context: a miss, and the scoring curve
        ctx = br.new_context(**ctxkw); page = ctx.new_page(); page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{BASE}/hidden.html?today={DAY}"); page.wait_for_selector("#hs"); page.wait_for_timeout(300)
        tap_at(page, 80, 700); page.click("#lock"); page.wait_for_timeout(2600)
        sc = int(page.inner_text(".hverdict .big")); check(sc == 0 and "Missed" in page.inner_text(".hverdict .word"), f"far miss scores 0 (got {sc})")
        ctx.close()
    sc = br.new_context().new_page().evaluate if False else None
    pg = br.new_context().new_page(); pg.goto(f"{BASE}/hidden.html?today={DAY}"); pg.wait_for_selector("#hs")
    curve = pg.evaluate("""() => { const S = AE_DEBUG.state.S, a = S.answers; const c = a[0].geom[0]; const out = {};
       [0, 1, 2, 3, 4, 5, 6, 8].forEach(k => { const R = S.radius_px; out[k] = AE_DEBUG.score([c[0] + (k * R), c[1]], a, R).score; }); return out; }""")
    print("     score at k*R from a vertex:", curve)
    br.close()
print("\nconsole/page errors:", errors if errors else "none")
print("FAILED" if fails else "ALL OK", len(fails))
sys.exit(1 if fails or errors else 0)
