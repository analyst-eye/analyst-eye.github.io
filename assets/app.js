/* Analyst Eye: static, framework-free. Works sandboxed (no forms, no login, no fetch needed). */
(() => {
"use strict";
const C = window.AE_CONFIG || {}, IDX = window.AE_INDEX || { dates: [] };
const MODE = document.body.dataset.mode || "full";
const EMBED = MODE === "embed";
const app = document.getElementById("app");
const qs = new URLSearchParams(location.search);
const ROUND_S = C.ROUND_SECONDS || 30, HINT_PEN = C.HINT_PENALTY || 25;
const SITE = (C.SITE_URL || location.href.replace(/[^/]*$/, ""));

/* ---------- layout: photo beside the panel in wide, short frames (style.css body.split) ---------- */
const SPLIT_MQ = matchMedia(EMBED ? "(min-aspect-ratio: 1/1) and (min-width: 560px)" : "(orientation: landscape) and (max-height: 560px) and (min-width: 560px)");
const setSplit = () => document.body.classList.toggle("split", SPLIT_MQ.matches);
setSplit();
if (SPLIT_MQ.addEventListener) SPLIT_MQ.addEventListener("change", setSplit); else if (SPLIT_MQ.addListener) SPLIT_MQ.addListener(setSplit);

/* ---------- storage (falls back to memory when sandboxed) ---------- */
const mem = {};
const store = {
  get(k) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : null; } catch (e) { return k in mem ? mem[k] : null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { mem[k] = v; } }
};

/* Saved data is user-editable (devtools), so validate it before use: garbage is ignored, never crashes or renders as HTML. */
const num = (v, lo, hi, dflt = 0) => (typeof v === "number" && isFinite(v)) ? Math.min(hi, Math.max(lo, v)) : dflt;
const isDay = v => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v);
function cleanResult(r) {
  if (!r || typeof r !== "object") return null;
  const c = Array.isArray(r.click) && r.click.length === 2 ? r.click.map(v => num(v, -1e4, 1e4)) : [0, 0];
  return { d: num(r.d, 0, 1e5), acc: num(r.acc, 0, 80), speed: num(r.speed, 0, 20), hint: r.hint === true,
    score: Math.round(num(r.score, 0, 100)), t: num(r.t, 0, 1e4), ti: Math.round(num(r.ti, 0, 999)), click: c,
    dk: Number.isInteger(r.dk) && r.dk >= 0 && r.dk < 20 ? r.dk : -1 };
}
function loadDay(ds, n) {
  const v = store.get("ae:day:" + ds);
  if (!v || typeof v !== "object" || !Array.isArray(v.results)) return null;
  const results = v.results.slice(0, n).map(cleanResult);
  if (results.some(r => !r)) return null;
  return { results, done: results.length >= n };
}
function loadStats() {
  const v = store.get("ae:stats"), st = { played: 0, streak: 0, maxStreak: 0, best: 0, bestDate: null, last: null, hist: {} };
  if (!v || typeof v !== "object") return st;
  st.played = Math.round(num(v.played, 0, 1e6)); st.streak = Math.round(num(v.streak, 0, 1e6));
  st.maxStreak = Math.round(num(v.maxStreak, 0, 1e6)); st.best = Math.round(num(v.best, 0, 1e6));
  st.bestDate = isDay(v.bestDate) ? v.bestDate : null; st.last = isDay(v.last) ? v.last : null;
  if (v.hist && typeof v.hist === "object") for (const [d, sc] of Object.entries(v.hist)) if (isDay(d) && typeof sc === "number" && isFinite(sc)) st.hist[d] = Math.round(num(sc, 0, 1e6));
  return st;
}

/* ---------- dates (US Central) ---------- */
const fmt = new Intl.DateTimeFormat("en-CA", { timeZone: C.TIMEZONE || "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit" });
const centralToday = () => fmt.format(new Date());
const addDays = (ds, n) => { const d = new Date(ds + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const dayNum = ds => Math.round((Date.parse(ds + "T12:00:00Z") - Date.parse((C.LAUNCH_DATE || IDX.launch) + "T12:00:00Z")) / 864e5) + 1;
const nice = ds => new Date(ds + "T12:00:00Z").toLocaleDateString("en-US", { timeZone: "UTC", month: "short", day: "numeric", year: "numeric" });
function untilMidnight() {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: C.TIMEZONE || "America/Chicago", hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })
    .formatToParts(new Date()).map(x => [x.type, x.value]));
  let s = 86400 - ((+p.hour % 24) * 3600 + (+p.minute) * 60 + (+p.second));
  const h = Math.floor(s / 3600); s -= h * 3600; const m = Math.floor(s / 60);
  return `${h}h ${String(m).padStart(2, "0")}m`;
}

/* ---------- helpers ---------- */
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { app.className = "app"; app.innerHTML = html; return app; };
const toast = (msg) => { const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 1600); };
function decode(secret, ds) {
  const raw = atob(secret), key = new TextEncoder().encode("analyst-eye:" + ds);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i) ^ key[i % key.length];
  return JSON.parse(new TextDecoder().decode(bytes));
}
function loadPuzzle(ds) {
  return new Promise((res, rej) => {
    const have = window.AE_PUZZLES && window.AE_PUZZLES[ds]; if (have) return res(have);
    const s = document.createElement("script"); s.src = `puzzles/${ds}.js`;
    s.onload = () => (window.AE_PUZZLES && window.AE_PUZZLES[ds]) ? res(window.AE_PUZZLES[ds]) : rej(new Error("empty"));
    s.onerror = () => rej(new Error("missing")); document.head.appendChild(s);
  });
}

/* ---------- scoring ---------- */
function segDist(p, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy;
  const t = L ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L)) : 0;
  return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
}
function inPoly(p, poly) {
  let ins = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > p[1]) !== (yj > p[1]) && p[0] < (xj - xi) * (p[1] - yi) / (yj - yi + 1e-9) + xi) ins = !ins;
  }
  return ins;
}
function distOne(p, t, hw) {
  let d = Math.hypot(p[0] - t.answer[0], p[1] - t.answer[1]);
  const g = t.geom || [];
  if (t.gtype === "polygon" && g.length > 2 && inPoly(p, g)) return 0;
  if (g.length > 1) {
    let m = Infinity; for (let i = 1; i < g.length; i++) m = Math.min(m, segDist(p, g[i - 1], g[i]));
    if (t.gtype === "line") m = Math.max(0, m - (hw || 0));
    d = Math.min(d, m);
  }
  return d;
}
// every same-type feature in the photo counts: score against the nearest one
const targets = s => [s, ...(s.alts || [])];
function nearest(p, s) {
  let best = { d: Infinity, i: 0 };
  targets(s).forEach((t, i) => { const d = distOne(p, t, s.halfwidth_px); if (d < best.d) best = { d, i }; });
  return best;
}
function distance(p, s) { return nearest(p, s).d; }
// decoy rounds: look-alikes of another type are in the photo; a pin on one (and nearer to it than to any target) scores 0
function decoyHit(p, s, dTarget) {
  let hit = -1, best = Infinity;
  (s.decoys || []).forEach((dc, i) => { const d = distOne(p, dc, dc.halfwidth_px); if (d <= (dc.r || 8) && d < dTarget && d < best) { best = d; hit = i; } });
  return hit;
}
function score(p, s, R, t, hint) {
  const nb = nearest(p, s), d = nb.d, dk = decoyHit(p, s, d);
  if (dk >= 0) return { d: Math.round(d), acc: 0, speed: 0, hint: !!hint, score: 0, t: Math.round(t * 10) / 10, ti: nb.i, dk };
  const acc = d <= R ? 80 : Math.max(0, 80 * (1 - (d - R) / (5 * R)));
  const speed = acc > 0 ? 20 * Math.max(0, Math.min(1, (ROUND_S - t) / (ROUND_S - 5))) * (acc / 80) : 0;
  const total = Math.max(0, Math.round(acc + speed - (hint ? HINT_PEN : 0)));
  return { d: Math.round(d), acc: Math.round(acc), speed: Math.round(speed), hint: !!hint, score: Math.min(100, total), t: Math.round(t * 10) / 10, ti: nb.i, dk: -1 };
}
const sq = s => s >= 80 ? "🟦" : s >= 40 ? "🟧" : "⬛";
const cls = s => s >= 80 ? "good" : s >= 40 ? "ok" : "miss";
const TIER_NAME = { easy: "Easy", medium: "Medium", hard: "Hard" };
const TIER_SHORT = { easy: "Easy", medium: "Med", hard: "Hard" };
const isTier = t => Object.prototype.hasOwnProperty.call(TIER_NAME, t);
const verdict = s => s >= 90 ? "Bullseye!" : s >= 70 ? "Nice!" : s >= 40 ? "Close!" : s > 0 ? "Not quite" : "Missed it";

/* ---------- state ---------- */
let G = null;   // { ds, P, practice, i, results }
// ?today= is a testing override; on the public site it can only go back in time, never unlock future puzzles
const LOCAL = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname) || location.protocol === "file:";
const QT = qs.get("today"), REAL_TODAY = centralToday();
const TODAY = (isDay(QT) && (LOCAL || QT <= REAL_TODAY)) ? QT : REAL_TODAY;
const avail = (IDX.dates || []).filter(d => d <= TODAY).sort();

async function init() {
  const req = qs.get("date"), pt = qs.get("practice");
  if (pt && isTier(pt)) return startTier(pt);
  if (req && avail.includes(req) && req !== TODAY) return start(req, true);
  if (avail.includes(TODAY)) return start(TODAY, false);
  const next = (IDX.dates || []).find(d => d > TODAY);
  h(`<div class="hud"><span class="brand">Analyst Eye</span></div>
     <div class="panel"><p class="task">No puzzle for ${esc(nice(TODAY))} yet.</p>
     <p class="dim">${next ? `The first one unlocks ${esc(nice(next))} at midnight (US Central).` : "The next puzzle is on its way."}</p>
     ${archiveHTML()}</div>`);
}

/* Practice only: a 5-round set of one difficulty, pooled from past days (the daily puzzle is never affected). */
async function startTier(tier) {
  const past = avail.filter(d => d < TODAY), pool = []; let size = 768;
  for (const d of past) {
    try { const P = await loadPuzzle(d); size = P.size;
      P.rounds.forEach(r => { if (!r.s) r.s = decode(r.secret, d); if (r.tier === tier) pool.push(r); }); } catch (e) {}
  }
  for (let i = pool.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [pool[i], pool[j]] = [pool[j], pool[i]]; }
  const picked = pool.slice(0, 5).sort((a, b) => (a.dscore || 0) - (b.dscore || 0));
  if (!picked.length) return h(`<div class="hud"><span class="brand">Analyst Eye</span></div><div class="panel"><p class="task">No ${TIER_NAME[tier].toLowerCase()} rounds to practice yet.</p><p class="dim">Come back after a few daily puzzles.</p>${archiveHTML()}</div>`);
  G = { ds: TODAY, P: { number: "", size, rounds: picked }, practice: true, tier, i: 0, results: [] };
  intro();
}
function practiceLink(tier, ds) {
  const q = new URLSearchParams(location.search); q.delete("date"); q.delete("practice");
  if (tier === "mixed") q.set("date", ds); else q.set("practice", tier);
  return "?" + q.toString();
}
function tierPicker() {
  if (!G.practice || EMBED) return "";
  const lastPast = avail.filter(d => d < TODAY).pop();
  const cur = G.tier || "mixed", ds = G.tier ? lastPast : G.ds;
  return `<div class="seg" role="group" aria-label="Practice difficulty">${["mixed", "easy", "medium", "hard"].map(t =>
    `<a href="${esc(practiceLink(t, ds))}" target="_self" class="${t === cur ? "on" : ""}" ${t === cur ? 'aria-current="true"' : ""}>${t === "mixed" ? "Mixed" : TIER_NAME[t]}</a>`).join("")}</div>`;
}

async function start(ds, practice) {
  let P;
  try { P = await loadPuzzle(ds); } catch (e) { return h(`<div class="panel">Couldn't load the puzzle for ${esc(nice(ds))}. Try again later.</div>`); }
  P.rounds.forEach(r => { r.s = decode(r.secret, ds); });
  const saved = practice ? null : loadDay(ds, P.rounds.length);
  G = { ds, P, practice, i: 0, results: saved ? saved.results : [] };
  if (!practice && saved && saved.done) return end();
  if (G.results.length) { G.i = G.results.length; return round(); }
  intro();
}

/* ---------- header: title, round dots, score ---------- */
function hud() {
  const tot = G.results.reduce((a, r) => a + r.score, 0);
  const N = G.P.rounds.length;
  const dots = G.P.rounds.map((_, i) => {
    const r = G.results[i];
    return `<span class="${r ? cls(r.score) : i === G.i ? "cur" : ""}"></span>`;
  }).join("");
  return `<div class="hud"><span class="brand">Analyst Eye${G.practice ? ' <span class="tag practice">Practice</span>' : ""}</span>
    <span class="dots" aria-label="round ${Math.min(G.i + 1, N)} of ${N}">${dots}</span>
    <span class="hudr"><span class="pts"><b>${tot}</b> pts</span><button class="iconbtn" id="help" aria-label="How to play">?</button></span></div>`;
}
function bindHelp() { const b = document.getElementById("help"); if (b) b.onclick = () => howto(true); }

/* ---------- first-time how-to overlay ---------- */
function howto(force) {
  if (!force && store.get("ae:howto")) return;
  const m = document.createElement("div"); m.className = "modal"; m.id = "howto";
  m.innerHTML = `<div class="card" role="dialog" aria-label="How to play"><h2>How to play</h2>
    <ol><li>Read what to find, then tap the photo to drop a pin.</li>
    <li>Pinch or scroll to zoom, drag to look around.</li>
    <li>Hit <b>Lock in</b>. Closer and faster = more points.</li></ol>
    <button class="btn primary" id="gotit" style="width:100%">Got it</button></div>`;
  document.body.appendChild(m);
  const close = () => { store.set("ae:howto", 1); m.remove(); };
  m.querySelector("#gotit").onclick = close;
  m.addEventListener("click", e => { if (e.target === m) close(); });
}

/* ---------- the photo, with zoom/pan ---------- */
function scopeHTML(r, extra = "") {
  return `<div class="scope" id="scope"><div class="stage" id="stage"><img id="img" src="puzzles/${esc(r.image)}" alt="Aerial photo, round ${r.round}" draggable="false">
    <svg id="ov" viewBox="0 0 ${G.P.size} ${G.P.size}" preserveAspectRatio="none"></svg></div>
    <div class="scale" id="scale"><i></i><span></span></div>
    <div class="zoom"><button type="button" data-z="in" aria-label="Zoom in">+</button><button type="button" data-z="out" aria-label="Zoom out">−</button><button type="button" data-z="reset" aria-label="Reset zoom">⤢</button></div>
    <button type="button" class="info" id="info" aria-label="About this photo">i</button><div class="pop" id="pop" hidden></div>${extra}</div>`;
}
function infoHTML(r, revealed) {
  const s = r.s, d = s.naip && s.naip.acquired;
  const when = d ? new Date(d + "T12:00:00Z").toLocaleDateString("en-US", { timeZone: "UTC", month: "short", year: "numeric" }) : "";
  return `Photo: USDA NAIP${when ? ", " + esc(when) : ""}<br>Map data: © OpenStreetMap` +
    (revealed ? `<br>${s.name ? esc(s.name) + " · " : ""}<a href="${esc(s.osm)}" target="_blank" rel="noopener">View on map ↗</a>` : "");
}
function setupScope(r, onTap, getRevealed) {
  const scope = document.getElementById("scope"), stage = document.getElementById("stage");
  const scaleEl = document.getElementById("scale"), pop = document.getElementById("pop");
  const Z = { k: 1, tx: 0, ty: 0, onChange: null };
  const W = () => scope.clientWidth, H = () => scope.clientHeight;
  const clampT = () => { Z.tx = Math.min(0, Math.max(W() - W() * Z.k, Z.tx)); Z.ty = Math.min(0, Math.max(H() - H() * Z.k, Z.ty)); };
  let lastW = 0, lastH = 0;
  function apply() {
    const w = W(), hh = H();
    if (lastW && w && (w !== lastW || hh !== lastH)) { Z.tx *= w / lastW; Z.ty *= hh / lastH; }
    lastW = w; lastH = hh;
    clampT(); stage.style.transform = `translate(${Z.tx}px,${Z.ty}px) scale(${Z.k})`;
    scope.classList.toggle("zoomed", Z.k > 1.01);
    const pxPerM = W() / (G.P.size * r.gsd_m) * Z.k;
    const m = [5, 10, 20, 50, 100, 200].filter(v => v * pxPerM <= Math.max(60, W() * 0.22)).pop() || 5;
    scaleEl.querySelector("i").style.width = (m * pxPerM) + "px"; scaleEl.querySelector("span").textContent = m + " m";
    Z.onChange && Z.onChange(Z.k);
  }
  function zoomAt(sx, sy, nk, anim) {
    nk = Math.max(1, Math.min(4, nk));
    Z.tx = sx - (sx - Z.tx) * nk / Z.k; Z.ty = sy - (sy - Z.ty) * nk / Z.k; Z.k = nk;
    if (anim) { stage.classList.add("anim"); setTimeout(() => stage.classList.remove("anim"), 260); }
    apply();
  }
  Z.zoomAt = zoomAt;
  Z.reset = anim => { if (anim) { stage.classList.add("anim"); setTimeout(() => stage.classList.remove("anim"), 260); } Z.k = 1; Z.tx = Z.ty = 0; apply(); };
  scope.querySelectorAll(".zoom button").forEach(b => b.onclick = e => {
    e.stopPropagation(); const z = b.dataset.z;
    if (z === "reset") Z.reset(true); else zoomAt(W() / 2, H() / 2, Z.k * (z === "in" ? 1.6 : 1 / 1.6), true);
  });
  document.getElementById("info").onclick = e => { e.stopPropagation(); pop.innerHTML = infoHTML(r, getRevealed()); pop.hidden = !pop.hidden; };
  // stop control taps from starting a pan/tap gesture on the photo
  scope.querySelectorAll(".zoom,.info,.pop").forEach(el => el.addEventListener("pointerdown", e => e.stopPropagation()));

  const pts = new Map(); let g = null;
  const rel = e => { const b = scope.getBoundingClientRect(); return { x: e.clientX - b.left, y: e.clientY - b.top }; };
  scope.addEventListener("pointerdown", e => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    try { scope.setPointerCapture(e.pointerId); } catch (_) {}
    const p = rel(e); pts.set(e.pointerId, p);
    if (pts.size === 1) g = { multi: false, moved: false, x0: p.x, y0: p.y, tx0: Z.tx, ty0: Z.ty };
    else if (pts.size === 2 && g) {
      const [a, b] = [...pts.values()];
      Object.assign(g, { multi: true, d0: Math.hypot(a.x - b.x, a.y - b.y) || 1, k0: Z.k, mx0: (a.x + b.x) / 2, my0: (a.y + b.y) / 2, tx0: Z.tx, ty0: Z.ty });
    }
  });
  scope.addEventListener("pointermove", e => {
    if (!pts.has(e.pointerId) || !g) return;
    pts.set(e.pointerId, rel(e));
    if (pts.size >= 2) {
      const [a, b] = [...pts.values()], d = Math.hypot(a.x - b.x, a.y - b.y), mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      const nk = Math.max(1, Math.min(4, g.k0 * d / g.d0));
      const ix = (g.mx0 - g.tx0) / g.k0, iy = (g.my0 - g.ty0) / g.k0;   // photo point under the fingers at start
      Z.k = nk; Z.tx = mx - ix * nk; Z.ty = my - iy * nk; g.moved = true; apply();
    } else {
      const p = pts.get(e.pointerId), dx = p.x - g.x0, dy = p.y - g.y0;
      if (!g.moved && Math.hypot(dx, dy) > 8) g.moved = true;
      if (g.moved && Z.k > 1) { Z.tx = g.tx0 + dx; Z.ty = g.ty0 + dy; apply(); }
    }
  });
  const up = e => {
    if (!pts.has(e.pointerId)) return;
    const p = pts.get(e.pointerId); pts.delete(e.pointerId);
    if (pts.size === 1 && g) { const q = [...pts.values()][0]; Object.assign(g, { x0: q.x, y0: q.y, tx0: Z.tx, ty0: Z.ty, moved: true }); return; }
    if (pts.size === 0) {
      const tap = g && !g.multi && !g.moved && e.type === "pointerup"; g = null;
      if (tap) { pop.hidden = true; onTap([((p.x - Z.tx) / Z.k) / W() * G.P.size, ((p.y - Z.ty) / Z.k) / H() * G.P.size]); }
    }
  };
  scope.addEventListener("pointerup", up); scope.addEventListener("pointercancel", up);
  scope.addEventListener("wheel", e => { e.preventDefault(); const p = rel(e); zoomAt(p.x, p.y, Z.k * Math.exp(-e.deltaY * 0.0015)); }, { passive: false });
  apply();
  if (window.ResizeObserver) new ResizeObserver(() => { if (document.body.contains(scope) && (scope.clientWidth !== lastW || scope.clientHeight !== lastH)) apply(); }).observe(scope);
  if (window.AE_DEBUG) window.AE_DEBUG.zoom = Z;
  return Z;
}

function intro() {
  const r = G.P.rounds[0], N = G.P.rounds.length;
  const kicker = G.tier ? `Practice · ${TIER_NAME[G.tier]} rounds from past days` : `Puzzle #${esc(G.P.number || dayNum(G.ds))} · ${esc(nice(G.ds))}${G.practice ? " · practice" : ""}`;
  // today's lineup: difficulty only, never the targets
  const lineup = G.P.rounds.map(x => isTier(x.tier) ? `<li class="t-${x.tier}"><i></i>${TIER_SHORT[x.tier]}</li>` : "<li><i></i></li>").join("");
  let extras = "";
  if (!G.practice) {
    const st = loadStats(), hasPast = avail.some(d => d < TODAY);
    const stats = st.played > 0
      ? `<div class="istats"><div><b>${st.streak}</b><span>Streak</span></div><div><b>${st.best}</b><span>Best</span></div><div><b>${st.played}</b><span>Played</span></div></div>`
      : `<p class="istart">Start your streak today</p>`;
    extras = `<div class="imeta">${stats}<p class="inext"><span id="nextin">Next puzzle in ${untilMidnight()}</span>${EMBED ? ` <span>· <a href="${esc(SITE)}" target="_blank" rel="noopener">Full site ↗</a></span>` : hasPast ? ` <span>· <a href="${esc(practiceLink("easy"))}" target="_self">Practice</a></span>` : ""}</p></div>`;
  }
  h(`${hud()}<div class="play intro-play">
     ${scopeHTML(r, `<div class="cover"><button class="btn primary big-btn" id="go">▶ Play</button></div>`)}
     <div class="side intro">
       <div class="ihead">
         <div class="kicker">${kicker}</div>
         <h1 class="ititle">${N} Things to Spy from the Sky</h1>
         <p class="isub">${G.practice ? "Practice games don't change your stats." : "New puzzle every midnight"}</p>
       </div>
       ${G.tier ? "" : `<ol class="lineup" aria-label="Rounds by difficulty">${lineup}</ol>`}
       ${tierPicker()}
       ${extras}
       ${EMBED && G.practice ? `<a class="dim small" href="${esc(SITE)}" target="_blank" rel="noopener">Open full site ↗</a>` : ""}
     </div></div>`);
  app.classList.add("is-intro");
  bindHelp();
  const nx = document.getElementById("nextin");
  if (nx) { const iv = setInterval(() => { if (!document.body.contains(nx)) return clearInterval(iv); nx.textContent = "Next puzzle in " + untilMidnight(); }, 30000); }
  document.getElementById("go").onclick = () => { preload(); round(); };
  howto(false);
}
function preload() { G.P.rounds.forEach(r => { const i = new Image(); i.src = "puzzles/" + r.image; }); }

// u = photo units per screen pixel, so the pin stays the same on-screen size at any zoom
const unitPx = k => { const sc = document.getElementById("scope"); return G.P.size / ((sc ? sc.clientWidth : G.P.size) * k); };
function crosshair([x, y], col, k = 1, u0) {
  const u = u0 || unitPx(k), r = 10 * u, a = 20 * u, b = 6 * u;
  const d = `M${x - a} ${y}H${x - b}M${x + b} ${y}H${x + a}M${x} ${y - a}V${y - b}M${x} ${y + b}V${y + a}`;
  return `<g fill="none" stroke-linecap="round"><circle cx="${x}" cy="${y}" r="${r}" stroke="rgba(0,0,0,.6)" stroke-width="${4.5 * u}"/><path d="${d}" stroke="rgba(0,0,0,.6)" stroke-width="${4.5 * u}"/>` +
    `<circle cx="${x}" cy="${y}" r="${r}" stroke="${col}" stroke-width="${2.2 * u}"/><path d="${d}" stroke="${col}" stroke-width="${2.2 * u}"/><circle cx="${x}" cy="${y}" r="${1.6 * u}" fill="${col}"/></g>`;
}

function round() {
  const r = G.P.rounds[G.i], s = r.s;
  let click = null, hint = false, t0 = null, raf = 0, done = false, k = 1;
  h(`${hud()}<div class="play">${scopeHTML(r)}
     <div class="side">
       <div class="task">${r.tier ? `<span class="tier t-${esc(r.tier)}">${TIER_NAME[r.tier] || ""}</span>` : ""}${esc(r.task)}</div>
       ${r.caution ? `<p class="caution">${esc(r.caution)}</p>` : ""}
       <div class="timer"><i id="bar"></i></div>
       <div class="row"><button class="btn ghost" id="hint">💡 Hint <small>−${HINT_PEN}</small></button>
         <button class="btn primary grow" id="lock" disabled>Lock in</button></div>
       <div class="dim small" id="tip">Tap the photo to drop a pin. Pinch or scroll to zoom.</div>
     </div></div>`);
  bindHelp();
  const img = document.getElementById("img"), ov = document.getElementById("ov");
  const bar = document.getElementById("bar"), lock = document.getElementById("lock"), tip = document.getElementById("tip");
  const startClock = () => { if (t0 == null) { t0 = performance.now(); tick(); } };
  if (img.complete) startClock(); else { img.onload = startClock; img.onerror = startClock; }
  function tick() {
    if (done) return;
    const t = (performance.now() - t0) / 1000;
    bar.style.width = (Math.max(0, ROUND_S - t) / ROUND_S * 100) + "%";
    raf = requestAnimationFrame(tick);
  }
  function draw() {
    let svg = "";
    if (hint) svg += `<circle cx="${s.hint[0]}" cy="${s.hint[1]}" r="${s.hint[2]}" fill="rgba(255,176,46,.08)" stroke="#ffb02e" stroke-width="3" vector-effect="non-scaling-stroke" stroke-dasharray="10 8"/>`;
    if (click) svg += crosshair(click, "#fff", k);
    ov.innerHTML = svg;
  }
  const Z = setupScope(r, p => {
    if (done) return; startClock();
    click = p; lock.disabled = false; tip.textContent = "Tap again to move your pin, then Lock in."; draw();
  }, () => done);
  Z.onChange = kk => { k = kk; draw(); };
  document.getElementById("hint").onclick = (e) => { hint = true; e.currentTarget.disabled = true; draw(); };
  lock.onclick = () => {
    if (!click || done) return; done = true; cancelAnimationFrame(raf);
    const t = t0 == null ? ROUND_S : (performance.now() - t0) / 1000;
    const res = score(click, s, r.radius_px, t, hint); res.click = click.map(v => Math.round(v));
    G.results.push(res);
    if (!G.practice) store.set("ae:day:" + G.ds, { results: G.results, done: G.results.length >= G.P.rounds.length });
    if (!G.practice && G.results.length >= G.P.rounds.length) recordStats();
    reveal(res, Z);
  };
}

function decoySVG(s, res, u) {
  let svg = "";
  (s.decoys || []).forEach((dc, i) => {
    const g = dc.geom || [], hit = res && res.dk === i, w = (hit ? 3 : 2) * u, op = hit ? 1 : .75;
    if (g.length > 1) {
      const pts = g.map(p => p.join(",")).join(" ");
      svg += dc.gtype === "polygon" ? `<polygon points="${pts}" fill="rgba(255,92,92,${hit ? .22 : .1})" stroke="#ff5c5c" stroke-opacity="${op}" stroke-width="${w}" stroke-dasharray="${6 * u} ${4 * u}"/>`
        : `<polyline points="${pts}" fill="none" stroke="#ff5c5c" stroke-opacity="${op * .6}" stroke-width="${Math.max(3, (dc.halfwidth_px || 2) * 2)}" stroke-dasharray="${8 * u} ${6 * u}"/>`;
    } else svg += `<circle cx="${dc.answer[0]}" cy="${dc.answer[1]}" r="${Math.max(9 * u, dc.r || 8)}" fill="none" stroke="#ff5c5c" stroke-opacity="${op}" stroke-width="${w}" stroke-dasharray="${5 * u} ${4 * u}"/>`;
    const [x, y] = dc.answer, a = 5 * u;
    svg += `<path d="M${x - a} ${y - a}L${x + a} ${y + a}M${x + a} ${y - a}L${x - a} ${y + a}" stroke="#ff5c5c" stroke-width="${2.2 * u}" stroke-linecap="round"/>`;
  });
  return svg;
}
function answerSVG(r, res, k, u0) {
  const s = r.s, u = u0 || unitPx(k), T = targets(s); let svg = decoySVG(s, res, u);
  const near = T[res && res.ti != null ? res.ti : (res ? nearest(res.click, s).i : 0)] || s;
  T.forEach(t => {
    const g = t.geom || [];
    if (g.length > 1) {
      const pts = g.map(p => p.join(",")).join(" ");
      svg += t.gtype === "polygon" ? `<polygon points="${pts}" fill="rgba(90,209,230,.18)" stroke="#5ad1e6" stroke-width="3" vector-effect="non-scaling-stroke"/>`
        : `<polyline points="${pts}" fill="none" stroke="#5ad1e6" stroke-width="${Math.max(4, (s.halfwidth_px || 2) * 2)}" stroke-opacity=".55"/>`;
    }
    if (t !== near) svg += `<circle cx="${t.answer[0]}" cy="${t.answer[1]}" r="${Math.max(9 * u, r.radius_px * 0.8)}" fill="none" stroke="#ffb02e" stroke-opacity=".7" stroke-width="${2 * u}" stroke-dasharray="${5 * u} ${4 * u}"/>`;
  });
  if (res) svg += `<line x1="${res.click[0]}" y1="${res.click[1]}" x2="${near.answer[0]}" y2="${near.answer[1]}" stroke="#fff" stroke-width="2" vector-effect="non-scaling-stroke" stroke-dasharray="6 6"/>`;
  svg += `<circle cx="${near.answer[0]}" cy="${near.answer[1]}" r="${Math.max(12 * u, r.radius_px)}" fill="none" stroke="#ffb02e" stroke-width="${3 * u}"/><circle cx="${near.answer[0]}" cy="${near.answer[1]}" r="${3 * u}" fill="#ffb02e"/>`;
  if (res) svg += crosshair(res.click, "#fff", k, u0);
  return svg;
}

function reveal(res, Z) {
  const r = G.P.rounds[G.i], s = r.s, ov = document.getElementById("ov");
  document.getElementById("scope").classList.add("locked");
  Z.onChange = kk => { ov.innerHTML = answerSVG(r, res, kk); };
  Z.reset(true);
  document.querySelector(".hud").outerHTML = hud(); bindHelp();
  const meters = Math.round(res.d * r.gsd_m), last = G.i >= G.P.rounds.length - 1;
  const side = document.querySelector(".side");
  const dc = res.dk >= 0 && (s.decoys || [])[res.dk];
  side.innerHTML = `<div class="verdict ${dc ? "decoy" : cls(res.score)}"><span class="word">${dc ? "Decoy!" : verdict(res.score)}</span> <span class="big">${res.score}</span></div>
    ${dc ? `<p class="note">${esc(dc.clue)}</p>` : `<p class="note">${esc(s.note)}</p>`}${(s.alts || []).length ? `<p class="dim small">There were ${targets(s).length} in this photo. Any of them counts.</p>` : ""}
    ${(s.decoys || []).length ? `<p class="dim small"><span class="dkey"></span>Decoys</p>` : ""}
    <details class="more"><summary>Details</summary><div>${res.d === 0 ? "Right on it" : `${meters} m away`} · closeness ${res.acc}/80 · speed +${res.speed}${res.hint ? ` · hint −${HINT_PEN}` : ""}</div></details>
    <div class="row"><button class="btn primary grow" id="next">${last ? "See results ▶" : "Next ▶"}</button></div>`;
  document.getElementById("next").onclick = () => { G.i++; last ? end() : round(); };
  if (!EMBED && !document.body.classList.contains("split")) side.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function recordStats() {
  const st = loadStats();
  if (st.hist[G.ds] != null) return;
  const total = G.results.reduce((a, r) => a + r.score, 0);
  st.hist[G.ds] = total; st.played++;
  st.streak = st.last === addDays(G.ds, -1) ? st.streak + 1 : 1;
  st.maxStreak = Math.max(st.maxStreak, st.streak); st.last = G.ds;
  if (total > st.best) { st.best = total; st.bestDate = G.ds; }
  store.set("ae:stats", st);
}

function shareText() {
  const total = G.results.reduce((a, r) => a + r.score, 0), hints = G.results.filter(r => r.hint).length;
  const st = loadStats();
  return [G.tier ? `Analyst Eye practice (${TIER_NAME[G.tier]}) 🛰️ ${total}/${G.P.rounds.length * 100}` : `Analyst Eye #${G.P.number || dayNum(G.ds)}${G.practice ? " (practice)" : ""} 🛰️ ${total}/500`,
    G.results.map(r => sq(r.score)).join(""),
    [hints ? `💡${hints}` : "", (!G.practice && st && st.streak > 1) ? `🔥${st.streak}` : ""].filter(Boolean).join(" "),
    SITE].filter(Boolean).join("\n");
}

function archiveHTML() {
  const past = avail.filter(d => d < TODAY).slice(-30).reverse();
  if (!past.length) return "";
  if (EMBED) return `<a class="btn ghost" href="${esc(SITE)}" target="_blank" rel="noopener">Past puzzles ↗</a>`;
  const q = t => { const u = new URLSearchParams(location.search); u.delete("date"); u.set("practice", t); return "?" + u.toString(); };
  return `<h3 class="kicker" style="margin:14px 0 4px">Practice by difficulty</h3>
    <div class="seg">${["easy", "medium", "hard"].map(t => `<a href="${esc(q(t))}" target="_self">${TIER_NAME[t]}</a>`).join("")}</div>
    <h3 class="kicker" style="margin:14px 0 4px">Play past days</h3>
    <ul class="list">${past.map(d => { const sc = loadStats().hist[d];
      return `<li><a href="?date=${d}" target="_self">#${dayNum(d)} · ${esc(nice(d))}${sc != null ? ` · ${sc}` : ""}</a></li>`; }).join("")}</ul>`;
}

function end() {
  G.i = G.P.rounds.length;
  const N = G.P.rounds.length, total = G.results.reduce((a, r) => a + r.score, 0), text = shareText();
  const st = loadStats();
  const intent = "https://x.com/intent/tweet?text=" + encodeURIComponent(text);
  const title = G.tier ? `Practice · ${TIER_NAME[G.tier]}` : `Analyst Eye #${G.P.number || dayNum(G.ds)} · ${nice(G.ds)}${G.practice ? " · practice" : ""}`;
  const rows = G.P.rounds.map((r, i) => { const x = G.results[i] || { score: 0 };
    return `<li class="rrow"><button type="button" class="rbtn" aria-expanded="false" data-i="${i}">
      <span class="sqr ${cls(x.score)}" aria-hidden="true"></span><span class="rname">${esc(r.label)}</span>
      <span class="rtier t-${esc(r.tier || "")}">${TIER_SHORT[r.tier] || ""}</span><span class="rpts">${x.score}</span><span class="chev" aria-hidden="true">›</span></button>
      <div class="rdetail" hidden></div></li>`; }).join("");
  const stats = G.practice ? `Practice doesn't count toward stats · <a href="?" target="_self">Back to today</a>`
    : `Played ${st.played} · Streak ${st.streak} · Best ${st.best} · Next puzzle in ${untilMidnight()}`;
  h(`<div class="hud"><span class="brand">Analyst Eye</span><button class="iconbtn" id="help" aria-label="How to play">?</button></div>
    <section class="results" aria-label="Results">
      <div class="rhead"><div class="kicker">${esc(title)}</div><div class="total"><b>${total}</b><span>/${N * 100}</span></div></div>
      <ol class="rtable">${rows}</ol>
      <div class="row"><a class="btn x grow" id="sharex" href="${esc(intent)}" target="_blank" rel="noopener">𝕏 Share on X</a>
        <button type="button" class="btn ghost iconcopy" id="copy" aria-label="Copy result" title="Copy result"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/></svg></button></div>
      <p class="quiet" id="stats">${stats}</p>
      ${EMBED ? `<p class="quiet"><a href="${esc(SITE)}" target="_blank" rel="noopener">Past puzzles ↗</a></p>` : ""}
    </section>
    ${EMBED ? "" : `<div class="results more">${archiveHTML()}</div>`}`);
  bindHelp();
  document.getElementById("copy").onclick = () => copy(text);
  app.querySelectorAll(".rbtn").forEach(btn => btn.onclick = () => {
    const open = btn.getAttribute("aria-expanded") === "true";
    app.querySelectorAll(".rbtn").forEach(b => { b.setAttribute("aria-expanded", "false"); b.nextElementSibling.hidden = true; });
    if (open) return;
    const i = +btn.dataset.i, r = G.P.rounds[i], res = G.results[i], det = btn.nextElementSibling;
    det.innerHTML = `<div class="rthumb"><img src="puzzles/${esc(r.image)}" alt="Answer for round ${i + 1}"><svg viewBox="0 0 ${G.P.size} ${G.P.size}" preserveAspectRatio="none"></svg></div>
      <p>${res && res.dk >= 0 && (r.s.decoys || [])[res.dk] ? esc(r.s.decoys[res.dk].clue) : esc(r.s.note)}${(r.s.alts || []).length ? ` <span class="dim">(${targets(r.s).length} in the photo; any counted.)</span>` : ""}</p>`;
    det.hidden = false; btn.setAttribute("aria-expanded", "true");
    const th = det.querySelector(".rthumb");
    det.querySelector("svg").innerHTML = answerSVG(r, res, 1, G.P.size / (th.clientWidth || 150));
  });
}

function copy(text) {
  const ok = () => toast("Copied!");
  const fallback = () => { const ta = document.createElement("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select(); try { document.execCommand("copy") ? ok() : toast("Select the text to copy"); } catch (e) { toast("Select the text to copy"); } ta.remove(); };
  try { navigator.clipboard ? navigator.clipboard.writeText(text).then(ok, fallback) : fallback(); } catch (e) { fallback(); }
}

window.AE_DEBUG = { score, distance, decode, get state() { return G; } };
init();
})();
