#!/usr/bin/env python3
"""Review sheet for the DRAFT aircraft set: one numbered tile per NEEDS-AJ object (USDA NAIP photo, public domain).
   python3 tools/aircraft_review_sheet.py [--all]   -> generator/curated/aircraft_review.png (+ copy in screens/)"""
import io, json, math, os, shutil, sys, time
import requests
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, "generator/curated/aircraft_draft.json")))
SVC = "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer/exportImage"
UA = {"User-Agent": "AnalystEye/1.0 (daily geo puzzle; https://x.com/A_is_A)"}
T, CAP = 340, 58
def font(n):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(f): return ImageFont.truetype(f, n)
    return ImageFont.load_default()
def chip(lat, lon, size_m, px):
    k = 1 / math.cos(math.radians(lat)); h = size_m / 2 * k
    X = lon * 20037508.34 / 180; Y = math.log(math.tan((90 + lat) * math.pi / 360)) * 6378137.0
    for i in range(6):
        try:
            r = requests.get(SVC, headers=UA, timeout=180, params=dict(bbox=f"{X-h},{Y-h},{X+h},{Y+h}", bboxSR=3857, imageSR=3857,
                             size=f"{px},{px}", format="jpg", f="image", interpolation="RSP_BilinearInterpolation"))
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"): return Image.open(io.BytesIO(r.content)).convert("RGB")
        except requests.RequestException: pass
        time.sleep(4 * 2 ** i)
    raise RuntimeError("NAIP unavailable")
objs = [o for o in D["objects"] if "--all" in sys.argv or o["tier"] == "NEEDS AJ"]
cols = 4; rows = math.ceil(len(objs) / cols)
sheet = Image.new("RGB", (cols * T, 64 + rows * (T + CAP)), (12, 18, 24)); dr = ImageDraw.Draw(sheet)
dr.text((12, 10), "Analyst Eye: aircraft labels for AJ to review (80-94% confidence). Reply with # and OK / wrong (+ correct type).", fill=(230, 236, 242), font=font(16))
dr.text((12, 36), "Box = proposed object. Photos: USDA NAIP (public domain). Auto-approved (>=95%) items are in aircraft_draft.json, not shown.", fill=(150, 165, 180), font=font(12))
for n, o in enumerate(objs):
    view = max(60.0, o["size_m"] * 1.7)
    im = chip(o["lat"], o["lon"], view, T); d = ImageDraw.Draw(im)
    b = o["size_m"] * 1.12 / view * T / 2; c = T / 2
    d.rectangle([c - b, c - b, c + b, c + b], outline=(255, 176, 46), width=3)
    tag = f"#{o['rank']}"; d.rectangle([c - b, c - b - 24, c - b + 14 + 11 * len(tag), c - b], fill=(255, 176, 46)); d.text((c - b + 6, c - b - 22), tag, fill=(0, 0, 0), font=font(16))
    L = 10 / view * T; d.rectangle([10, T - 16, 10 + L, T - 11], fill=(255, 255, 255)); d.text((16 + L, T - 22), "10 m", fill=(255, 255, 255), font=font(12), stroke_width=2, stroke_fill=(0, 0, 0))
    x, y = (n % cols) * T, 64 + (n // cols) * (T + CAP); sheet.paste(im, (x, y))
    dr.text((x + 8, y + T + 4), f"#{o['rank']}  {o['label']}  ·  {o['confidence']}%", fill=(255, 210, 120), font=font(15))
    dr.text((x + 8, y + T + 24), o["site"].split(",")[0][:44], fill=(170, 185, 200), font=font(12))
    dr.text((x + 8, y + T + 40), f"OSM: {o['osm_name']}"[:50], fill=(130, 145, 160), font=font(11))
out = os.path.join(ROOT, "generator/curated/aircraft_review.png"); sheet.save(out, optimize=True)
os.makedirs(os.path.join(ROOT, "screens"), exist_ok=True); shutil.copy(out, os.path.join(ROOT, "screens/aircraft_review.png")); print(out)
