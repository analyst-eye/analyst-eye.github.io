#!/usr/bin/env python3
"""Draw each round's accepted answer area on its photo (for review).
   python tools/answer_overlay.py 2026-10-21 [more dates]  -> screens/answers/DATE-N.png
   cyan = target footprint (+ tolerance band, lighter), orange circle = answer point/radius,
   other parts / same-type alternates in cyan too, red = decoys (score 0)."""
import base64, json, math, os, sys
from PIL import Image, ImageDraw
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUZ = os.path.join(ROOT, "puzzles"); OUT = os.path.join(ROOT, "screens", "answers"); os.makedirs(OUT, exist_ok=True)

def decode(sec, ds):
    key = f"analyst-eye:{ds}".encode()
    return json.loads(bytes(b ^ key[i % len(key)] for i, b in enumerate(base64.b64decode(sec))))

def shapes(t, hw0):
    """-> [(geom, gtype, hw)] for one target incl. its extra parts"""
    out = [(t.get("geom") or [], t.get("gtype", "point"), hw0)]
    for p in t.get("parts") or []: out.append((p["geom"], p["gtype"], p.get("halfwidth_px", 0)))
    return out

def draw_target(d, ov, t, hw0, R, col, a=60):
    for g, gt, hw in shapes(t, hw0):
        g = [tuple(p) for p in g]
        if len(g) > 1:
            # tolerance band: everything within R of the outline (or line+hw) scores full closeness
            w = int(2 * (R + (hw if gt == "line" else 0)))
            ov.line(g + ([g[0]] if gt == "polygon" else []), fill=col + (a,), width=max(2, w), joint="curve")
            for p in g: ov.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=col + (a,))
            if gt == "polygon": ov.polygon(g, fill=col + (a,))
            d.line(g + ([g[0]] if gt == "polygon" else []), fill=col + (255,), width=2)
    x, y = t["answer"]
    if len(t.get("geom") or []) < 2 and not t.get("parts"):
        ov.ellipse([x - R, y - R, x + R, y + R], fill=col + (a,))
    d.ellipse([x - R, y - R, x + R, y + R], outline=(255, 176, 46, 255), width=2)
    d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 176, 46, 255))

def render(ds, only=None):
    P = json.load(open(os.path.join(PUZ, f"{ds}.json"))); paths = []
    for r in P["rounds"]:
        if only and r["round"] not in only: continue
        s = decode(r["secret"], ds); R = r["radius_px"]
        im = Image.open(os.path.join(PUZ, r["image"])).convert("RGBA")
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0)); ov = ImageDraw.Draw(lay)
        top = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(top)
        for t in [s] + (s.get("alts") or []): draw_target(d, ov, t, s.get("halfwidth_px", 0), R, (90, 209, 230))
        for dc in s.get("decoys") or []: draw_target(d, ov, dc, dc.get("halfwidth_px", 0), dc.get("r", 8), (255, 92, 92))
        im = Image.alpha_composite(Image.alpha_composite(im, lay), top)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, im.size[0], 22], fill=(0, 0, 0, 170))
        d.text((6, 5), f"{ds} R{r['round']} {r['category']} | {s.get('name') or ''} | {s.get('osm','')} | alts {len(s.get('alts') or [])} parts {len(s.get('parts') or [])} decoys {len(s.get('decoys') or [])}", fill=(255, 255, 255, 255))
        p = os.path.join(OUT, f"{ds}-{r['round']}.png"); im.convert("RGB").save(p); paths.append(p)
    return paths

if __name__ == "__main__":
    for ds in sys.argv[1:]: print("\n".join(render(ds)))
