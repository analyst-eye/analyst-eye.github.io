#!/usr/bin/env python3
"""
Analyst Eye daily puzzle generator.

Builds N rounds/day from free, openly licensed data only:
  * Targets: OpenStreetMap via the Overpass API (ODbL; attribution shown on site)
  * Imagery: USDA NAIP via the USGS National Map ImageServer (public domain)

Usage:
  python generator/make_puzzle.py                     # ensure today..today+days_ahead exist (US Central)
  python generator/make_puzzle.py --date 2026-10-25   # one specific day
  python generator/make_puzzle.py --start 2026-10-19 --days 7 [--force]

Optional: XAI_API_KEY (and AE_GROK_MODEL) -> polish analyst notes with Grok; falls back to templates.
"""
import argparse, base64, datetime as dt, hashlib, io, json, math, os, random, re, sys, time
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageStat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "generator")
PUZ = os.path.join(ROOT, "puzzles")
IMG = os.path.join(PUZ, "img")
CACHE = os.path.join(GEN, ".cache")
S = json.load(open(os.path.join(GEN, "settings.json")))
BL = json.load(open(os.path.join(GEN, "blocklist.json")))
UA = {"User-Agent": S["user_agent"]}
SIZE = S["image_size"]

# ---------------------------------------------------------------- categories
# sel: Overpass selectors; gsd: metres/pixel for the chip; r_m: "perfect" radius in metres
# kind: how the answer geometry is scored; diff: 1 easy .. 3 hard (rounds are ordered by this)
CATS = {
 "stadium":      dict(sel=['nwr["leisure"="stadium"]'], label="Stadium", task="Find a stadium.", gsd=0.9, r_m=25, diff=1),
 "runway":       dict(sel=['way["aeroway"="runway"]'], label="Runway", task="Find a runway.", gsd=1.6, r_m=30, diff=1, halfwidth_m=23),
 "marina":       dict(sel=['nwr["leisure"="marina"]'], label="Marina", task="Find a marina.", gsd=0.9, r_m=30, diff=1),
 "golf":         dict(sel=['way["golf"="green"]'], label="Putting green", task="Find a putting green.", gsd=0.6, r_m=10, diff=2),
 "baseball":     dict(sel=['way["leisure"="pitch"]["sport"="baseball"]'], label="Baseball field", task="Find a baseball field.", gsd=0.6, r_m=18, diff=1),
 "soccer":       dict(sel=['way["leisure"="pitch"]["sport"="soccer"]'], label="Soccer field", task="Find a soccer field.", gsd=0.6, r_m=18, diff=1),
 "football":     dict(sel=['way["leisure"="pitch"]["sport"="american_football"]'], label="Football field", task="Find a football field.", gsd=0.6, r_m=18, diff=1),
 "track":        dict(sel=['way["leisure"="track"]["sport"="athletics"]'], label="Running track", task="Find a running track.", gsd=0.6, r_m=20, diff=1),
 "cemetery":     dict(sel=['way["landuse"="cemetery"]'], label="Cemetery", task="Find a cemetery.", gsd=0.9, r_m=25, diff=2),
 "wastewater":   dict(sel=['nwr["man_made"="wastewater_plant"]'], label="Water treatment plant", task="Find a water treatment plant.", gsd=0.9, r_m=30, diff=2),
 "pier":         dict(sel=['way["man_made"="pier"]'], label="Pier", task="Find a pier.", gsd=0.6, r_m=15, diff=2, halfwidth_m=4),
 "bridge":       dict(sel=['way["man_made"="bridge"]'], label="Bridge", task="Find a bridge.", gsd=0.9, r_m=20, diff=2),
 "roundabout":   dict(sel=['way["junction"="roundabout"]'], label="Roundabout", task="Find a roundabout.", gsd=0.6, r_m=15, diff=2),
 "pool":         dict(sel=['way["leisure"="swimming_pool"]["name"]'], label="Swimming pool", task="Find a swimming pool.", gsd=0.6, r_m=12, diff=2),
 "tennis":       dict(sel=['way["leisure"="pitch"]["sport"="tennis"]'], label="Tennis court", task="Find a tennis court.", gsd=0.6, r_m=12, diff=2),
 "water_tower":  dict(sel=['nwr["man_made"="water_tower"]'], label="Water tower", task="Find a water tower.", gsd=0.6, r_m=18, diff=2),
 "storage_tank": dict(sel=['nwr["man_made"="storage_tank"]'], label="Storage tank", task="Find a storage tank.", gsd=0.6, r_m=15, diff=2),
 "solar":        dict(sel=['nwr["power"="plant"]["plant:source"="solar"]', 'way["power"="generator"]["generator:source"="solar"]["generator:method"="photovoltaic"]'], label="Solar farm", task="Find the solar panels.", gsd=0.9, r_m=20, diff=2),
 "substation":   dict(sel=['way["power"="substation"]'], label="Power substation", task="Find a power substation.", gsd=0.6, r_m=15, diff=3),
 "slipway":      dict(sel=['nwr["leisure"="slipway"]'], label="Boat ramp", task="Find a boat ramp.", gsd=0.6, r_m=15, diff=3),
 "lighthouse":   dict(sel=['nwr["man_made"="lighthouse"]'], label="Lighthouse", task="Find a lighthouse.", gsd=0.6, r_m=15, diff=3),
 "mast":         dict(sel=['node["man_made"="mast"]', 'node["man_made"="tower"]["tower:type"="communication"]'], label="Radio tower", task="Find a radio tower.", gsd=0.6, r_m=15, diff=3),
}

def cat_of(t):
    mm = t.get("man_made"); sport = t.get("sport")
    if t.get("leisure") == "stadium": return "stadium"
    if t.get("aeroway") == "runway": return "runway"
    if t.get("leisure") == "marina": return "marina"
    if t.get("golf") == "green": return "golf"
    if t.get("leisure") == "pitch":
        return {"baseball": "baseball", "soccer": "soccer", "american_football": "football", "tennis": "tennis"}.get(sport)
    if t.get("leisure") == "track" and sport == "athletics": return "track"
    if t.get("leisure") == "swimming_pool" and t.get("name"): return "pool"
    if t.get("leisure") == "slipway": return "slipway"
    if t.get("landuse") == "cemetery": return "cemetery"
    if t.get("junction") == "roundabout": return "roundabout"
    if mm == "bridge": return "bridge"
    if mm == "wastewater_plant": return "wastewater"
    if mm in ("pier", "water_tower", "storage_tank", "lighthouse"): return mm
    if t.get("power") == "substation": return "substation"
    if t.get("plant:source") == "solar" or t.get("generator:source") == "solar": return "solar"
    if mm == "mast" or (mm == "tower" and t.get("tower:type") == "communication"): return "mast"
    return None

# ---------------------------------------------------------------- analyst notes (templates)
# One short, plain-English clue per round (no jargon). Two variants each, picked at random.
NOTES = {
 "stadium": ["A big green field with rows of seats wrapped around it.", "Look for a neat green field with stands along both long sides."],
 "runway": ["The longest, straightest strip of pavement, with white stripes at each end.", "A long gray strip much wider than any road, with nothing built on it."],
 "marina": ["Rows of thin docks with white boats parked side by side.", "A sheltered patch of water lined with boats in neat rows."],
 "golf": ["A small, extra-smooth patch of bright green, usually hugged by white sand traps.", "Find the end of a fairway: a smooth oval of lighter green next to a sand trap."],
 "baseball": ["A green fan shape with a tan dirt diamond at its point.", "Look for the tan dirt infield shaped like a slice of pie."],
 "soccer": ["A bright green rectangle with white lines and a circle in the middle.", "A big green rectangle with a goal box painted at each end."],
 "football": ["A green rectangle striped with white lines every few steps.", "Look for a green field with evenly spaced white stripes across it."],
 "track": ["A reddish or dark oval loop, like a mini racetrack.", "Look for an oval running loop, often with a field in the middle."],
 "cemetery": ["A tidy lawn covered in tiny, evenly spaced dots: the headstones.", "Look for a grassy area with neat rows of little white specks."],
 "wastewater": ["Big round and square pools of water grouped together behind a fence.", "Several identical circles of water side by side, like giant coins."],
 "pier": ["A long, thin, straight walkway sticking out into the water.", "A straight pale line running from the shore out over the water."],
 "bridge": ["A road crossing over water or another road, with its shadow underneath.", "Look where a road keeps going straight across water."],
 "roundabout": ["A small circle where several roads meet, with an island in the middle.", "Follow the roads until they meet at a ring."],
 "pool": ["A bright blue rectangle that stands out from everything around it.", "Look for a splash of bright blue among the roofs and grass."],
 "tennis": ["A small, flat court, often green or blue, with white lines.", "Look for small colored rectangles, often in a row behind a fence."],
 "water_tower": ["From above it's a small circle, but its long shadow looks like a lollipop.", "Look for a lollipop-shaped shadow on the ground."],
 "storage_tank": ["A perfect circle, often in a group of other circles.", "Round, flat-topped discs with a curved shadow on one side."],
 "solar": ["Neat rows of dark panels that look like stripes of corduroy.", "Dark blue-black rectangles laid out in tidy parallel rows."],
 "substation": ["A fenced gravel yard packed with metal equipment where power lines meet.", "Follow the cleared power-line path through the trees to a yard full of gear."],
 "slipway": ["A short paved ramp running straight into the water, usually beside a parking lot.", "Look for a strip of pavement that dips right into the water."],
 "lighthouse": ["A small round tower by the water with a long, thin shadow.", "Look along the shore for a small tower and its long shadow."],
 "mast": ["It's almost invisible from above; look for a very long, thin shadow.", "Find a tiny fenced pad with a needle-thin shadow stretching away."],
}

# ---------------------------------------------------------------- helpers
def log(*a): print(*a, file=sys.stderr, flush=True)

def central_today():
    return dt.datetime.now(ZoneInfo(S["timezone"])).date()

def merc(lat, lon):
    return lon * 20037508.34 / 180, math.log(math.tan((90 + lat) * math.pi / 360)) * 6378137.0

def unmerc(x, y):
    return math.degrees(2 * math.atan(math.exp(y / 6378137.0)) - math.pi / 2), x * 180 / 20037508.34

def local_m(lat0, lon0):
    kx = 111320 * math.cos(math.radians(lat0)); ky = 110540
    return lambda la, lo: ((lo - lon0) * kx, (la - lat0) * ky)

def seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)

def point_in_ring(p, ring):
    x, y = p; inside = False
    for i in range(len(ring)):
        x1, y1 = ring[i]; x2, y2 = ring[(i + 1) % len(ring)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            inside = not inside
    return inside

def get(url, **kw):
    for i in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=kw.pop("timeout", 120), **kw)
            if r.status_code == 200: return r
            log(f"  GET {r.status_code} {url[:80]}")
        except requests.RequestException as e:
            log(f"  GET error {e}")
        time.sleep(5 * 2 ** i)
    raise RuntimeError(f"GET failed: {url}")

def overpass(q):
    for attempt in range(2):
        for m in S["overpass_mirrors"]:
            try:
                log(f"  Overpass -> {m}")
                r = requests.post(m, data={"data": q}, headers=UA, timeout=240)
                if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                    return r.json()["elements"]
                log(f"  Overpass {r.status_code}: {r.text[:120]!r}")
            except (requests.RequestException, ValueError) as e:
                log(f"  Overpass error {e}")
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("all Overpass mirrors failed")

# ---------------------------------------------------------------- data fetch (cached ~20h)
def fetch_osm():
    os.makedirs(CACHE, exist_ok=True)
    cpath = os.path.join(CACHE, "overpass.json")
    if os.path.exists(cpath) and time.time() - os.path.getmtime(cpath) < 20 * 3600:
        return json.load(open(cpath))
    s, w, n, e = S["region"]["bbox"]
    slices = S.get("query_slices", 3); step = (e - w) / slices
    els, seen = [], set()
    for i in range(slices):      # smaller tiles keep each query light for the public servers
        bb = f"({s},{w + i * step:.4f},{n},{w + (i + 1) * step:.4f})"
        cand = "".join(f"{sel}{bb};" for c in CATS.values() for sel in c["sel"])
        q = f"""[out:json][timeout:180];
( {cand} )->.cand;
( nwr["landuse"="military"]{bb}; nwr["military"]{bb}; nwr["amenity"="prison"]{bb};
  nwr["power"="plant"]["plant:source"="nuclear"]{bb}; nwr["industrial"="refinery"]{bb};
  nwr["aeroway"="aerodrome"]{bb}; )->.bad;
.cand out tags center geom;
.bad out tags geom;"""
        log(f"  tile {i + 1}/{slices} {bb}")
        for x in overpass(q):
            key = (x["type"], x["id"])
            if key not in seen: seen.add(key); els.append(x)
        time.sleep(3)
    # the two result sets are concatenated; split by tags
    cands, bad = [], []
    rx = re.compile(BL["name_regex"])
    for x in els:
        t = x.get("tags", {})
        sensitive = (t.get("landuse") == "military" or "military" in t or t.get("amenity") == "prison"
                     or t.get("plant:source") == "nuclear" or t.get("industrial") == "refinery")
        if t.get("aeroway") == "aerodrome":
            sensitive = sensitive or bool(rx.search(" ".join([t.get("name", ""), t.get("operator", ""), t.get("operator:type", "")])))
        if sensitive: bad.append(x)
        elif cat_of(t): cands.append(x)
    data = {"fetched": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "cands": cands, "bad": bad}
    json.dump(data, open(cpath, "w"))
    log(f"  OSM: {len(cands)} candidates, {len(bad)} sensitive features")
    return data

def bad_shapes(bad):
    """-> list of (name, rings[list of [(lat,lon)]], points[(lat,lon)])"""
    out = []
    for b in bad:
        name = b.get("tags", {}).get("name", b.get("tags", {}).get("military", "sensitive"))
        rings, pts = [], []
        if b["type"] == "node":
            pts.append((b["lat"], b["lon"]))
        elif b["type"] == "way" and b.get("geometry"):
            rings.append([(p["lat"], p["lon"]) for p in b["geometry"]])
        elif b["type"] == "relation":
            for m in b.get("members", []):
                if m.get("geometry"): rings.append([(p["lat"], p["lon"]) for p in m["geometry"]])
        out.append((name, rings, pts))
    for bx in BL["bboxes"]:
        s, w, n, e = bx["bbox"]
        out.append((bx["name"], [[(s, w), (s, e), (n, e), (n, w), (s, w)]], []))
    return out

def chip_is_clear(shapes, lat_c, lon_c, half_m, margin_m):
    """True if no sensitive feature lies inside the chip footprint grown by margin_m."""
    proj = local_m(lat_c, lon_c); lim = half_m + margin_m
    box = [(-lim, -lim), (lim, -lim), (lim, lim), (-lim, lim)]
    for name, rings, pts in shapes:
        for p in pts:
            x, y = proj(*p)
            if abs(x) <= lim and abs(y) <= lim: return False, name
        for ring in rings:
            r = [proj(*p) for p in ring]
            if any(abs(x) <= lim and abs(y) <= lim for x, y in r): return False, name
            if len(r) > 2 and (point_in_ring((0, 0), r) or any(point_in_ring(c, r) for c in box)): return False, name
            for a, b in zip(r, r[1:]):   # long edges crossing the box without a vertex inside
                L = math.hypot(b[0] - a[0], b[1] - a[1]); k = max(1, int(L / 25))
                for i in range(k + 1):
                    x = a[0] + (b[0] - a[0]) * i / k; y = a[1] + (b[1] - a[1]) * i / k
                    if abs(x) <= lim and abs(y) <= lim: return False, name
    return True, None

# ---------------------------------------------------------------- imagery
def naip_chip(xmin, ymin, xmax, ymax):
    p = dict(bbox=f"{xmin},{ymin},{xmax},{ymax}", bboxSR=3857, imageSR=3857, size=f"{SIZE},{SIZE}",
             format="jpg", f="image", interpolation="RSP_BilinearInterpolation")
    r = get(f"{S['naip_service']}/exportImage", params=p)
    if not r.headers.get("content-type", "").startswith("image"): raise RuntimeError("NAIP returned non-image")
    return Image.open(io.BytesIO(r.content)).convert("RGB")

def naip_meta(lat, lon):
    try:
        geom = json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}})
        j = get(f"{S['naip_service']}/identify", timeout=60, params=dict(geometry=geom, geometryType="esriGeometryPoint",
                returnCatalogItems="true", returnGeometry="false", f="json")).json()
        best = None
        for f in (j.get("catalogItems") or {}).get("features", []):
            a = f["attributes"]
            if a.get("Category") == 1 and a.get("acquisition_date"):
                if not best or a["acquisition_date"] > best["acquisition_date"]: best = a
        if best:
            return {"acquired": dt.datetime.fromtimestamp(best["acquisition_date"] / 1000, dt.timezone.utc).date().isoformat(),
                    "year": best.get("Year"), "state": best.get("State"), "tile": best.get("Name"),
                    "resolution_m": round(best.get("resolution_value") or 0, 2) or None}
    except Exception as e:
        log(f"  NAIP meta unavailable: {e}")
    return None

def quality_ok(img, ax, ay, cat=None):
    g = img.convert("L"); st = ImageStat.Stat(g)
    h = g.histogram(); n = SIZE * SIZE
    blank = (sum(h[:3]) + sum(h[-3:])) / n
    if blank > 0.05: return False, f"blank/no-data {blank:.2f}"
    if st.stddev[0] < 12: return False, f"low contrast {st.stddev[0]:.1f}"
    if not 35 < st.mean[0] < 215: return False, f"bad exposure {st.mean[0]:.0f}"
    r = 40; patch = g.crop((max(0, ax - r), max(0, ay - r), min(SIZE, ax + r), min(SIZE, ay + r)))
    if ImageStat.Stat(patch).stddev[0] < 6: return False, "featureless target patch"
    # solar farms built after the NAIP flight show up as bare bright ground: panels must read darker than the scene
    # heuristic tuned on a handful of chips: bright AND warm (tan soil) target patch = no panels yet
    if cat == "solar":
        pc = ImageStat.Stat(img.convert("RGB").crop(patch_box := (max(0, ax - r), max(0, ay - r), min(SIZE, ax + r), min(SIZE, ay + r)))).mean
        if ImageStat.Stat(patch).mean[0] > 1.05 * st.mean[0] and pc[0] - pc[2] > 18:
            return False, "bare ground at solar site (built after imagery?)"
    # exact duplicate rows/cols = seam/no-data stripe
    return True, "ok"

# ---------------------------------------------------------------- notes
def ref_clause(t):
    ref = t.get("ref", "")
    m = re.match(r"^(\d{1,2})[LRC]?/(\d{1,2})", ref)
    if not m: return ""
    a, b = int(m.group(1)) * 10, int(m.group(2)) * 10
    return f". This one is runway {ref}: the numbers are magnetic headings ({a:03d}° / {b:03d}°), so it runs roughly {'north-south' if a in (10,20,30,160,170,180,190,200,340,350,360) else 'east-west' if a in (80,90,100,260,270,280) else 'diagonally'}"

SPORT_NOTES = {
 "baseball": "A ballpark: a green fan shape with a tan dirt diamond, ringed by seats.",
 "soccer": "A green rectangle with a circle in the middle, ringed by seats.",
 "american_football": "A striped green field inside a running track, with stands along the sides.",
}

def template_note(cat, t, rng, meta):
    sport = (t.get("sport") or "").split(";")[0]
    if cat == "stadium" and "dome" in (t.get("name") or "").lower(): return "A giant round white roof: this stadium has a lid on it."
    if cat == "stadium" and sport in SPORT_NOTES: return SPORT_NOTES[sport]
    return rng.choice(NOTES[cat])

def grok_note(cat, t, base, meta):
    key = os.environ.get("XAI_API_KEY")
    if not key: return None
    try:
        tags = {k: v for k, v in t.items() if k in ("name", "height", "operator", "surface", "ref", "capacity", "sport", "material", "content")}
        prompt = (f"You write the one-line clue for a daily aerial-imagery spotting game. Target type: {CATS[cat]['label']}. "
                  f"OSM tags (only facts you may use): {json.dumps(tags)}. Imagery: USDA NAIP aerial photo, ~0.6 m resolution"
                  f"{', acquired ' + meta['acquired'] if meta else ''}. Draft: {base}\n"
                  "Rewrite as ONE short, friendly sentence (max 110 chars) in plain English a 12-year-old understands: "
                  "what it looks like from above (shape, color, shadow). No jargon, no place names, "
                  "no facts or numbers not given. No hashtags, no emojis.")
        r = requests.post("https://api.x.ai/v1/chat/completions", timeout=45,
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                          json={"model": os.environ.get("AE_GROK_MODEL", "grok-4.7"), "temperature": 0.4,
                                "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"].strip()
        return txt if 20 < len(txt) < 160 else None
    except Exception as e:
        log(f"  Grok note skipped: {e}")
        return None

def _num(v):
    try: return float(re.match(r"[\d.]+", str(v)).group())
    except Exception: return 0.0

def extent_m(x):
    b = x.get("bounds")
    if not b: return 0.0
    proj = local_m(b["minlat"], b["minlon"]); X, Y = proj(b["maxlat"], b["maxlon"])
    return math.hypot(X, Y)

def feature_point(x, c):
    """Representative answer point: node coords, polygon centroid (if inside), else mid-length of the line."""
    if "lat" in x: return {"lat": x["lat"], "lon": x["lon"]}
    g = [(p["lat"], p["lon"]) for p in x.get("geometry") or [] if p]
    if len(g) >= 2:
        closed = len(g) > 3 and g[0] == g[-1]
        if closed and c not in ("runway", "pier"):
            proj = local_m(*g[0]); r = [proj(*p) for p in g]
            A = cx = cy = 0.0
            for (x1, y1), (x2, y2) in zip(r, r[1:]):
                k = x1 * y2 - x2 * y1; A += k; cx += (x1 + x2) * k; cy += (y1 + y2) * k
            if abs(A) > 1e-6:
                cx /= 3 * A; cy /= 3 * A
                if point_in_ring((cx, cy), r):
                    lat = g[0][0] + cy / 110540; lon = g[0][1] + cx / (111320 * math.cos(math.radians(g[0][0])))
                    return {"lat": lat, "lon": lon}
        proj = local_m(*g[0]); r = [proj(*p) for p in g]
        L = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(r, r[1:])]; half = sum(L) / 2
        for (a, b), l, (ga, gb) in zip(zip(r, r[1:]), L, zip(g, g[1:])):
            if half <= l and l > 0:
                f = half / l; return {"lat": ga[0] + (gb[0] - ga[0]) * f, "lon": ga[1] + (gb[1] - ga[1]) * f}
            half -= l
    c0 = x.get("center")
    if c0: return c0
    b = x.get("bounds")
    return {"lat": (b["minlat"] + b["maxlat"]) / 2, "lon": (b["minlon"] + b["maxlon"]) / 2} if b else None

# ---------------------------------------------------------------- answer obfuscation (anti-peek, not security)
def xor_pack(obj, date):
    raw = json.dumps(obj, separators=(",", ":")).encode()
    key = f"analyst-eye:{date}".encode()
    return base64.b64encode(bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))).decode()

# ---------------------------------------------------------------- build one day
def load_history():
    p = os.path.join(GEN, "history.json")
    return json.load(open(p)) if os.path.exists(p) else {"used": {}, "days": {}}

def save_history(h):
    json.dump(h, open(os.path.join(GEN, "history.json"), "w"), indent=1, sort_keys=True)

def day_number(date):
    return (date - dt.date.fromisoformat(S["launch_date"])).days + 1

def build_pool(data, hist):
    """Eligible candidates by category (applies size/tag filters, manual rejects and history dedupe)."""
    used = hist["used"]
    names_used = {v.get("key") for v in used.values()}
    pool = {}
    for x in data["cands"]:
        t = x.get("tags", {}); c = cat_of(t)
        if not c: continue
        oid = f"{x['type']}/{x['id']}"
        if oid in used or oid in BL.get("osm_ids", []): continue   # manual rejects
        if re.search(BL["name_regex"], " ".join([t.get("name", ""), t.get("operator", "")])): continue
        if t.get("access") in ("private", "military", "no"): continue
        if c == "runway" and (t.get("surface") in ("grass", "dirt", "unpaved") or "water" in t.get("surface", "")): continue
        if c == "storage_tank" and t.get("content") in ("gas", "fuel", "oil", "lpg"): pass  # allowed; refineries excluded by area
        if c == "mast" and _num(t.get("height")) < 40: continue   # only tall masts cast a findable shadow
        size_m = extent_m(x)
        if c == "pier" and size_m < 60 and not t.get("name"): continue        # skip tiny private docks
        if c == "solar" and t.get("power") != "plant" and size_m < 80: continue  # skip rooftop panels
        if c in ("bridge", "cemetery") and size_m < 80: continue                 # tiny culverts / family plots
        if c == "roundabout" and size_m < 25: continue                           # mini traffic circles
        if c in ("tennis", "pool") and size_m < 20: continue
        if c == "golf" and not 12 <= size_m <= 80: continue                      # real putting greens only
        # fairness: a target whose outline spans most of the photo makes the round trivial
        if c not in ("runway", "pier", "mast", "lighthouse", "water_tower") and size_m > 0.7 * SIZE * CATS[c]["gsd"]: continue
        if c in ("storage_tank",) and x["type"] == "way" and size_m < 12: continue
        cen = feature_point(x, c)
        if not cen: continue
        k = f"{c}:{t.get('name','').lower()}" if t.get("name") else None
        if k and k in names_used: continue
        pool.setdefault(c, []).append((x, cen, k))
    for c in pool: pool[c].sort(key=lambda z: (z[0]["type"], z[0]["id"]))
    return pool, names_used, used

def build_day(date, data, shapes, hist):
    ds = date.isoformat()
    rng = random.Random(int(hashlib.sha256(f"analyst-eye/{ds}".encode()).hexdigest(), 16))
    pool, names_used, used = build_pool(data, hist); cats = sorted(pool)
    log(f"[{ds}] pool: " + ", ".join(f"{c}={len(pool[c])}" for c in cats))
    # Ramp: rounds 1-2 easy, 3-4 medium, 5 hard (TIERS on the 0-100 difficulty score).
    # One round per type per day; each type at most max_per_week times in any 7 days (previous 6 days counted).
    # If a tier can't be filled: widen the band, then relax the weekly cap; give up (day fails) after that.
    cap0 = S.get("max_per_week", 2)
    recent = {}
    for i in range(1, 7):
        for c0 in hist["days"].get((date - dt.timedelta(days=i)).isoformat(), []): recent[c0] = recent.get(c0, 0) + 1
    rounds, chosen = [], set()
    center = {"easy": 0.0, "medium": 0.5, "hard": 1.0}
    for tier in SLOTS:
        lo, hi = TIERS[tier]; got = None
        for cap, widen in ((cap0, 0), (cap0, 5), (cap0 + 1, 5), (cap0 + 1, 10)):
            band = (max(0, lo - widen), min(100, hi + widen))
            ok_cats = [c for c in cats if recent.get(c, 0) < cap and c not in chosen]
            rng.shuffle(ok_cats)   # likely types first (by prior), random within
            ok_cats.sort(key=lambda c: abs((CATS[c]["diff"] - 1) / 2 - center[tier]) + rng.random() * 0.6)
            for c in ok_cats:
                cand_list = pool[c][:]; rng.shuffle(cand_list)
                for x, cen, k in cand_list[:40]:
                    r = make_round(ds, len(rounds) + 1, c, CATS[c], x, cen, shapes, rng, data, band)
                    if r:
                        got = r; used[f"{x['type']}/{x['id']}"] = {"date": ds, "key": k, "cat": c}
                        if k: names_used.add(k)
                        break
                if got: break
            if got: break
            log(f"  {tier}: nothing in {band} with weekly cap {cap}; widening")
        if not got: raise RuntimeError(f"could not fill a {tier} round for {ds}")
        got["_slot"] = len(rounds); got["tier"] = tier; rounds.append(got); chosen.add(got["category"])   # slot tier wins if the band was widened
        log(f"  {tier}: {got['category']} difficulty {got['dscore']}")
    if len(rounds) < S["rounds_per_day"]:
        raise RuntimeError(f"only {len(rounds)} rounds for {ds}")
    rounds.sort(key=lambda r: (r["_slot"] // 2 if r["_slot"] < 4 else 2, r["dscore"]))   # tiers in order, easier first within a tier
    for i, r in enumerate(rounds, 1):
        old = r["image"]; new = f"img/{ds}-{i}.jpg"
        os.replace(os.path.join(PUZ, old), os.path.join(PUZ, new))
        r["image"] = new; r["round"] = i; r.pop("_tie"); r.pop("_slot", None)
    puzzle = {"date": ds, "number": day_number(date), "region": S["region"]["name"], "size": SIZE,
              "rounds": [{k: v for k, v in r.items() if k != "secret_plain"} for r in rounds],
              "attribution": "Imagery: USDA NAIP via USGS The National Map (public domain). Targets: © OpenStreetMap contributors, ODbL.",
              "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    for r, rr in zip(puzzle["rounds"], rounds): r["secret"] = xor_pack(rr["secret_plain"], ds)
    with open(os.path.join(PUZ, f"{ds}.json"), "w") as f: json.dump(puzzle, f, indent=1)
    with open(os.path.join(PUZ, f"{ds}.js"), "w") as f:
        f.write("(window.AE_PUZZLES=window.AE_PUZZLES||{})[%s]=%s;\n" % (json.dumps(ds), json.dumps(puzzle, separators=(",", ":"))))
    hist["days"][ds] = [r["category"] for r in rounds]
    log(f"[{ds}] OK: " + ", ".join(r["category"] for r in rounds))
    return puzzle

_BYCAT = {}
def same_type(data, c):
    if not _BYCAT:
        for y in data["cands"]:
            cc = cat_of(y.get("tags", {}))
            if cc: _BYCAT.setdefault(cc, []).append(y)
    return _BYCAT.get(c, [])

def alternates(data, c, x, px):
    """Other OSM features of the same type visible in the chip -> also accepted as correct."""
    out = []
    for y in same_type(data, c):
        if y["type"] == x["type"] and y["id"] == x["id"]: continue
        pt = feature_point(y, c)
        if not pt: continue
        a = px(pt["lat"], pt["lon"])
        geom, gtype = [], "point"
        if y["type"] == "way" and y.get("geometry"):
            geom = [px(p["lat"], p["lon"]) for p in y["geometry"] if p]
            closed = len(geom) > 3 and y["geometry"][0] == y["geometry"][-1]
            gtype = "polygon" if closed and c not in ("runway", "pier") else "line"
        pts = geom or [a]
        if not any(-8 <= u <= SIZE + 8 and -8 <= v <= SIZE + 8 for u, v in pts + [a]): continue
        out.append({"answer": a, "geom": geom, "gtype": gtype, "name": y.get("tags", {}).get("name")})
    return out

def ambiguity(ans, alts, gsd, link_m=60):
    """-> (sites, raw): same-type features in frame, with features < link_m apart merged into one site."""
    pts = [ans] + [a["answer"] for a in alts]; parent = list(range(len(pts)))
    def f(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i in range(len(pts)):
        for j in range(i):
            if math.dist(pts[i], pts[j]) * gsd < link_m: parent[f(i)] = f(j)
    return len({f(i) for i in range(len(pts))}), len(alts)

MAX_SITES, MAX_ALTS = 3, 6

# ---------------------------------------------------------------- difficulty model
# Things that look alike from above; other-type features from the same group in frame count as distractors.
LOOKALIKE = [{"baseball", "soccer", "football", "track", "stadium", "tennis"}, {"storage_tank", "wastewater", "water_tower", "pool"},
             {"pier", "slipway", "marina", "bridge"}, {"substation", "solar"}, {"mast", "lighthouse", "water_tower"},
             {"golf", "cemetery"}, {"roundabout", "storage_tank"}]
NODE_SIZE_M = {"water_tower": 14, "mast": 4, "lighthouse": 8, "storage_tank": 15, "slipway": 10, "marina": 80,
               "wastewater": 100, "stadium": 120, "solar": 60, "pool": 15}
TIERS = {"easy": (0, 29), "medium": (30, 49), "hard": (50, 100)}   # calibrated on the Gulf Coast pool
SLOTS = ["easy", "easy", "medium", "medium", "hard"]
W_SIZE, W_ZOOM, W_DISTR, W_VIS, W_PRIOR = .28, .18, .18, .16, .20
clamp = lambda v, a=0.0, b=1.0: max(a, min(b, v))

def target_size_m(x, c):
    e = extent_m(x)
    return e if e > 0 else NODE_SIZE_M.get(c, 20)

def lookalikes(data, c, px):
    group = set().union(*[g for g in LOOKALIKE if c in g]) - {c}
    n = 0
    for cc in group:
        for y in same_type(data, cc):
            pt = feature_point(y, cc)
            if pt:
                u, v = px(pt["lat"], pt["lon"])
                if 0 <= u <= SIZE and 0 <= v <= SIZE: n += 1
    return n

def pre_difficulty(c, x, gsd, alts, ans, n_look):
    """Difficulty parts that need no imagery. -> dict of 0..1 terms"""
    size = target_size_m(x, c); frac = clamp(size / (SIZE * gsd), 1e-4, 1)
    size_t = clamp((math.log(0.35) - math.log(frac)) / (math.log(0.35) - math.log(0.02)))
    screen_px = size / gsd * 340 / SIZE                      # on a ~340 px phone-sized photo
    zoom_t = clamp((40 - screen_px) / 30)
    distr_t = clamp(n_look / 5)
    sites, _ = ambiguity(ans, alts, gsd)
    bonus = min(0.2, 0.08 * (sites - 1))                     # more accepted targets = easier
    return {"size": size_t, "zoom": zoom_t, "distract": distr_t, "prior": (CATS[c]["diff"] - 1) / 2, "bonus": bonus,
            "size_m": round(size), "screen_px": round(screen_px), "lookalikes": n_look, "sites": sites}

def visibility(img, ans, size_px):
    """0 = invisible .. 1 = pops out: target patch vs. its surroundings."""
    g = img.convert("L"); rp = int(clamp(size_px / 2, 6, 60)); x, y = int(ans[0]), int(ans[1])
    box = lambda r: (max(0, x - r), max(0, y - r), min(SIZE, x + r), min(SIZE, y + r))
    inner = ImageStat.Stat(g.crop(box(rp))); outer = ImageStat.Stat(g.crop(box(2 * rp)))
    n_in = (box(rp)[2] - box(rp)[0]) * (box(rp)[3] - box(rp)[1]); n_out = (box(2 * rp)[2] - box(2 * rp)[0]) * (box(2 * rp)[3] - box(2 * rp)[1])
    ring_mean = (outer.mean[0] * n_out - inner.mean[0] * n_in) / max(1, n_out - n_in)
    return clamp(abs(inner.mean[0] - ring_mean) / 40 + inner.stddev[0] / 60)

def combine(parts, vis=None):
    lowvis = 0.5 if vis is None else 1 - vis
    v = (W_SIZE * parts["size"] + W_ZOOM * parts["zoom"] + W_DISTR * parts["distract"] + W_VIS * lowvis
         + W_PRIOR * parts["prior"] - parts["bonus"])
    return round(100 * clamp(v))
   # more look-alikes than this in one photo = trivial round -> pick another chip

def make_round(ds, idx, c, cfg, x, cen, shapes, rng, data=None, band=None):
    lat, lon = cen["lat"], cen["lon"]; gsd = cfg["gsd"]
    k = 1 / math.cos(math.radians(lat))
    half_merc = SIZE / 2 * gsd * k
    fx, fy = rng.uniform(0.18, 0.82), rng.uniform(0.18, 0.82)
    tx, ty = merc(lat, lon)
    xmin = tx - fx * 2 * half_merc; xmax = xmin + 2 * half_merc
    ymax = ty + fy * 2 * half_merc; ymin = ymax - 2 * half_merc
    clat, clon = unmerc((xmin + xmax) / 2, (ymin + ymax) / 2)
    ok, why = chip_is_clear(shapes, clat, clon, SIZE / 2 * gsd, S["chip_margin_m"])
    if not ok:
        log(f"    skip {c} {x['type']}/{x['id']}: near sensitive '{why}'"); return None
    def px(la, lo):
        X, Y = merc(la, lo)
        return [round((X - xmin) / (xmax - xmin) * SIZE, 1), round((ymax - Y) / (ymax - ymin) * SIZE, 1)]
    ans = px(lat, lon)
    geom, gtype = [], "point"
    if x["type"] == "way" and x.get("geometry"):
        geom = [px(p["lat"], p["lon"]) for p in x["geometry"]]
        closed = len(geom) > 3 and x["geometry"][0] == x["geometry"][-1]
        gtype = "polygon" if closed and c not in ("runway", "pier") else "line"
        if gtype == "polygon":   # use pole-ish point: centroid may fall outside concave shapes; keep OSM center
            pass
        # clip silly geometry that is mostly off-chip (huge features): keep anyway, scoring handles it
    alts = alternates(data, c, x, px) if data else []
    sites, raw = ambiguity(ans, alts, gsd)
    if sites > MAX_SITES or raw > MAX_ALTS:
        log(f"    skip {c} {x['type']}/{x['id']}: {raw} look-alikes in frame ({sites} sites)"); return None
    parts = pre_difficulty(c, x, gsd, alts, ans, lookalikes(data, c, px) if data else 0)
    if band:   # cheap pre-check: visibility can move the score by at most +/- W_VIS*50
        lo_s, hi_s = combine(parts, 1.0), combine(parts, 0.0)
        if hi_s < band[0] or lo_s > band[1]: return None
    try:
        img = naip_chip(xmin, ymin, xmax, ymax)
    except Exception as e:
        log(f"    skip {c}: imagery error {e}"); return None
    ok, why = quality_ok(img, int(ans[0]), int(ans[1]), c)
    if not ok:
        log(f"    skip {c} {x['type']}/{x['id']}: QC {why}"); return None
    vis = visibility(img, ans, parts["size_m"] / gsd)
    dscore = combine(parts, vis)
    if band and not band[0] <= dscore <= band[1]:
        log(f"    skip {c} {x['type']}/{x['id']}: difficulty {dscore} outside {band}"); return None
    meta = naip_meta(lat, lon)
    t = x.get("tags", {})
    base = template_note(c, t, rng, meta)
    note = grok_note(c, t, base, meta) or base
    tmp = f"img/_tmp-{ds}-{idx}.jpg"
    os.makedirs(IMG, exist_ok=True)
    img.save(os.path.join(PUZ, tmp), quality=S["jpeg_quality"], optimize=True, progressive=True)
    r_px = round(cfg["r_m"] / gsd, 1)
    hr = round(SIZE * 0.2); ang = rng.uniform(0, 2 * math.pi); off = rng.uniform(0.15, 0.6) * hr
    hint = [round(min(SIZE - hr * 0.5, max(hr * 0.5, ans[0] + off * math.cos(ang)))),
            round(min(SIZE - hr * 0.5, max(hr * 0.5, ans[1] + off * math.sin(ang)))), hr]
    secret = {"answer": ans, "geom": geom, "gtype": gtype,
              "halfwidth_px": round(cfg.get("halfwidth_m", 0) / gsd, 1), "hint": hint,
              "name": t.get("name"), "lat": round(lat, 5), "lon": round(lon, 5),
              "osm": f"https://www.openstreetmap.org/{x['type']}/{x['id']}", "note": note,
              "naip": meta, "alts": alts,
              "chip_merc": [round(v, 2) for v in (xmin, ymin, xmax, ymax)]}
    return {"round": idx, "category": c, "label": cfg["label"], "task": cfg["task"], "image": tmp,
            "gsd_m": gsd, "radius_px": r_px, "difficulty": cfg["diff"],
            "dscore": dscore, "tier": next(k for k, (a, b) in TIERS.items() if a <= dscore <= b),
            "dparts": {**{k: (round(v, 2) if isinstance(v, float) else v) for k, v in parts.items()}, "visibility": round(vis, 2)},
            "imagery_date": (meta or {}).get("acquired"), "secret_plain": secret, "_tie": rng.random()}

def replace_round(spec, data, shapes, hist):
    """--replace 2026-10-21:3 -> swap one round for another feature of the same type (keeps the rest of the day)."""
    ds, n = spec.split(":"); n = int(n); date = dt.date.fromisoformat(ds)
    P = json.load(open(os.path.join(PUZ, f"{ds}.json"))); old = P["rounds"][n - 1]; c = old["category"]
    rng = random.Random(f"replace/{ds}/{n}/{len(hist['used'])}")
    pool, names_used, used = build_pool(data, hist)
    cand = pool.get(c, [])[:]; rng.shuffle(cand)
    for x, cen, k in cand[:40]:
        r = make_round(ds, n, c, CATS[c], x, cen, shapes, rng, data, TIERS.get(old.get("tier")))
        if not r: continue
        os.replace(os.path.join(PUZ, r["image"]), os.path.join(PUZ, old["image"]))
        r["image"] = old["image"]; r["round"] = n; r.pop("_tie"); r.pop("_slot", None); sp = r.pop("secret_plain")
        r["secret"] = xor_pack(sp, ds); P["rounds"][n - 1] = r
        used[f"{x['type']}/{x['id']}"] = {"date": ds, "key": k, "cat": c}
        with open(os.path.join(PUZ, f"{ds}.json"), "w") as f: json.dump(P, f, indent=1)
        with open(os.path.join(PUZ, f"{ds}.js"), "w") as f:
            f.write("(window.AE_PUZZLES=window.AE_PUZZLES||{})[%s]=%s;\n" % (json.dumps(ds), json.dumps(P, separators=(",", ":"))))
        log(f"[{ds}] round {n} ({c}) replaced with {x['type']}/{x['id']}"); return
    raise RuntimeError(f"no replacement found for {spec}")

def refresh_day(ds, data):
    P = json.load(open(os.path.join(PUZ, f"{ds}.json")))
    key = f"analyst-eye:{ds}".encode()
    for r in P["rounds"]:
        sp = json.loads(bytes(b ^ key[i % len(key)] for i, b in enumerate(base64.b64decode(r["secret"]))))
        c = r["category"]; cfg = CATS[c]; gsd = r["gsd_m"]
        if "chip_merc" in sp: xmin, ymin, xmax, ymax = sp["chip_merc"]
        else:   # rebuild the footprint from the answer pixel (lat/lon stored to 1e-5 deg, < 1 px error)
            k = 1 / math.cos(math.radians(sp["lat"])); span = SIZE * gsd * k; X, Y = merc(sp["lat"], sp["lon"])
            xmin = X - sp["answer"][0] / SIZE * span; xmax = xmin + span; ymax = Y + sp["answer"][1] / SIZE * span; ymin = ymax - span
            sp["chip_merc"] = [round(v, 2) for v in (xmin, ymin, xmax, ymax)]
        def px(la, lo, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax):
            X, Y = merc(la, lo); return [round((X - xmin) / (xmax - xmin) * SIZE, 1), round((ymax - Y) / (ymax - ymin) * SIZE, 1)]
        tp, tid = sp["osm"].rsplit("/", 2)[-2:]
        sp["alts"] = alternates(data, c, {"type": tp, "id": int(tid)}, px)
        r["task"] = cfg["task"]; r["label"] = cfg["label"]; r["secret"] = xor_pack(sp, ds)
        if sp["alts"]: log(f"[{ds}] round {r['round']} {c}: {len(sp['alts'])} more in frame")
    with open(os.path.join(PUZ, f"{ds}.json"), "w") as f: json.dump(P, f, indent=1)
    with open(os.path.join(PUZ, f"{ds}.js"), "w") as f:
        f.write("(window.AE_PUZZLES=window.AE_PUZZLES||{})[%s]=%s;\n" % (json.dumps(ds), json.dumps(P, separators=(",", ":"))))

def write_index():
    days = sorted(f[:-5] for f in os.listdir(PUZ) if re.match(r"\d{4}-\d{2}-\d{2}\.json$", f))
    idx = {"launch": S["launch_date"], "dates": days}
    json.dump(idx, open(os.path.join(PUZ, "index.json"), "w"), indent=1)
    open(os.path.join(PUZ, "index.js"), "w").write("window.AE_INDEX=%s;\n" % json.dumps(idx))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date"); ap.add_argument("--start"); ap.add_argument("--days", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--replace", help="DATE:N  swap one round (same type), e.g. 2026-10-21:3. Add the bad id to blocklist osm_ids first.")
    ap.add_argument("--refresh", nargs="+", metavar="DATE", help="recompute accepted same-type features + task text for existing days")
    a = ap.parse_args()
    if a.refresh:
        data = fetch_osm(); [refresh_day(d, data) for d in a.refresh]; return
    if a.replace:
        data = fetch_osm(); hist = load_history(); replace_round(a.replace, data, bad_shapes(data["bad"]), hist); save_history(hist); return
    if a.date: dates = [dt.date.fromisoformat(a.date)]
    else:
        start = dt.date.fromisoformat(a.start) if a.start else max(central_today(), dt.date.fromisoformat(S["launch_date"]))
        n = a.days if a.days else S["days_ahead"] + (0 if a.start else 1)
        dates = [start + dt.timedelta(days=i) for i in range(n)]
    todo = [d for d in dates if a.force or not os.path.exists(os.path.join(PUZ, f"{d.isoformat()}.json"))]
    if not todo:
        log("nothing to do"); write_index(); return
    data = fetch_osm(); shapes = bad_shapes(data["bad"]); hist = load_history()
    failures = 0
    for d in todo:
        try:
            build_day(d, data, shapes, hist); save_history(hist)
        except Exception as e:
            failures += 1; log(f"[{d}] FAILED: {e}")
    for f in os.listdir(IMG):
        if f.startswith("_tmp-"): os.remove(os.path.join(IMG, f))
    write_index()
    sys.exit(1 if failures == len(todo) else 0)

if __name__ == "__main__":
    main()
