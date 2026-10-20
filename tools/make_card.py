#!/usr/bin/env python3
"""Make assets/card.png (the poster X shows before the player loads). 1200x900 = 640x480 aspect.
   python3 tools/make_card.py [puzzles/img/2026-10-19-1.jpg]"""
import glob, os, sys
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob(os.path.join(ROOT, "puzzles/img/*-1.jpg")))[0]
W, H = 1200, 900
card = Image.new("RGB", (W, H), (10, 16, 22)); d = ImageDraw.Draw(card)
for x in range(0, W, 40): d.line([(x, 0), (x, H)], fill=(16, 28, 36))
for y in range(0, H, 40): d.line([(0, y), (W, y)], fill=(16, 28, 36))
chip = Image.open(src).convert("RGB").resize((660, 660))
card.paste(chip, (40, 120)); d.rectangle([40, 120, 700, 780], outline=(255, 176, 46), width=3)
A = (255, 176, 46); C = (90, 209, 230); Wt = (220, 231, 238); D = (138, 160, 176)
cx, cy = 370, 450
d.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], outline=A, width=6)
for a, b in (((cx - 110, cy), (cx - 70, cy)), ((cx + 70, cy), (cx + 110, cy)), ((cx, cy - 110), (cx, cy - 70)), ((cx, cy + 70), (cx, cy + 110))):
    d.line([a, b], fill=A, width=6)
def font(sz, bold=True):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"]:
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    return ImageFont.load_default()
d.text((40, 40), "ANALYST EYE", font=font(56), fill=A)
d.text((740, 150), "Daily aerial", font=font(40), fill=Wt)
d.text((740, 200), "spotting game", font=font(40), fill=Wt)
y = 300
for line in ["5 targets / day", "30 s each", "Score /500", "Same set for all", "Tap to play ▶"]:
    d.text((740, y), line, font=font(32, False), fill=C if "play" in line else D); y += 58
d.text((40, 820), "Imagery: USDA NAIP via USGS  ·  Targets: © OpenStreetMap contributors  ·  @A_is_A", font=font(22, False), fill=D)
out = os.path.join(ROOT, "assets/card.png"); card.save(out, optimize=True); print(out)
