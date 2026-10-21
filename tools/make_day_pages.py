#!/usr/bin/env python3
"""Per-day share pages + card images, one per puzzle day.
   p/YYYY-MM-DD.html     : the full game (same as index.html) with its own X player card / og tags
   assets/cards/DATE.jpg : 1200x900 card (640x480 player aspect): round 1 photo, no marker, "Puzzle #N: can you find the <target>?"
   python3 tools/make_day_pages.py            # every day in puzzles/index.json (cards rebuilt only when round 1 changes)
   python3 tools/make_day_pages.py --force    # rebuild every card
Run automatically at the end of generator/make_puzzle.py. Future days are safe to publish: the page and card name
only the round 1 target TYPE and show its (already public) photo; answers stay packed in puzzles/*.js."""
import hashlib, html, json, os, re, sys
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUZ, PAGES, CARDS = (os.path.join(ROOT, d) for d in ("puzzles", "p", "assets/cards"))
MANIFEST = os.path.join(CARDS, "manifest.json")
CARD_VERSION = 1   # bump to rebuild every card after a design change
W, H = 1200, 900
A, C, Wt, D = (255, 176, 46), (90, 209, 230), (220, 231, 238), (138, 160, 176)

def font(sz, bold=True):
    for p in (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"] if bold else
              ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]):
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    try: return ImageFont.load_default(sz)
    except TypeError: return ImageFont.load_default()
def mono(sz):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"]:
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    return font(sz)

def wrap(d, text, f, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width or not cur: cur = t
        else: lines.append(cur); cur = w
    return lines + ([cur] if cur else [])

def make_card(src, number, label, out):
    """Photo + question only. Deliberately no crosshair, ring, pin or any mark that could point at the answer."""
    card = Image.new("RGB", (W, H), (10, 16, 22)); d = ImageDraw.Draw(card)
    for x in range(0, W, 40): d.line([(x, 0), (x, H)], fill=(16, 28, 36))
    for y in range(0, H, 40): d.line([(0, y), (W, y)], fill=(16, 28, 36))
    im = Image.open(src).convert("RGB"); s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2)).resize((660, 660), Image.LANCZOS)
    card.paste(im, (40, 120)); d.rectangle([40, 120, 700, 780], outline=A, width=3)
    d.text((40, 40), "ANALYST EYE", font=mono(56), fill=A)
    d.text((740, 140), f"Puzzle #{number}", font=font(34, False), fill=D)
    y = 200
    for line in wrap(d, f"Can you find the {label.lower()}?", font(52), 420):
        d.text((740, y), line, font=font(52), fill=Wt); y += 64
    y += 40
    for line in ["5 aerial photos", "30 seconds each", "New puzzle daily"]:
        d.text((740, y), line, font=font(30, False), fill=D); y += 46
    d.text((740, max(y + 30, 690)), "Tap to play ▶", font=font(36), fill=C)
    d.text((40, 820), "Imagery: USDA NAIP via USGS  ·  Map data: © OpenStreetMap contributors  ·  @A_is_A", font=font(21, False), fill=D)
    card.save(out, "JPEG", quality=86, optimize=True, progressive=True)

def meta_sub(h, attr, key, value):
    pat = re.compile(r'<meta %s="%s"[^>]*>' % (attr, re.escape(key)))
    assert pat.search(h), key
    return pat.sub(lambda m: value, h, count=1)

def url_meta(attr, key, rel, site):
    return f'<meta {attr}="{key}" data-ae-url="{html.escape(rel)}" content="{html.escape(site + rel)}">'

def make_page(tpl, site, ds, number, label, card_rel):
    q = f"Can you find the {label.lower()}?"
    title = f"Analyst Eye #{number}: can you find the {label.lower()}?"
    desc = f"Puzzle #{number}. 5 aerial photos, 30 seconds each. First up: find the {label.lower()}. Free daily spotting game."
    e = html.escape
    h = tpl.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<base href="../">', 1)
    h = re.sub(r"<title>.*?</title>", f"<title>{e(title)}</title>", h, count=1)
    h = meta_sub(h, "name", "description", f'<meta name="description" content="{e(desc)}">')
    h = re.sub(r'<link rel="canonical"[^>]*>', f'<link rel="canonical" data-ae-url="p/{ds}.html" href="{e(site)}p/{ds}.html">', h, count=1)
    h = h.replace("<!-- X player card: X loads embed.html inside the post. URLs are rewritten by tools/set_site_url.py -->",
                  f"<!-- Per-day page for {ds} (tools/make_day_pages.py). X loads embed.html?date={ds} inside the post. -->")
    h = meta_sub(h, "name", "twitter:title", f'<meta name="twitter:title" content="{e(title)}">')
    h = meta_sub(h, "name", "twitter:description", f'<meta name="twitter:description" content="{e(desc)}">')
    h = meta_sub(h, "name", "twitter:player", url_meta("name", "twitter:player", f"embed.html?date={ds}", site))
    h = meta_sub(h, "name", "twitter:image", url_meta("name", "twitter:image", card_rel, site))
    h = meta_sub(h, "name", "twitter:image:alt", f'<meta name="twitter:image:alt" content="{e(f"Aerial photo from Analyst Eye puzzle #{number}: {q}")}">')
    h = meta_sub(h, "property", "og:title", f'<meta property="og:title" content="{e(title)}">')
    h = meta_sub(h, "property", "og:description", f'<meta property="og:description" content="{e(desc)}">')
    h = meta_sub(h, "property", "og:url", url_meta("property", "og:url", f"p/{ds}.html", site))
    h = meta_sub(h, "property", "og:image", url_meta("property", "og:image", card_rel, site))
    h = h.replace('<body data-mode="full">', f'<body data-mode="full" data-day="{ds}">', 1)
    assert f'data-day="{ds}"' in h and '<base href="../">' in h
    return h

def main(force=False):
    site = re.search(r'SITE_URL:\s*"([^"]+)"', open(os.path.join(ROOT, "config.js")).read()).group(1)
    tpl = open(os.path.join(ROOT, "index.html")).read()
    dates = json.load(open(os.path.join(PUZ, "index.json")))["dates"]
    os.makedirs(PAGES, exist_ok=True); os.makedirs(CARDS, exist_ok=True)
    man = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {}
    for ds in dates:
        P = json.load(open(os.path.join(PUZ, f"{ds}.json"))); r1 = P["rounds"][0]
        src = os.path.join(PUZ, r1["image"]); label = r1["label"]; number = P["number"]
        key = hashlib.sha1(open(src, "rb").read() + f"|{number}|{label}|{CARD_VERSION}".encode()).hexdigest()[:10]
        out = os.path.join(CARDS, f"{ds}.jpg")
        if force or man.get(ds) != key or not os.path.exists(out):
            make_card(src, number, label, out); man[ds] = key; print("card", out, file=sys.stderr)
        page = make_page(tpl, site, ds, number, label, f"assets/cards/{ds}.jpg?v={key}")
        pp = os.path.join(PAGES, f"{ds}.html")
        if not os.path.exists(pp) or open(pp).read() != page: open(pp, "w").write(page); print("page", pp, file=sys.stderr)
    # retired days (removed from the index) lose their page and card
    for f in os.listdir(PAGES):
        if f.endswith(".html") and f[:-5] not in dates: os.remove(os.path.join(PAGES, f))
    for f in os.listdir(CARDS):
        if f.endswith(".jpg") and f[:-4] not in dates: os.remove(os.path.join(CARDS, f)); man.pop(f[:-4], None)
    json.dump(dict(sorted(man.items())), open(MANIFEST, "w"), indent=1)

if __name__ == "__main__":
    main(force="--force" in sys.argv)
