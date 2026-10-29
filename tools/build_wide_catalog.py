#!/usr/bin/env python3
"""Builds generator/curated/wide_catalog.json: the vetted candidates for the "wide" puzzle types (landforms, aircraft,
vehicles, rail/quarry/silo). Run by hand (needs network for --bulk only); the nightly generator never calls this.

  python3 tools/build_wide_catalog.py [--bulk raw/bulk.json]

* PINS / RINGS / PLANES below are hand-verified against NAIP photos (a contact sheet of each was looked at before it was added).
* --bulk is the output of tools/fetch_wide_bulk.py (OSM parking lots, garages, quarries, rail yards, silos in the Gulf bbox).
* Planes: only civilian airports; the builder refuses any plane within 8 km of a known military airfield. Labels are generic
  ("airliner", "small airplane", "parked airplanes") and each has a confidence: >= 0.95 -> "approved" (auto), 0.80-0.94 -> "flagged"
  (needs AJ's OK; the generator skips it), < 0.80 -> dropped.
"""
import argparse, json, math, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "generator", "curated", "wide_catalog.json")

def px2ll(lat0, lon0, gsd, x, y, view=512):
    """pixel (x, y) of a `view`-px wide rendering of a 768-px chip centred on (lat0, lon0) -> (lat, lon)."""
    mpp = 768 / view * gsd
    dx = (x - view / 2) * mpp; dy = (view / 2 - y) * mpp
    return lat0 + dy / 111320.0, lon0 + dx / (111320.0 * math.cos(math.radians(lat0)))

def ring_from_px(lat0, lon0, gsd, pts, view=512):
    r = [list(px2ll(lat0, lon0, gsd, x, y, view)) for x, y in pts]
    return [[round(a, 6), round(b, 6)] for a, b in r + [r[0]]]

# ---- landforms: point pins (lat, lon) with scale gsd (m/px of the puzzle photo) and accepted radius r_m
# (id, cat, name, lat, lon, gsd, r_m, size_m, diff_add, note)
PINS = [
 ("sunset_crater", "volcano", "Sunset Crater, Arizona", 35.3647, -111.5008, 4, 450, 1200, 0, None),
 ("capulin", "volcano", "Capulin Volcano, New Mexico", 36.7819, -103.9703, 4, 400, 900, 0, None),
 ("lava_butte", "volcano", "Lava Butte, Oregon", 43.9184, -121.3564, 4, 250, 500, 5, None),
 ("amboy", "volcano", "Amboy Crater, California", 34.5457, -115.7911, 3, 250, 450, 10, None),
 ("shiprock", "mesa", "Shiprock, New Mexico", 36.6879, -108.8349, 6, 300, 600, 15, "A dark, jagged rock tower standing alone, with thin straight walls of rock fanning out from it like spokes."),
 ("devils_tower", "mesa", "Devils Tower, Wyoming", 44.5902, -104.7145, 3, 150, 300, 5, "A steep-sided stump of grey rock with a pale ring of rubble around it, surrounded by pine forest."),
 ("courthouse_butte", "mesa", "Courthouse Butte, Arizona", 34.8008, -111.7557, 3, 200, 400, 0, None),
 ("scotts_bluff", "mesa", "Scotts Bluff, Nebraska", 41.8319, -103.7071, 3, 350, 700, 15, "A pale bluff with a cliff edge and a road looping up to its flat top."),
 ("horseshoe_bend", "meander", "Horseshoe Bend, Arizona", 36.8808, -111.5202, 3, 700, 1200, 0, None),
 ("goosenecks", "meander", "Goosenecks of the San Juan, Utah", 37.1699, -109.9324, 4, 350, 1500, 5, None),
 ("jourdan_bend", "meander", "Jourdan River bend, Mississippi", 30.4640, -89.0124, 3, 120, 350, 5, "A dark river doubling back on itself in a tight loop, with houses on the land inside the bend."),
 ("wax_lake", "delta", "Wax Lake Delta, Louisiana", 29.52, -91.43, 8, 2000, 4000, 5, None),
 ("birdfoot", "delta", "Mississippi River bird's-foot delta, Louisiana", 29.1, -89.2, 20, 5000, 12000, 10, None),
 ("tensaw", "delta", "Mobile-Tensaw Delta, Alabama", 30.78, -87.98, 10, 3000, 6000, 15, None),
]

# ---- landforms scored on an outline (display-pixel polygons from the verified preview)
# (id, cat, name, lat0, lon0, gsd, view_px, polygon px, r_m, size_m, diff_add, note)
RINGS = [
 ("lake_providence", "oxbow", "Lake Providence, Louisiana", 32.82, -91.19, 6, 768,
  [(0,140),(70,215),(140,265),(210,330),(290,375),(380,420),(445,445),(520,465),(560,480),(600,520),(630,570),(640,610),(600,600),(540,570),(490,555),(420,535),(330,505),(230,478),(170,445),(110,400),(50,355),(0,320)],
  60, 2500, 0, "A long curved lake that used to be a bend of the Mississippi, with a town along its far shore."),
 ("chandeleur", "sandbar", "Chandeleur Islands, Louisiana", 29.87, -88.84, 6, 512,
  [(395,20),(410,15),(385,150),(360,260),(330,380),(300,490),(240,495),(250,420),(300,330),(310,260),(340,200),(350,120)],
  80, 3500, 0, "A long, thin ribbon of pale sand running down the photo with the open Gulf on one side and shallow water on the other."),
]

# ---- dune fields, scored on an outline drawn on the verified view; the photo is kept on that view (view + jit), because the
# field fills most of the frame and the outline is only known inside it. polygons run slightly past the frame edge on purpose.
# (id, name, lat0, lon0, gsd, view_px, polygon px, size_m, diff_add, note)
DUNE_RINGS = [
 ("coral_pink", "Coral Pink Sand Dunes, Utah", 37.0368, -112.7237, 4, 512,
  [(345,-40),(552,-40),(552,50),(430,150),(370,260),(320,350),(290,440),(250,550),(75,550),(110,430),(150,350),(190,270),(235,190),(285,100)],
  1500, 0, "A long band of smooth orange sand ridges, running diagonally between scrub desert and dark red cliffs."),
 ("sleeping_bear", "Sleeping Bear Dunes, Michigan", 44.88, -86.06, 4, 512,
  [(105,-40),(470,-40),(480,100),(420,200),(380,300),(330,380),(280,440),(240,550),(130,550),(110,300)],
  1800, 5, "A wide belt of pale, rumpled sand and scrubby patches, between a long beach on a deep-blue lake and the dark forest."),
 ("great_sand_dunes", "Great Sand Dunes, Colorado", 37.7916, -105.5943, 14, 512,
  [(190,40),(552,40),(552,552),(170,552),(150,430),(95,330),(95,250),(130,150)],
  6000, 10, "A vast, pale field of wind-rippled sand heaped against the foot of a dark mountain range."),
]
DROP = {"mesquite_flat", "amboy", "tensaw", "false_river"}   # amboy: mapped inside/next to Twentynine Palms Marine base training area -> no military proximity   # dune field fills the frame at any usable scale: no edge to draw an outline on
VIEW_PINS = {"wax_lake", "birdfoot", "tensaw", "horseshoe_bend", "goosenecks", "jourdan_bend"}   # big accept circles: keep the vetted view (jit 0.12)
LOTS_UNSURE = {"parking_lot-w436876533", "parking_lot-w743185191", "parking_lot-w1057500866", "parking_lot-w1206957283"}   # other equally full lots in frame that aren't mapped
HOLD_NOTE = "other equally full, unmapped lots in the photo, so 'the' lot would be ambiguous"

# ---- aircraft (civilian airports only). (id, cat, airport, lat0, lon0, gsd, view_px, (x, y), r_m, size_m, confidence, note)
PLANES = []
def planes(cat, airport, lat0, lon0, gsd, pts, r_m, size_m, conf, note, tag, view=512, start=0):
    for i, (x, y) in enumerate(pts, start):
        la, lo = px2ll(lat0, lon0, gsd, x, y, view)
        PLANES.append((f"{tag}{i+1}", cat, airport, round(la, 6), round(lo, 6), gsd, r_m, size_m, conf, note))
planes("airliner", "Louis Armstrong New Orleans International", 29.9942, -90.2558, 0.4, [(210,192),(205,258),(455,365)],
       25, 36, 0.97, "A big jet with swept wings, parked nose-in beside the terminal's long finger of gates.", "msyA")
planes("airliner", "Louis Armstrong New Orleans International", 29.9880, -90.2590, 0.4, [(910-512,150)],
       25, 36, 0.97, "A big blue-and-white jet parked on the concrete beside a round, teal-roofed gate building.", "msyB")
planes("small_plane", "Louis Armstrong New Orleans International (cargo ramp)", 29.9965, -90.2640, 0.4, [(108,38),(190,45),(45,128),(75,138)],
       12, 15, 0.95, "A small white airplane, shaped like a cross, parked on a huge empty slab of concrete.", "msyC")
PLANES.append(("msyC5", "small_plane", "Louis Armstrong New Orleans International (cargo ramp)", 29.997998, -90.264307, 0.4, 12, 15, 0.95,
               "A small white airplane, shaped like a cross, parked on a huge empty slab of concrete."))  # 5th plane on same ramp, found in overlay review
# Lakefront Airport (KNEW) removed 2026-10-29: next to the UNO / NIWC Atlantic Navy area
planes("small_plane", "Hattiesburg-Laurel Regional", 31.4690, -89.3335, 0.3, [(60,238),(55,300),(130,285),(130,333)],
       10, 12, 0.95, "A small white airplane, shaped like a cross, parked on the apron beside a hangar.", "pib")
# every other airliner visible around the MSY terminal piers (768-px tiles, gsd 0.4): all of them are accepted answers
_MSY = "Louis Armstrong New Orleans International"; _N = "A big jet with swept wings, parked beside the terminal's long finger of gates."
for _tag, (_la, _lo), _pts in [("msyD", (29.9954, -90.2540), [(265, 530)]), ("msyE", (29.9927, -90.2570), [(100, 100)]),
        ("msyF", (29.9927, -90.2540), [(605, 285), (540, 350), (150, 465)]), ("msyG", (29.9927, -90.2510), [(210, 295), (190, 400)]),
        ("msyH", (29.9900, -90.2570), [(215, 490)])]:
    planes("airliner", _MSY, _la, _lo, 0.4, _pts, 25, 36, 0.97, _N, _tag, view=768)
PLANE_RINGS = [  # (id, airport, lat0, lon0, gsd, polygon px, conf, note)
 ("pibRamp", "Hattiesburg-Laurel Regional", 31.4690, -89.3335, 0.3, [(30,215),(165,215),(165,355),(30,355)], 0.96,
  "Four small white airplanes parked in a tight group on pale pavement beside a big hangar."),
 ("msyRamp", "Louis Armstrong New Orleans International (cargo ramp)", 29.9965, -90.2640, 0.4, [(20,20),(220,20),(220,160),(20,160)], 0.95,
  "A small cluster of white airplanes parked together on a very wide concrete apron."),
]
# military airfields in and around the Gulf region: planes must stay >= 8 km away from all of them
MIL_AIRFIELDS = [("NAS JRB New Orleans (Belle Chasse)", 29.8258, -90.0350), ("Keesler AFB", 30.4104, -88.9244),
 ("Gulfport-Biloxi (joint-use, CRTC)", 30.4073, -89.0701), ("NAS Pensacola (Forrest Sherman)", 30.3503, -87.3187),
 ("NAS Whiting Field", 30.7239, -87.0219), ("Eglin AFB", 30.4833, -86.5254), ("Hurlburt Field", 30.4278, -86.6893),
 ("Camp Shelby (Bobby L. Chain)", 31.1560, -89.0690), ("Stennis Space Center", 30.3700, -89.5900),
 ("NOLA Naval Support (Michoud)", 30.0200, -89.9200), ("Fort Polk (Polk AAF)", 31.0450, -93.1900),
 ("Barksdale AFB", 32.5018, -93.6627), ("Columbus AFB", 33.6438, -88.4438), ("Meridian NAS", 32.5521, -88.5560),
 ("Maxwell AFB", 32.3830, -86.3650), ("Brookley / Mobile ANG", 30.6268, -88.0680)]
MIL_KM = 8.0
HOLD = {"scotts_bluff", "goosenecks", "jourdan_bend"}   # goosenecks/jourdan: several equally tight bends in the frame -> "the" bend is ambiguous   # the bluff doesn't read clearly from straight above at 3 m/px

def hav(a, b, c, d):
    p = math.pi / 180; x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))

def mil_clear(lat, lon): return all(hav(lat, lon, la, lo) >= MIL_KM for _, la, lo in MIL_AIRFIELDS)

# ---- OSM bulk (Gulf) -> candidates
GULF = (29.85, -90.35, 30.75, -87.45)
def area_m2(ring):
    la0 = sum(p[0] for p in ring) / len(ring); k = 111320.0
    pts = [((lo) * k * math.cos(math.radians(la0)), la * k) for la, lo in ring]
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2

def ring_of(e):
    g = e.get("geometry")
    if g and len(g) >= 4 and (g[0]["lat"], g[0]["lon"]) == (g[-1]["lat"], g[-1]["lon"]):
        return [[p["lat"], p["lon"]] for p in g]
    if e["type"] == "relation":
        for m in e.get("members", []):
            if m.get("role") == "outer" and m.get("geometry"):
                g = m["geometry"]
                if len(g) >= 4 and (g[0]["lat"], g[0]["lon"]) == (g[-1]["lat"], g[-1]["lon"]): return [[p["lat"], p["lon"]] for p in g]
    return None

def simplify(ring, tol_m=2.0):
    out = [ring[0]]
    for p in ring[1:-1]:
        if math.hypot((p[0] - out[-1][0]) * 111320, (p[1] - out[-1][1]) * 96000) >= tol_m: out.append(p)
    out.append(ring[0]); return out if len(out) >= 4 else ring

def bulk_entries(path, rng, per_kind=None, keep=None, kinds=("lot",)):
    B = json.load(open(path)); out = []
    keep = keep or {}
    per_kind = per_kind or {"lot": 90, "garage": 40, "quarry": 25, "yard": 20, "silo": 25}
    spec = {  # kind -> (cat, area range m2, name, note, diff_add)
     "lot": ("parking_lot", (1200, 60000), "Parking lot", "A big paved lot filled with rows of tiny, colorful cars.", 0),
     "garage": ("parking_garage", (1800, 16000), "Parking garage", "A large flat-roofed block whose top level is striped with parking lines and dotted with cars.", 0),
     "quarry": ("quarry", (20000, 1500000), "Quarry", "A pale, bare pit with terraced walls and gravel piles, with no buildings in it.", 0),
     "yard": ("railyard", (30000, 600000), "Rail yard", "A wide stretch where many railroad tracks run side by side and split apart.", 0),
     "silo": ("silo", (0, 100000), "Grain silos", "A group of round tops with long, thin shadows, standing beside a long building or a railroad.", 0)}
    for kind, items in B.items():
        if kind not in kinds: continue
        cat, (lo, hi), nm, note, dadd = spec[kind]; cand = []
        seen = set()
        for e in items:
            if (e["type"], e["id"]) in seen: continue
            seen.add((e["type"], e["id"])); t = e.get("tags", {})
            if t.get("access") in ("private", "no", "customers", "permissive") and kind == "lot": continue
            if t.get("military") or "military" in str(t.get("operator", "")).lower(): continue
            c = e.get("center") or ({"lat": e["lat"], "lon": e["lon"]} if "lat" in e else None)
            if not c and e.get("bounds"):
                b = e["bounds"]; c = {"lat": (b["minlat"] + b["maxlat"]) / 2, "lon": (b["minlon"] + b["maxlon"]) / 2}
            if not c or not (GULF[0] <= c["lat"] <= GULF[2] and GULF[1] <= c["lon"] <= GULF[3]): continue
            r = ring_of(e)
            if kind == "silo":
                if r and area_m2(r) > hi: continue
                cand.append((e, None, c)); continue
            if not r: continue
            a = area_m2(r)
            if not lo <= a <= hi: continue
            cand.append((e, r, c))
        rng.shuffle(cand)
        alt_only = []
        if cat in keep:   # hand-reviewed keepers only (tools/curate_lots.py); every other mapped lot stays in as an accepted look-alike
            ok = set(keep[cat]); alt_only = [z for z in cand if f"{cat}-{z[0]['type'][0]}{z[0]['id']}" not in ok]
            cand = [z for z in cand if f"{cat}-{z[0]['type'][0]}{z[0]['id']}" in ok]
        for e, r, c in cand[:per_kind[kind]]:
            ent = dict(id=f"{cat}-{e['type'][0]}{e['id']}", cat=cat, name=e.get("tags", {}).get("name") if kind in ("quarry", "yard") else None,
                       note=None, status="approved", url=f"https://www.openstreetmap.org/{e['type']}/{e['id']}")
            if r: ent["ring"] = [[round(a, 6), round(b, 6)] for a, b in simplify(r)]
            else: ent["lat"], ent["lon"] = round(c["lat"], 6), round(c["lon"], 6)
            if kind == "silo": ent["r_m"] = 18
            out.append(ent)
        for e, r, c in alt_only:
            out.append(dict(id=f"{cat}-{e['type'][0]}{e['id']}", cat=cat, status="alt", ring=[[round(a, 6), round(b, 6)] for a, b in simplify(r)]))
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--bulk", nargs="*"); ap.add_argument("--keep"); ap.add_argument("--kinds", default="lot"); ap.add_argument("--seed", type=int, default=29); a = ap.parse_args()
    rng = random.Random(a.seed); E = []
    for id_, cat, name, la, lo, gsd, r_m, size, dadd, note in PINS:
        E.append(dict(id=id_, cat=cat, name=name, lat=la, lon=lo, gsd=gsd, r_m=r_m, size_m=size, diff_add=dadd, note=note, status="approved"))
    for id_, cat, name, la0, lo0, gsd, view, poly, r_m, size, dadd, note in RINGS:
        E.append(dict(id=id_, cat=cat, name=name, ring=ring_from_px(la0, lo0, gsd, poly, view), gsd=gsd, r_m=r_m, size_m=size, diff_add=dadd, note=note, status="approved"))
    for id_, name, la0, lo0, gsd, view, poly, size, dadd, note in DUNE_RINGS:
        E.append(dict(id=id_, cat="dune", name=name, ring=ring_from_px(la0, lo0, gsd, poly, view), view=[la0, lo0], jit=0.06, gsd=gsd,
                      r_m=60, size_m=size, diff_add=dadd, note=note, status="approved"))
    try:   # False River: real outline from OSM relation 19370506 (saved as a simplified ring)
        fr = json.load(open(os.path.join(HERE, "..", "generator", "curated", "false_river_ring.json")))
        E.append(dict(id="false_river", cat="oxbow", name="False River, Louisiana", ring=fr, gsd=20, r_m=80, size_m=3000, diff_add=0,
                      note="A big crescent-shaped lake wrapped around a patch of farmland, once a bend of the Mississippi.",
                      status="approved", url="https://www.openstreetmap.org/relation/19370506"))
    except Exception as ex: print("false river ring missing:", ex)
    dropped = []
    for id_, cat, ap_, la, lo, gsd, r_m, size, conf, note in PLANES:
        st = "approved" if conf >= 0.95 else "flagged" if conf >= 0.80 else None
        if not mil_clear(la, lo): dropped.append((id_, "within 8 km of a military airfield")); continue
        if st is None: dropped.append((id_, f"confidence {conf}")); continue
        E.append(dict(id=id_, cat=cat, name=ap_, lat=la, lon=lo, gsd=gsd, r_m=r_m, size_m=size, diff_add=0, note=note, status=st, conf=conf))
    for id_, ap_, la0, lo0, gsd, poly, conf, note in PLANE_RINGS:
        if not mil_clear(la0, lo0): dropped.append((id_, "military")); continue
        st = "approved" if conf >= 0.95 else "flagged"
        E.append(dict(id=id_, cat="plane_ramp", name=ap_, ring=ring_from_px(la0, lo0, gsd, poly), gsd=gsd, r_m=20, size_m=80, diff_add=0, note=note, status=st, conf=conf))
    keep = json.load(open(a.keep)) if a.keep else {}
    for bp in a.bulk or []:
        if os.path.exists(bp): E += bulk_entries(bp, rng, keep=keep, kinds=a.kinds.split(","))
    E = [e for e in E if e["id"] not in DROP]
    for e in E:
        if e["id"] in VIEW_PINS: e["view"] = [e["lat"], e["lon"]]; e["jit"] = 0.12
        if e["id"] in LOTS_UNSURE: e["status"] = "flagged"; e["hold"] = HOLD_NOTE
    for e in E:   # pins I looked at and am not sure show the feature at this scale: held back for AJ
        if e["id"] in HOLD: e["status"] = "flagged"
    sp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "generator", "curated", "safety_sweep.json")
    if os.path.exists(sp):   # OSM sweep for military / prison / refinery / nuclear features around each non-lot pin; only "clean" stays enabled
        SW = json.load(open(sp))["entries"]
        for e in E:
            if e["cat"] == "parking_lot" or e.get("status") != "approved": continue
            v = SW.get(e["id"], "not swept")
            if v != "clean": e["status"] = "disabled"; e["hold"] = "safety sweep: " + v
    for e in E:   # no empty names/notes keys
        for k in ("note", "name"):
            if e.get(k) is None: e.pop(k, None)
    json.dump({"_comment": "Vetted targets for the 'wide' puzzle types. Built by tools/build_wide_catalog.py. status: approved = usable; flagged = aircraft label 80-94% sure, waiting for AJ.",
               "entries": E, "bad": [], "decoys": []}, open(OUT, "w"), indent=0, separators=(",", ":"))
    from collections import Counter
    print(len(E), "entries", dict(Counter(e["cat"] for e in E)), "dropped:", dropped)
if __name__ == "__main__": main()
