#!/usr/bin/env python3
"""Install one hidden (LiDAR reveal) round into the site.
   python3 tools/make_hidden.py YYYY-MM-DD /path/to/rounds/<id>      # round dir from ae-lidar/weekly/build_round.py
Writes hidden/img/DATE-photo.jpg, DATE-lidar.jpg, hidden/DATE.js (answer packed like puzzles/*.js) and refreshes hidden/index.js.
The date must be a Sunday (US Central). Safe to publish ahead: the page only names the target type; the geometry is XOR-packed
with 'analyst-eye:hidden:DATE' (the same casual-cheat protection the daily puzzles have; the repo itself is public)."""
import base64, datetime, glob, json, os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); H = os.path.join(ROOT, "hidden")
def pack(obj, ds):
    raw = json.dumps(obj, separators=(",", ":")).encode(); key = ("analyst-eye:hidden:" + ds).encode()
    return base64.b64encode(bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))).decode()
def main(ds, rd):
    if datetime.date.fromisoformat(ds).weekday() != 6: sys.exit(f"{ds} is not a Sunday")
    r = json.load(open(os.path.join(rd, "round.json"))); os.makedirs(os.path.join(H, "img"), exist_ok=True)
    shutil.copy(os.path.join(rd, "photo.jpg"), os.path.join(H, "img", f"{ds}-photo.jpg")); shutil.copy(os.path.join(rd, "lidar.jpg"), os.path.join(H, "img", f"{ds}-lidar.jpg"))
    secret = dict(answers=r["answers"], radius_px=r["radius_px"], reveal=r["reveal"], noun=r["noun"], note=r["note"])
    pub = dict(date=ds, size=r["size"], gsd_m=r["gsd_m"], prompt=r["prompt"], photo=f"img/{ds}-photo.jpg", lidar=f"img/{ds}-lidar.jpg", secret=pack(secret, ds),
               attribution=r["credit"])
    open(os.path.join(H, f"{ds}.js"), "w").write('(window.AE_HIDDEN=window.AE_HIDDEN||{})["%s"]=%s;\n' % (ds, json.dumps(pub, separators=(",", ":"))))
    dates = sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(H, "20??-??-??.js")))
    open(os.path.join(H, "index.js"), "w").write("window.AE_HIDDEN_INDEX=%s;\n" % json.dumps({"dates": dates}))
    print("installed", ds, "->", dates)
if __name__ == "__main__": main(sys.argv[1], sys.argv[2])
