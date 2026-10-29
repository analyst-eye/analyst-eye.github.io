"""Turn the OSM safety-sweep results (one small-bbox Overpass query per pin: military, prison, refinery, nuclear)
into generator/curated/safety_sweep.json and enable/disable the matching wide_catalog.json entries.
Usage: apply_sweep.py <sweep_results.json>   (results: {id: {ok: bool|None, hits: [[type,id,name,kind,dist_m,bounds],...]}})"""
import json, sys, os
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "generator", "curated")
R = json.load(open(sys.argv[1])); cat_p = os.path.join(root, "wide_catalog.json"); C = json.load(open(cat_p))
S = {}
for e in C["entries"]:
    if e["cat"] == "parking_lot": continue
    r = R.get(e["id"])
    if not r or r.get("ok") is None: v = "incomplete (Overpass unavailable)"
    else:
        bad = [h for h in r["hits"] if h[3] != "police"]   # police stations are informational only
        v = "clean" if not bad else "hits: " + "; ".join(f"{h[2] or h[0]+'/'+str(h[1])} ({h[3]})" for h in bad)
    S[e["id"]] = v
    if e.get("status") in ("approved", "disabled"):
        if v == "clean": e["status"] = "approved"; e.pop("hold", None)
        else: e["status"] = "disabled"; e["hold"] = "safety sweep: " + v
json.dump({"_comment": "OSM sweep for military/prison/refinery/nuclear features near each non-lot catalog pin. Only 'clean' entries are enabled; re-run tools/apply_sweep.py when Overpass is back.", "entries": S}, open(os.path.join(root, "safety_sweep.json"), "w"), indent=0)
json.dump(C, open(cat_p, "w"), indent=0, separators=(",", ":"))
print({k: sum(1 for x in S.values() if (x == "clean") == (k == "clean")) for k in ("clean", "not")})
