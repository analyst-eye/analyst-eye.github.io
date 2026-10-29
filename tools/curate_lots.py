#!/usr/bin/env python3
"""Offline curation of OSM parking lots for the wide catalog (never run by the nightly generator).
   python3 tools/curate_lots.py raw/bulk.json out_dir [N]
   Fetches a NAIP chip per candidate lot and measures (a) how car-dense it is, (b) whether the mapped polygon
   really covers the visible lot. Writes out_dir/lots_scored.json; review the contact sheets by eye, then list the
   keepers in generator/curated/lots_ok.json (build_wide_catalog.py --keep)."""
import sys, os, json, math, random
from concurrent.futures import ThreadPoolExecutor
import numpy as np, cv2
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "generator"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_puzzle as M
import build_wide_catalog as B
from PIL import Image, ImageDraw
GSD = 0.5
def score(e, r):
    lat = sum(p[0] for p in r) / len(r); lon = sum(p[1] for p in r) / len(r)
    k = 1 / math.cos(math.radians(lat)); h = 384 * GSD * k; x, y = M.merc(lat, lon)
    box = (x - h, y - h, x + h, y + h)
    img = M.naip_chip(*box)
    def px(la, lo):
        X, Y = M.merc(la, lo); return [(X - box[0]) / (box[2] - box[0]) * 768, (box[3] - Y) / (box[3] - box[1]) * 768]
    poly = np.array([px(a, b) for a, b in r], np.int32)
    m = np.zeros((768, 768), np.uint8); cv2.fillPoly(m, [poly], 255)
    g = np.array(img.convert("L")).astype(np.float32)
    ins = m > 0
    if ins.sum() < 400: return None, img, poly
    med = np.median(g[ins]); dev = np.abs(g - med)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1); ed = np.hypot(gx, gy) > 90
    ker = np.ones((3, 3), np.uint8)
    out_ring = (cv2.dilate(m, ker, iterations=14) > 0) & (cv2.dilate(m, ker, iterations=3) == 0)
    similar_out = float((dev[out_ring] < 20).mean())
    s = dict(id=e["id"], dens=round(float((dev[ins] > 30).mean()), 3), edge=round(float(ed[ins].mean()), 3),
             out_similar=round(similar_out, 3), px=int(ins.sum()),
             black=round(float((g < 3).mean()), 3))
    return s, img, poly

if __name__ == "__main__":
    bulk, out = sys.argv[1], sys.argv[2]; n = int(sys.argv[3]) if len(sys.argv) > 3 else 240
    os.makedirs(out, exist_ok=True)
    items = json.load(open(bulk))["lot"]; rng = random.Random(5); cand = []; seen = set()
    for e in items:
        if (e["type"], e["id"]) in seen: continue
        seen.add((e["type"], e["id"])); t = e.get("tags", {})
        if t.get("access") in ("private", "no", "customers", "permissive") or t.get("parking") in ("underground", "multi-storey", "rooftop"): continue
        r = B.ring_of(e)
        if not r: continue
        c = (sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r))
        if not (B.GULF[0] <= c[0] <= B.GULF[2] and B.GULF[1] <= c[1] <= B.GULF[3]): continue
        if not 6000 <= B.area_m2(r) <= 40000: continue
        cand.append((dict(id=f"parking_lot-{e['type'][0]}{e['id']}"), B.simplify(r)))
    rng.shuffle(cand); cand = cand[:n]; res = []
    def work(it):
        try: return score(*it)
        except Exception as ex: return None, None, None
    with ThreadPoolExecutor(4) as ex:
        for (s, img, poly), it in zip(ex.map(work, cand), cand):
            if s:
                s["ring"] = it[1]; res.append(s)
                im = img.copy(); ImageDraw.Draw(im).line([tuple(map(int, p)) for p in poly] + [tuple(map(int, poly[0]))], fill=(0, 255, 255), width=3)
                im.resize((384, 384)).save(os.path.join(out, s["id"] + ".jpg"), quality=75)
    json.dump(res, open(os.path.join(out, "lots_scored.json"), "w"))
    print(len(res), "scored")
