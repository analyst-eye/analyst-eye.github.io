#!/usr/bin/env python3
"""QA: draw every round's answer marker/outline on its image -> screens/contact-<date>.jpg
   python3 tools/contact_sheet.py [date ...]   (default: all puzzles)
   python3 tools/contact_sheet.py --decoys [date ...]  -> screens/contact-decoys.jpg: only decoy rounds, bigger tiles
   Colours: cyan/orange = scoring target (+ other same-type features), red dashed + X = decoys (score 0), yellow = hint circle."""
import base64, glob, json, os, sys
from PIL import Image, ImageDraw
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out_dir = os.path.join(ROOT, "screens"); os.makedirs(out_dir, exist_ok=True)
def decode(sec, ds):
    raw = base64.b64decode(sec); key = f"analyst-eye:{ds}".encode()
    return json.loads(bytes(b ^ key[i % len(key)] for i, b in enumerate(raw)))
DEC = "--decoys" in sys.argv; args = [a for a in sys.argv[1:] if a != "--decoys"]
def draw_decoys(d, s):
    for t in s.get("decoys", []):
        g = [tuple(p) for p in t["geom"]]
        if len(g) > 1:
            for a, b in zip(g, g[1:]):   # dashed outline
                n = max(1, int(((b[0]-a[0])**2 + (b[1]-a[1])**2) ** .5 / 8))
                for i in range(0, n, 2):
                    d.line([(a[0]+(b[0]-a[0])*i/n, a[1]+(b[1]-a[1])*i/n), (a[0]+(b[0]-a[0])*min(n, i+1)/n, a[1]+(b[1]-a[1])*min(n, i+1)/n)], fill=(255, 70, 70), width=3)
        x, y = t["answer"]; d.line([(x-8, y-8), (x+8, y+8)], fill=(255, 70, 70), width=4); d.line([(x+8, y-8), (x-8, y+8)], fill=(255, 70, 70), width=4)
dates = args or sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(ROOT, "puzzles/20*.json")))
if DEC:
    tiles = []
    for ds in dates:
        P = json.load(open(os.path.join(ROOT, f"puzzles/{ds}.json")))
        for r in P["rounds"]:
            if not r.get("caution"): continue
            s = decode(r["secret"], ds); im = Image.open(os.path.join(ROOT, "puzzles", r["image"])).convert("RGB"); d = ImageDraw.Draw(im)
            draw_decoys(d, s)
            for t in s.get("alts", []):
                if len(t["geom"]) > 1: d.line([tuple(p) for p in t["geom"]], fill=(0, 160, 255), width=3)
            if len(s["geom"]) > 1: d.line([tuple(p) for p in s["geom"]], fill=(0, 255, 255), width=3)
            x, y = s["answer"]; R = max(16, r["radius_px"]); d.ellipse([x - R, y - R, x + R, y + R], outline=(0, 255, 120), width=4)
            tiles.append((f"{ds} R{r['round']} {r['tier'][:3]} {r['dscore']} | {r['label']} vs {', '.join(sorted({t['label'] for t in s['decoys']}))} ({len(s['decoys'])})", im))
    T = 420; cols = 3; rows = max(1, (len(tiles) + cols - 1) // cols)
    sheet = Image.new("RGB", (T * cols, rows * (T + 24)), (10, 16, 22)); d0 = ImageDraw.Draw(sheet)
    for i, (cap, im) in enumerate(tiles):
        x, y = (i % cols) * T, (i // cols) * (T + 24); sheet.paste(im.resize((T, T)), (x, y + 24)); d0.text((x + 4, y + 6), cap[:68], fill=(220, 230, 240))
    p = os.path.join(out_dir, "contact-decoys.jpg"); sheet.save(p, quality=88); print(p, len(tiles), "decoy rounds"); sys.exit(0)
for ds in dates:
    P = json.load(open(os.path.join(ROOT, f"puzzles/{ds}.json"))); T = 300
    sheet = Image.new("RGB", (T * 5, T + 22), (10, 16, 22)); d0 = ImageDraw.Draw(sheet)
    for i, r in enumerate(P["rounds"]):
        s = decode(r["secret"], ds); im = Image.open(os.path.join(ROOT, "puzzles", r["image"])).convert("RGB"); d = ImageDraw.Draw(im)
        for t in s.get("alts", []):   # other same-type features in frame (also accepted)
            if len(t["geom"]) > 1: d.line([tuple(p) for p in t["geom"]], fill=(0, 160, 255), width=3)
            ax, ay = t["answer"]; d.ellipse([ax - 10, ay - 10, ax + 10, ay + 10], outline=(255, 140, 0), width=3)
        if len(s["geom"]) > 1: d.line([tuple(p) for p in s["geom"]], fill=(0, 255, 255), width=3)
        x, y = s["answer"]; R = max(16, r["radius_px"])
        d.ellipse([x - R, y - R, x + R, y + R], outline=(255, 60, 0), width=4)
        draw_decoys(d, s)
        hx, hy, hr = s["hint"]; d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], outline=(255, 200, 0), width=2)
        sheet.paste(im.resize((T, T)), (i * T, 22))
        d0.text((i * T + 4, 4), f"{i+1}. {r.get('tier','?')[:1].upper()}{r.get('dscore','')} {r['label']} +{len(s.get('alts', []))} {s.get('name') or ''}"[:44], fill=(220, 230, 240))
    p = os.path.join(out_dir, f"contact-{ds}.jpg"); sheet.save(p, quality=85); print(p)
