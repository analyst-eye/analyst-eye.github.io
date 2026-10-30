/* Analyst Eye: Hidden. Weekly bonus round (one photo, one tap, then the LiDAR reveal). Static, framework-free, works sandboxed. */
(() => {
"use strict";
const C = window.AE_CONFIG || {}, IDX = window.AE_HIDDEN_INDEX || { dates: [] };
const app = document.getElementById("app");
const qs = new URLSearchParams(location.search);
const SITE = C.SITE_URL || location.href.replace(/[^/]*$/, "");
const LOCAL = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname) || location.protocol === "file:";
const isDay = v => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v);
const fmt = new Intl.DateTimeFormat("en-CA", { timeZone: C.TIMEZONE || "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit" });
const REAL_TODAY = fmt.format(new Date()), QT = qs.get("today");
const TODAY = (isDay(QT) && (LOCAL || QT <= REAL_TODAY)) ? QT : REAL_TODAY;   // like the daily game: ?today= can only go back in time on the public site
const dates = (IDX.dates || []).filter(d => isDay(d) && d <= TODAY).sort();
const nice = ds => new Date(ds + "T12:00:00Z").toLocaleDateString("en-US", { timeZone: "UTC", month: "short", day: "numeric", year: "numeric" });
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const mem = {};
const store = {
  get(k) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : null; } catch (e) { return k in mem ? mem[k] : null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { mem[k] = v; } }
};
const num = (v, lo, hi, d = 0) => (typeof v === "number" && isFinite(v)) ? Math.min(hi, Math.max(lo, v)) : d;
function loadSaved(ds) {   // saved data is user-editable: validate
  const v = store.get("ae:hidden:" + ds);
  if (!v || typeof v !== "object" || !Array.isArray(v.click) || v.click.length !== 2) return null;
  return { click: v.click.map(x => num(x, -1e4, 1e4)), score: Math.round(num(v.score, 0, 100)), d: num(v.d, 0, 1e5) };
}
function decode(secret, ds) {
  const raw = atob(secret), key = new TextEncoder().encode("analyst-eye:hidden:" + ds), b = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) b[i] = raw.charCodeAt(i) ^ key[i % key.length];
  return JSON.parse(new TextDecoder().decode(b));
}
function loadRound(ds) {
  return new Promise((res, rej) => {
    const have = window.AE_HIDDEN && window.AE_HIDDEN[ds]; if (have) return res(have);
    const s = document.createElement("script"); s.src = `hidden/${ds}.js`;
    s.onload = () => (window.AE_HIDDEN && window.AE_HIDDEN[ds]) ? res(window.AE_HIDDEN[ds]) : rej(new Error("empty"));
    s.onerror = () => rej(new Error("missing")); document.head.appendChild(s);
  });
}

/* ---------- scoring: 100 points, no clock. Full marks anywhere on the feature (or within radius_px of it), fading to 0 at six radii ---------- */
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
function shapeDist(p, a) {
  const g = a.geom || [];
  if (a.type === "polygon") { if (g.length > 2 && inPoly(p, g)) return 0; }
  let m = Infinity; const n = a.type === "polygon" ? g.length : g.length - 1;
  for (let i = 0; i < n; i++) m = Math.min(m, segDist(p, g[i], g[(i + 1) % g.length]));
  return a.type === "polygon" ? m : Math.max(0, m - (a.halfwidth_px || 0));
}
function nearest(p, answers) { let b = { d: Infinity, i: 0 }; answers.forEach((a, i) => { const d = shapeDist(p, a); if (d < b.d) b = { d, i }; }); return b; }
function score(p, answers, R) {
  const nb = nearest(p, answers), acc = nb.d <= R ? 1 : Math.max(0, 1 - (nb.d - R) / (5 * R));
  return { d: nb.d, i: nb.i, score: Math.round(acc * 100) };
}
const sq = s => s >= 80 ? "🟦" : s >= 40 ? "🟧" : "⬛";
const cls = s => s >= 80 ? "good" : s >= 40 ? "ok" : "miss";
const verdict = s => s >= 90 ? "Found it!" : s >= 70 ? "Nice!" : s >= 40 ? "Close!" : s > 0 ? "Not quite" : "Missed it";
const centroid = a => { const g = a.geom, n = a.type === "polygon" ? g.length : 0; if (!n) return g[Math.floor(g.length / 2)]; return [g.reduce((s, p) => s + p[0], 0) / n, g.reduce((s, p) => s + p[1], 0) / n]; };

/* ---------- screens ---------- */
const brand = (home) => `<div class="hud"><span class="hudl">${home ? `<a class="brand" href="./" style="text-decoration:none">Analyst Eye</a>` : `<span class="brand">Analyst Eye</span>`}<span class="hbonus">Hidden · weekly bonus</span></span></div>`;
const nrOf = ds => dates.indexOf(ds) + 1;
function pickDate() {
  const req = qs.get("date");
  if (isDay(req) && dates.includes(req)) return req;
  return dates[dates.length - 1] || null;
}
async function init() {
  const ds = pickDate();
  if (!ds) {
    const next = (IDX.dates || []).filter(d => d > TODAY).sort()[0];
    const nth = (IDX.dates || []).filter(isDay).sort().indexOf(next) + 1;
    app.innerHTML = `${brand(true)}<div class="panel"><p class="task">No hidden round yet.</p><p class="dim">${next ? `Hidden #${nth} unlocks ${esc(nice(next))} at midnight (US Central). One photo, one tap, then the LiDAR reveal.` : "The first one is on its way."}</p></div>`;
    return;
  }
  let P;
  try { P = await loadRound(ds); } catch (e) { app.innerHTML = `${brand(true)}<div class="panel">Couldn't load this round. Try again later.</div>`; return; }
  let S; try { S = decode(P.secret, ds); } catch (e) { app.innerHTML = `${brand(true)}<div class="panel">Couldn't read this round.</div>`; return; }
  play(ds, P, S);
}

function play(ds, P, S) {
  const saved = loadSaved(ds), size = P.size, R = S.radius_px, answers = S.answers;
  let click = null, done = false;
  const past = dates.filter(d => d !== ds).reverse().slice(0, 12);
  app.className = "app";
  app.innerHTML = `${brand(true)}
    <div class="hprompt"><span class="lbl">Round ${nrOf(ds)} · ${esc(nice(ds))}</span><span id="prompt">${esc(P.prompt)}</span></div>
    <div class="hscope" id="hs"><img id="hp" src="hidden/${esc(P.photo)}" alt="Aerial photo of a forested area" draggable="false">
      <img class="lid" id="hl" alt="LiDAR hillshade of the same area" draggable="false">
      <div class="divider"></div>
      <svg id="hov" viewBox="0 0 ${size} ${size}" preserveAspectRatio="none"></svg>
      <div class="scale"><i style="width:${(100 / P.gsd_m) / size * 100}%;min-width:0"></i><span>100 m</span></div></div>
    <div class="hcmp" id="cmp"><span>photo</span><input type="range" min="0" max="100" value="100" id="slider" aria-label="Compare photo and LiDAR"><span>LiDAR</span></div>
    <div id="side"><div class="row" style="margin-top:10px"><button class="btn primary grow" id="lock" disabled>Lock in</button></div>
      <div class="dim small" id="tip" style="margin-top:6px">Tap the photo to drop a pin, then Lock in. No clock.</div></div>`;
  const hs = document.getElementById("hs"), hov = document.getElementById("hov"), side = document.getElementById("side");
  const lock = document.getElementById("lock"), tip = document.getElementById("tip"), slider = document.getElementById("slider"), cmp = document.getElementById("cmp");
  const u = () => size / (hs.clientWidth || size);
  function pin([x, y], col) {
    const k = u(), r = 10 * k, a = 20 * k, b = 6 * k;
    const d = `M${x - a} ${y}H${x - b}M${x + b} ${y}H${x + a}M${x} ${y - a}V${y - b}M${x} ${y + b}V${y + a}`;
    return `<g fill="none" stroke-linecap="round"><circle cx="${x}" cy="${y}" r="${r}" stroke="rgba(0,0,0,.6)" stroke-width="${4.5 * k}"/><path d="${d}" stroke="rgba(0,0,0,.6)" stroke-width="${4.5 * k}"/><circle cx="${x}" cy="${y}" r="${r}" stroke="${col}" stroke-width="${2.2 * k}"/><path d="${d}" stroke="${col}" stroke-width="${2.2 * k}"/></g>`;
  }
  function answerSVG(res) {
    let s = "";
    answers.forEach(a => {
      const pts = a.geom.map(p => p.join(",")).join(" ");
      s += a.type === "polygon" ? `<polygon points="${pts}" fill="rgba(90,209,230,.2)" stroke="#5ad1e6" stroke-width="3" vector-effect="non-scaling-stroke"/>`
        : `<polyline points="${pts}" fill="none" stroke="#5ad1e6" stroke-width="${Math.max(4, (a.halfwidth_px || 2) * 2)}" stroke-opacity=".5" stroke-linejoin="round" stroke-linecap="round"/>`;
      const c = centroid(a); s += `<circle cx="${c[0]}" cy="${c[1]}" r="${Math.max(12 * u(), R)}" fill="none" stroke="#ffb02e" stroke-width="${2.5 * u()}"/><circle cx="${c[0]}" cy="${c[1]}" r="${3 * u()}" fill="#ffb02e"/>`;
    });
    const c = centroid(answers[res.i]);
    s += `<line x1="${res.click[0]}" y1="${res.click[1]}" x2="${c[0]}" y2="${c[1]}" stroke="#fff" stroke-width="2" vector-effect="non-scaling-stroke" stroke-dasharray="6 6"/>`;
    return s;
  }
  function draw() { hov.innerHTML = click ? pin(click, "#fff") : ""; }
  function setP(p) { hs.style.setProperty("--p", String(p)); slider.value = String(Math.round(Math.min(100, p / 1.06))); }
  function finish(res, animate) {
    done = true; hs.classList.add("locked");
    const lid = document.getElementById("hl"); if (!lid.getAttribute("src")) lid.src = `hidden/${P.lidar}`;
    const show = () => {
      hov.innerHTML = `<g class="ans">${answerSVG(res)}</g>` + pin(res.click, "#fff");
      requestAnimationFrame(() => hs.classList.add("shown")); cmp.classList.add("on");
    };
    hs.classList.add("revealed");
    const total = 106;   // gradient edge is 6 percent wide: sweep past the end so the photo is fully covered
    if (!animate) { setP(total); hs.classList.add("shown"); show(); hs.classList.add("shown"); }
    else {
      const t0 = performance.now(), dur = 1400, ease = x => x * x * (3 - 2 * x);
      const step = now => { const t = Math.min(1, (now - t0) / dur); setP(ease(t) * total); if (t < 1) requestAnimationFrame(step); else show(); };
      setP(0); requestAnimationFrame(step);
    }
    document.getElementById("prompt").textContent = "There it was: " + S.reveal.charAt(0).toLowerCase() + S.reveal.slice(1) + ".";
    const text = shareText(ds, S, res), link = "https://x.com/intent/tweet?text=" + encodeURIComponent(text);
    const meters = Math.round(res.d * P.gsd_m);
    side.innerHTML = `<div class="hverdict ${cls(res.score)}"><span class="word">${verdict(res.score)}</span> <span class="big">${res.score}</span><span class="of">/100</span></div>
      <p class="note">${esc(S.note)}</p>
      <details class="more"><summary>Details</summary><div>${res.d === 0 ? "Right on it" : `${meters} m from the feature`} · full marks within ${Math.round(R * P.gsd_m)} m of it · fades to 0 at ${Math.round(6 * R * P.gsd_m)} m${(answers.length > 1) ? ` · ${answers.length} spots count` : ""}</div></details>
      <div class="row" style="margin-top:10px"><a class="btn x grow" id="sharex" href="${esc(link)}" target="_blank" rel="noopener">𝕏 Share on X</a>
        <button type="button" class="btn ghost" id="copy" aria-label="Copy result">Copy</button></div>
      <p class="quiet dim small" style="margin-top:8px">Drag the slider to compare. A new hidden round every Sunday (US Central). <a href="./">Daily game</a></p>
      ${past.length ? `<h3 class="kicker" style="margin:14px 0 4px">Earlier rounds</h3><ul class="list">${past.map(d => { const sv = loadSaved(d); return `<li><a href="?date=${d}" target="_self">#${nrOf(d)} · ${esc(nice(d))}${sv ? ` · ${sv.score}` : ""}</a></li>`; }).join("")}</ul>` : ""}`;
    document.getElementById("copy").onclick = () => copy(text);
  }
  slider.addEventListener("input", () => { if (done) setP(+slider.value * 1.06); });
  const rect = () => hs.getBoundingClientRect();
  let down = null;
  hs.addEventListener("pointerdown", e => { if (done || (e.pointerType === "mouse" && e.button !== 0)) return; down = { x: e.clientX, y: e.clientY }; });
  hs.addEventListener("pointerup", e => {
    if (done || !down) return; const mv = Math.hypot(e.clientX - down.x, e.clientY - down.y); down = null; if (mv > 10) return;
    const b = rect(); click = [(e.clientX - b.left) / b.width * size, (e.clientY - b.top) / b.height * size];
    if (!document.getElementById("hl").getAttribute("src")) document.getElementById("hl").src = `hidden/${P.lidar}`;   // preload only; it stays invisible until the reveal
    lock.disabled = false; tip.textContent = "Tap again to move your pin, then Lock in."; draw();
  });
  lock.onclick = () => {
    if (!click || done) return;
    const r = score(click, answers, R), res = { click: click.map(v => Math.round(v)), score: r.score, d: r.d, i: r.i };
    store.set("ae:hidden:" + ds, { click: res.click, score: res.score, d: Math.round(r.d) });
    finish(res, true);
  };
  if (saved) { const r = score(saved.click, answers, R); finish({ click: saved.click, score: r.score, d: r.d, i: r.i }, false); }
  if (window.AE_DEBUG) window.AE_DEBUG.state = { ds, S, P };
}

function shareText(ds, S, res) {
  const n = nrOf(ds), noun = S.noun || "it";
  const line = res.score >= 80 ? `Found the ${noun} under the trees` : res.score >= 40 ? `Close to the ${noun} under the trees` : `Missed the ${noun} under the trees`;
  return [`Analyst Eye · Hidden #${n} 🌲🛰️ ${res.score}/100`, `${sq(res.score)} ${line}`, "Can you find what's under the forest?", SITE + "hidden.html"].join("\n");
}
function copy(text) {
  const ok = () => { const t = document.createElement("div"); t.className = "toast"; t.textContent = "Copied!"; document.body.appendChild(t); setTimeout(() => t.remove(), 1600); };
  const fb = () => { const ta = document.createElement("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0"; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); ok(); } catch (e) {} ta.remove(); };
  try { navigator.clipboard ? navigator.clipboard.writeText(text).then(ok, fb) : fb(); } catch (e) { fb(); }
}
window.AE_DEBUG = { score, nearest, decode, shareText };
init();
})();
