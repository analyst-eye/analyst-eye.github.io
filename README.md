# Analyst Eye 🛰️

**Play:** https://analyst-eye.github.io/ · X player card: https://analyst-eye.github.io/embed.html

A daily aerial-imagery spotting game. Five overhead images a day, one target each: tap it, score up to 100 per round (accuracy 80 + speed bonus 20, hint −25), then share a Wordle-style result on X.

* **Static site** (GitHub Pages): `index.html` (full game) and `embed.html` (640×480 X player-card view)
* **Fully automated content**: a nightly GitHub Action builds puzzles from **OpenStreetMap** targets and **USDA NAIP** imagery (public domain), commits them, and redeploys.
* No servers, no accounts, no tracking. Stats and streaks live in the player's browser (localStorage).

Made by [@A_is_A](https://x.com/A_is_A). Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright). Imagery: USDA NAIP via USGS The National Map.

---

## 5-minute setup

1. **Create the repo.** On GitHub: *New repository* → name it `analyst-eye` → **Public** → no README → *Create*.
2. **Push this folder.**
   ```bash
   cd analyst-eye
   git init -b main && git add -A && git commit -m "Analyst Eye"
   git remote add origin https://github.com/<YOUR-USERNAME>/analyst-eye.git
   git push -u origin main
   ```
3. **Turn on Pages via Actions.** Repo → *Settings → Pages → Build and deployment → Source:* **GitHub Actions**.
4. **Allow the bot to commit.** *Settings → Actions → General → Workflow permissions:* **Read and write permissions** → *Save*.
5. **Deploy now.** *Actions → "Daily puzzle + deploy" → Run workflow*. When it's done your game is at
   `https://<YOUR-USERNAME>.github.io/analyst-eye/`

(If the very first push already started a deploy run before Pages was switched on, it just fails; the manual run in step 5 fixes it.)

That's it. Every night at 05:00 UTC (midnight CDT, 11 pm CST) the workflow fills in any missing puzzles for today plus the next 7 days, commits them, and redeploys.

### The public URL (one setting)
X reads the `twitter:player` / `twitter:image` meta tags **without running JavaScript**, so they must contain the absolute URL.
* **Default:** do nothing. The deploy job reads your Pages URL and writes it into `config.js` and the meta tags of the deployed copy (`tools/set_site_url.py`).
* **Custom domain or different URL:** either set a repo variable *Settings → Secrets and variables → Actions → Variables →* `SITE_URL` = `https://your.domain/` , **or** edit `SITE_URL` in **`config.js`** and run `python3 tools/set_site_url.py` before committing.

### Posting it on X
Post the exact final URL, e.g. `https://<YOUR-USERNAME>.github.io/analyst-eye/` (https, trailing slash, no redirects). X should render a player card that runs `embed.html` inside the post on desktop; on mobile people see `assets/card.png`, tap, and X's panel opens the game (it covers the bottom ~30%, so all key UI is in the top 70%).
Player-card rendering for arbitrary domains is **not officially documented** by X anymore; indie sites were confirmed working in Oct 2026. If the card doesn't render, the link still works as a normal page.

### Optional: Grok-written clues
Add a repo secret `XAI_API_KEY` (*Settings → Secrets and variables → Actions → New repository secret*). The generator then asks Grok (`AE_GROK_MODEL`, default `grok-4.7`) to rewrite each templated clue as one short plain-English sentence, using only the OSM tags as facts. Without the key, the built-in templates are used.

---

## How it works

| Path | What |
|---|---|
| `index.html`, `embed.html` | Game pages (same code, different layout). Player-card meta tags are at the top. |
| `config.js` | **Single config**: `SITE_URL`, handle, launch date (#1), timezone, timer, hint penalty. |
| `assets/app.js`, `assets/style.css` | The game. No frameworks, no network calls besides loading `puzzles/*.js` and images. |
| `assets/card.png` | Poster image for the X card (`python3 tools/make_card.py` to rebuild). |
| `puzzles/YYYY-MM-DD.json` / `.js` | One day = 5 rounds. `.js` is loaded with a `<script>` tag so it works inside X's sandboxed iframe. Answers are XOR/base64-packed to stop casual peeking (not secure). |
| `puzzles/img/` | 768×768 NAIP chips (~100–170 KB each). |
| `puzzles/index.js` | List of available dates. |
| `generator/make_puzzle.py` | The generator (see below). |
| `generator/settings.json` | Region bbox, rounds/day, image size, Overpass mirrors, NAIP endpoint. |
| `generator/blocklist.json` | Manual exclusions (name regex + boxes). Add anything you never want shown. |
| `generator/history.json` | OSM features already used (no repeats). |
| `.github/workflows/daily.yml` | Nightly generate → commit → deploy; manual run; deploy on push. |
| `tools/` | `set_site_url.py`, `make_card.py`, `contact_sheet.py` (QA: draws answers on every image). |
| `tests/smoke.py` | Headless Playwright test that plays full games (mobile, desktop, 640×480 embed, sandboxed iframe), including pinch/wheel/button zoom, drag-to-pan (must not drop a pin) and tap-to-guess. Screenshots go to `screens/v2-*`. |

### Generator pipeline
1. **Overpass API** (3 tiles, falls back across mirrors with backoff, cached 20 h): 21 everyday target types: stadiums, runways, marinas, golf putting greens, baseball fields, sports fields (soccer and football merged, since line markings aren't reliable at 0.6 m), running tracks, cemeteries, water treatment plants, piers (≥60 m), bridges, roundabouts, named swimming pools, tennis courts, water towers, storage tanks, solar farms, substations, boat ramps, lighthouses (≥150 m cemeteries; ≥80 m bridges). Radio masts are excluded: from straight overhead they are a thin pole with no visible footprint.
2. **Sensitive-site exclusion**: anything tagged `landuse=military`, `military=*`, prisons, nuclear plants, refineries, military-named aerodromes, plus `blocklist.json`. A round is rejected if any of those lies **inside the image footprint or within 150 m of it**, so excluded sites never appear in frame even at the edge. Names matching the blocklist regex are skipped too.
3. **Imagery**: `exportImage` from `https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer` (USDA NAIP, public domain). Target placed off-center; answer pixel and outline computed from Web-Mercator math.
4. **QC**: rejects no-data/blank, low-contrast, badly exposed chips and featureless target patches, then tries another feature.
5. **Metadata**: NAIP tile acquisition date via the service's `identify` catalog (behind the small ⓘ on the photo); omitted if unavailable.
6. **Clues**: one short, plain-English sentence per type about what it looks like from above; optional Grok rewrite.
7. **Variety**: each type at most once per day and at most `max_per_week` (default 2) times in any 7 days (`settings.json`); if the pool ever runs dry the cap relaxes by one and the log says so. Rounds are ordered easy → hard (2 easy, 2 medium, 1 hard).
8. **Look-alikes**: every other OSM feature of the same type inside the photo is stored and also scores as correct (nearest one wins; all are revealed). Photos with more than 3 separate sites or 6 extra copies are skipped as too easy. Golf is a *putting green* (not the whole course), and any polygon target spanning most of the photo is skipped.
9. **Difficulty ramp**: each candidate gets a 0–100 difficulty score from target size vs. frame, whether you need to zoom on a phone, look-alike distractors of other types in frame, how much the target stands out from its surroundings, and a per-type prior (fewer accepted copies = harder). Each day is rounds 1–2 Easy (0–29), 3–4 Medium (30–49), 5 Hard (50+); `TIERS` in `make_puzzle.py`. If a tier can't be filled the band widens by 5–10 points, then the weekly cap relaxes; the day fails if it still can't. Practice mode (only) lets players pick Easy / Medium / Hard / Mixed, built from past days.
10. **Fix one round**: `python3 generator/make_puzzle.py --replace 2026-10-21:3` swaps a single round for another of the same type and tier. Add `--any` to allow any type that isn't already in that day and is under the weekly cap.
11. **Distinctness check**: every candidate is measured against its surroundings (color inside vs. a ring around the outline, edge strength along it, or patch vs. ring for points). Below 0.3 it is rejected, so targets that blend into their background never ship.
11. **Manual rejects**: add `"way/123"`-style ids to `osm_ids` in `blocklist.json` to never use a feature again.

Run locally:
```bash
pip install requests pillow
python3 generator/make_puzzle.py                       # fill today..+7 (US Central)
python3 generator/make_puzzle.py --date 2026-11-01 --force
python3 tools/contact_sheet.py 2026-11-01              # eyeball the answers
python3 -m http.server 8000                            # then open http://localhost:8000/?today=2026-10-19
```
`?today=YYYY-MM-DD` simulates a date for testing; `?date=YYYY-MM-DD` plays a past day as practice.

### Change the region
Edit `region.bbox` (`[south, west, north, east]`) in `generator/settings.json`. Imagery is US-only (NAIP). Review `blocklist.json` for the new area.

### Known limitations
* GitHub pauses scheduled workflows in repos with no activity for 60 days. The nightly bot commit normally keeps it active; if it ever pauses, re-enable it on the Actions tab.
* OSM positions can be off by a few metres and NAIP is a 2–3-year cycle, so features may be newer or older than the photo. Scoring uses the outline when OSM has one, with a generous radius.
* Future puzzles are in the public repo; the packing only stops casual peeking.
* Repo size grows ~0.7 MB/day (~250 MB/year). Prune old `puzzles/img` after a year, or lower `jpeg_quality`.
* Public Overpass servers are shared. One nightly run is well within their usage policy; don't point the game itself at Overpass.

### Data & licences
* OpenStreetMap data © OpenStreetMap contributors, available under the [ODbL](https://www.openstreetmap.org/copyright). Credit is shown in the site footer.
* NAIP imagery: USDA Farm Production and Conservation, distributed by USGS The National Map; public domain.
