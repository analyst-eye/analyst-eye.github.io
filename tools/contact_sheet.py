#!/usr/bin/env python3
"""QA: draw every round's answer marker/outline on its image -> screens/contact-<date>.jpg
   python3 tools/contact_sheet.py [date ...]   (default: all puzzles)"""
import base64, glob, json, os, sys
from PIL import Image, ImageDraw
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out_dir = os.path.join(ROOT, "screens"); os.makedirs(out_dir, exist_ok=True)
def decode(sec, ds):
    raw = base64.b64decode(sec); key = f"analyst-eye:{ds}".encode()
    return json.loads(bytes(b ^ key[i % len(key)] for i, b in enumerate(raw)))
dates = sys.argv[1:] or sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(ROOT, "puzzles/20*.json")))
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
        hx, hy, hr = s["hint"]; d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], outline=(255, 200, 0), width=2)
        sheet.paste(im.resize((T, T)), (i * T, 22))
        d0.text((i * T + 4, 4), f"{i+1}. {r.get('tier','?')[:1].upper()}{r.get('dscore','')} {r['label']} +{len(s.get('alts', []))} {s.get('name') or ''}"[:44], fill=(220, 230, 240))
    p = os.path.join(out_dir, f"contact-{ds}.jpg"); sheet.save(p, quality=85); print(p)
