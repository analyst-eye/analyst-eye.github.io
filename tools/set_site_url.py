#!/usr/bin/env python3
"""Write the public site URL into config.js and every HTML meta tag.
   python3 tools/set_site_url.py                       # use SITE_URL already in config.js
   python3 tools/set_site_url.py https://you.github.io/analyst-eye/
Meta tags are marked with  data-ae-url="..."  attributes so this is idempotent."""
import glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = os.path.join(ROOT, "config.js"); src = open(cfg).read()
url = sys.argv[1] if len(sys.argv) > 1 else re.search(r'SITE_URL:\s*"([^"]+)"', src).group(1)
if not url.startswith("https://"): sys.exit("SITE_URL must start with https://")
if not url.endswith("/"): url += "/"
open(cfg, "w").write(re.sub(r'SITE_URL:\s*"[^"]*"', f'SITE_URL: "{url}"', src))
for page in ["index.html", "embed.html", "hidden.html"] + sorted(os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(ROOT, "p", "*.html"))):
    p = os.path.join(ROOT, page); h = open(p).read()
    # <meta ... data-ae-url="embed.html" content="https://.../embed.html">
    h = re.sub(r'(<meta[^>]*data-ae-url="([^"]*)"[^>]*content=")[^"]*(")',
               lambda m: m.group(1) + url + m.group(2) + m.group(3), h)
    h = re.sub(r'(<link rel="canonical"[^>]*data-ae-url="([^"]*)"[^>]*href=")[^"]*(")',
               lambda m: m.group(1) + url + m.group(2) + m.group(3), h)
    open(p, "w").write(h)
print("SITE_URL set to", url)
