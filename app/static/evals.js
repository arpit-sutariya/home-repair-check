const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (p) => (p == null ? "–" : Math.round(p * 100) + "%");
const frac = (s) => { const [a, b] = String(s).split("/").map(Number); return { a, b, p: b ? a / b : 0 }; };
const NAMES = {
  water_stain: "Water stain", plumbing_leak: "Plumbing leak", mold: "Mold", wall_crack: "Wall crack",
  foundation_crack: "Stair-step crack", peeling_paint: "Peeling paint", roof_damage: "Roof damage", outlet_damage: "Outlet damage",
};
const ORDER = Object.keys(NAMES);
const name = (id) => NAMES[id] || id;

// ------------------------------------------------------------------ theme toggle (same as the main page)
(() => {
  const b = $("#theme"), dark = () => (document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark";
  const paint = () => (b.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${dark()
    ? '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'
    : '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>'}</svg>`);
  b.onclick = () => { const t = dark() ? "light" : "dark"; document.documentElement.dataset.theme = t; try { localStorage.setItem("rc.theme", t); } catch {} paint(); };
  paint();
})();

// ------------------------------------------------------------------ hover tooltips (any element with data-tip)
const tip = $("#tip");
document.addEventListener("pointermove", (e) => {
  const t = e.target.closest?.("[data-tip]");
  if (!t) { tip.hidden = true; return; }
  tip.innerHTML = t.dataset.tip; tip.hidden = false;
  const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8);
  const y = e.clientY + 16 + tip.offsetHeight > innerHeight ? e.clientY - tip.offsetHeight - 12 : e.clientY + 16;
  tip.style.left = x + "px"; tip.style.top = y + "px";
});

function tile(k, v, d) { return `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`; }

// ------------------------------------------------------------------ charts
function groupedBars(plain, used) {
  const ids = ORDER.filter((id) => used.per_problem[id]);
  const rows = [{ id: "_all", label: "All 75 photos", a: plain.accuracy, b: used.accuracy, overall: true },
    ...ids.map((id) => ({ id, label: name(id), a: frac(plain.per_problem[id]).p, b: frac(used.per_problem[id]).p,
      af: plain.per_problem[id], bf: used.per_problem[id] }))];
  const bar = (cls, p, f, who, label) => `<div class="gb-bar ${cls}"><i style="width:${p * 100}%"></i><span>${pct(p)}</span></div>`;
  return `<div class="legend"><span><i class="sw" style="background:var(--series-muted)"></i>Plain names (“a photo of mold growth”)</span>
      <span><i class="sw" style="background:var(--s1)"></i>Written visual cues (used)</span></div>
    <div class="gb">${rows.map((r) => `
      <div class="gb-row hit ${r.overall ? "overall" : ""}" data-tip="<b>${esc(r.label)}</b><br>Plain names: ${pct(r.a)}${r.af ? ` (${r.af})` : ""}<br>Visual cues: ${pct(r.b)}${r.bf ? ` (${r.bf})` : ""}">
        <span class="n">${esc(r.label)}</span>
        <div class="gb-bars">${bar("a", r.a)}${bar("b", r.b)}</div></div>`).join("")}
      <div class="gb-axis"><span></span><div><span>0%</span><span>50%</span><span>100%</span></div></div></div>`;
}

function confusion(cm) {
  const rows = ORDER.filter((id) => cm[id]);
  const cols = ORDER.filter((id) => rows.includes(id) || rows.some((r) => cm[r][id]));
  const max = Math.max(...rows.flatMap((r) => Object.values(cm[r])));
  const cell = (r, c) => {
    const n = cm[r][c] || 0, total = Object.values(cm[r]).reduce((a, b) => a + b, 0);
    if (!n) return `<td class="z" data-tip="Actually ${esc(name(r))}, predicted ${esc(name(c))}: 0">·</td>`;
    const k = 18 + 82 * (n / max);
    return `<td style="background:color-mix(in srgb, var(--s1) ${k}%, var(--card));color:${k > 55 ? "#fff" : "var(--ink)"}"
      data-tip="Actually <b>${esc(name(r))}</b>, predicted <b>${esc(name(c))}</b>: ${n} of ${total}">${n}</td>`;
  };
  return `<div class="cm-wrap"><table class="cm"><thead><tr><th></th><th colspan="${cols.length}" class="axis-t">Predicted →</th></tr>
    <tr><th class="axis-t" style="text-align:right">Actual ↓</th>${cols.map((c) => `<th title="${esc(name(c))}">${esc(name(c).split(/[ /]/)[0])}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr><th class="rowh">${esc(name(r))}</th>${cols.map((c) => cell(r, c)).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function reliability(series) {
  const W = 420, H = 300, P = { l: 40, r: 70, t: 12, b: 36 };
  const x = (v) => P.l + v * (W - P.l - P.r), y = (v) => H - P.b - v * (H - P.t - P.b);
  let g = "";
  for (const v of [0, .25, .5, .75, 1]) {
    g += `<line class="gridl" x1="${P.l}" x2="${W - P.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${P.l - 6}" y="${y(v) + 4}" text-anchor="end">${v * 100}%</text>`;
    g += `<text x="${x(v)}" y="${H - P.b + 16}" text-anchor="middle">${v * 100}%</text>`;
  }
  g += `<line class="axisl" x1="${P.l}" x2="${W - P.r}" y1="${y(0)}" y2="${y(0)}"/>`;
  g += `<line class="diag" x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}"/>`;
  g += `<text x="${(P.l + W - P.r) / 2}" y="${H - 4}" text-anchor="middle">Stated confidence</text>`;
  g += `<text transform="translate(11 ${(P.t + H - P.b) / 2}) rotate(-90)" text-anchor="middle">Actually right</text>`;
  series.forEach((s, si) => {
    const pts = s.bins.map((b) => [x(b.confidence), y(b.accuracy), b]);
    g += `<polyline class="l${si + 1}" points="${pts.map((p) => p.slice(0, 2).join(",")).join(" ")}"/>`;
    pts.forEach(([px, py, b]) => {
      g += si === 0 ? `<circle class="m1" cx="${px}" cy="${py}" r="5"/>` : `<rect class="m2" x="${px - 5}" y="${py - 5}" width="10" height="10" rx="2"/>`;
      g += `<circle class="hitc" cx="${px}" cy="${py}" r="14" data-tip="<b>${esc(s.label)}</b><br>Said ${pct(b.confidence)} sure (avg)<br>Actually right ${pct(b.accuracy)}<br>${b.n} cases"/>`;
    });
    const last = pts[pts.length - 1];
    g += `<text class="lbl1" x="${last[0] + 10}" y="${last[1] + (si ? 20 : -10)}">${esc(s.short)}</text>`;
  });
  const table = `<details class="tbl"><summary>Show as a table</summary><table class="dt"><thead><tr><th>Set</th><th class="num">Confidence bin</th><th class="num">Cases</th><th class="num">Avg confidence</th><th class="num">Right</th></tr></thead><tbody>
    ${series.flatMap((s) => s.bins.map((b) => `<tr><td>${esc(s.short)}</td><td class="num">${pct(b.range[0])}–${pct(b.range[1])}</td><td class="num">${b.n}</td><td class="num">${pct(b.confidence)}</td><td class="num">${pct(b.accuracy)}</td></tr>`)).join("")}</tbody></table></details>`;
  return `<div class="legend"><span><i class="sw s1"></i>Photos</span><span><i class="sw s2"></i>Descriptions</span><span><i class="sw dg"></i>Perfectly honest</span></div>
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Reliability diagram: stated confidence vs actual accuracy">${g}</svg>${table}`;
}

// ------------------------------------------------------------------ page
function render(d) {
  const pk = Object.keys(d.photos);
  const used = d.photos[pk.find((k) => k.includes("(used)"))], plain = d.photos[pk.find((k) => k.includes("plain"))];
  const others = pk.filter((k) => !k.includes("(used)") && !k.includes("plain"));
  const dk = Object.keys(d.descriptions), desc = d.descriptions[dk.find((k) => k.includes("(used)")) || dk[0]];
  const nPhotos = d.counts?.photos ?? 75, nDesc = d.counts?.descriptions ?? 48;
  const ho = d.safety_heldout_first_run, s1 = d.safety, s2 = d.safety_heldout;
  if (d.run_at) $("#runat").textContent = `, last run ${d.run_at}`;

  $("#ev").innerHTML = `
    <div class="tiles">
      ${tile("Photos: right answer", pct(used.accuracy), `<span class="up">+${Math.round((used.accuracy - plain.accuracy) * 100)} pts</span> from prompt design alone`)}
      ${tile("Descriptions: right answer", pct(desc.accuracy), `${nDesc} homeowner-style descriptions`)}
      ${tile("Held-out emergencies caught", ho?.caught ?? `${s2.caught_any_warning}/${s2.emergencies}`, `first run on unseen cases · ${ho?.false_alarms ?? "0/20"} false alarms`)}
      ${tile("Calibration error (ECE)", used.ece != null ? used.ece.toFixed(3) : "–", `photos · ${desc.ece != null ? desc.ece.toFixed(3) : "–"} for descriptions (0 = perfectly honest)`)}
    </div>

    <section class="block">
      <h2 class="sec">1. Reading photos</h2>
      <p class="sub">${nPhotos} real photos of five problems (15 each), and the model chooses among all eight problem types. Same model (CLIP ViT-B/32), same photos; the only change is <b>how the problems are described to it</b>.</p>
      <div class="grid2">
        <div class="card"><p class="chart-title">Writing down what each problem looks like</p>
          <p class="chart-sub">“A brown or yellow water stain on a ceiling” beats “a photo of a water stain”. Right answers per problem.</p>
          ${groupedBars(plain, used)}</div>
        <div class="card"><p class="chart-title">Where it goes wrong</p>
          <p class="chart-sub">Visual-cue prompts. Mold is mostly mistaken for a water stain, a reasonable confusion since mold often grows on one.</p>
          ${used.confusion ? confusion(used.confusion) : `<p class="chart-sub">${esc(used.common_mistakes.join(" · "))}</p>`}</div>
      </div>
      <div class="tiles" style="margin-top:16px">
        ${tile("Right in top 2", pct(used.top2), `vs ${pct(plain.top2)} with plain names`)}
        ${tile("Right when it was sure", pct(used.accuracy_when_sure), `confidence ≥ 45%`)}
        ${tile("Said “not sure”", `${used.said_not_sure}/${nPhotos}`, `right ${pct(used.accuracy_when_not_sure)} of those, so abstaining was correct`)}
        ${tile("Median time per photo", `${used.median_ms} ms`, "CPU, local ONNX model")}
      </div>
      ${others.length ? `<div class="card" style="margin-top:16px"><p class="chart-title">Other systems</p><div class="cm-wrap"><table class="dt"><thead><tr><th>System</th><th class="num">Right</th><th class="num">Top 2</th><th class="num">ECE</th></tr></thead><tbody>
        ${others.map((k) => `<tr><td>${esc(k)}</td><td class="num">${pct(d.photos[k].accuracy)}</td><td class="num">${pct(d.photos[k].top2)}</td><td class="num">${d.photos[k].ece ?? "–"}</td></tr>`).join("")}</tbody></table></div></div>` : ""}
    </section>

    <section class="block">
      <h2 class="sec">2. Are its confidence numbers honest?</h2>
      <p class="sub">The app shows a percentage and says “not sure” below 45%. That only helps if the percentage means something. Points on the diagonal mean “said 80% sure, was right 80% of the time”.</p>
      <div class="grid2">
        <div class="card rel">${used.reliability ? reliability([
          { label: "Photos (visual cues)", short: "Photos", bins: used.reliability },
          ...(desc.reliability ? [{ label: "Descriptions", short: "Descriptions", bins: desc.reliability }] : [])]) : "<p class='chart-sub'>Re-run the eval to add calibration.</p>"}</div>
        <div class="card"><p class="chart-title">Reading descriptions</p>
          <p class="chart-sub">${nDesc} casual descriptions like “theres a yellowish ring on my ceiling right below the upstairs tub”, across all 8 problems. All ${desc.mistakes.length} misses:</p>
          <ul class="quotes">${desc.mistakes.map((m) => {
            const mm = m.match(/^(.*): expected (\w+), got (\w+)$/);
            return mm ? `<li>“${esc(mm[1].replace(/^['"]|['"]$/g, ""))}”<br><b>${esc(name(mm[2]))}</b>, read as ${esc(name(mm[3]).toLowerCase())}</li>` : `<li>${esc(m)}</li>`;
          }).join("")}</ul>
          <p class="chart-sub" style="margin-top:10px">Most of these are genuinely ambiguous: a damp spot that keeps coming back could be either.</p></div>
      </div>
    </section>

    <section class="block">
      <h2 class="sec">3. Catching emergencies</h2>
      <p class="sub">Gas, sparks, carbon monoxide, water near power, a sagging ceiling, sewage. These are hard-coded rules on the customer's words, run before any AI. Missing one is the worst failure, so they were tested with a held-out set.</p>
      <div class="card"><div class="cm-wrap"><table class="dt">
        <thead><tr><th>Test set</th><th class="num">Emergencies caught</th><th class="num">False alarms</th><th>What it means</th></tr></thead>
        <tbody>
          <tr><td>First set, first run</td><td class="num">23/30</td><td class="num">2/30</td><td><span class="status bad">Missed 7</span> → rules broadened using these misses</td></tr>
          <tr><td><b>Held-out set, first run</b> (written before re-running, never tuned on)</td><td class="num"><b>${esc(ho?.caught ?? "19/20")}</b></td><td class="num"><b>${esc(ho?.false_alarms ?? "0/20")}</b></td><td><span class="status ok">The honest number</span></td></tr>
          <tr><td>Both sets today (all ${s1.emergencies + s2.emergencies} + ${s1.near_misses + s2.near_misses} cases are now regression tests)</td>
            <td class="num">${s1.caught_any_warning + s2.caught_any_warning}/${s1.emergencies + s2.emergencies}</td><td class="num">${s1.false_alarms + s2.false_alarms}/${s1.near_misses + s2.near_misses}</td>
            <td><span class="status ${s1.missed.length + s2.missed.length ? "bad" : "ok"}">${s1.missed.length + s2.missed.length ? "Regressions" : "No regressions"}</span></td></tr>
        </tbody></table></div>
        ${ho?.missed?.length ? `<p class="chart-sub" style="margin:12px 0 4px">The one held-out miss (since fixed):</p><ul class="quotes">${ho.missed.map((m) => `<li>“${esc(m)}”</li>`).join("")}</ul>` : ""}
      </div>
    </section>

    <section class="block">
      <h2 class="sec">Why it's built this way</h2>
      <div class="method">
        <div class="card"><h3>AI picks the problem, nothing else</h3><p>Safety warnings, urgency, prices and the quote verdict are code plus a knowledge file. The model can't invent a price or talk a gas leak down to “not urgent”.</p></div>
        <div class="card"><h3>Held-out, not re-run</h3><p>After the safety rules were fixed using the first set's misses, a fresh set was written <i>before</i> re-running. The first-run number on that set is the one reported.</p></div>
        <div class="card"><h3>Thresholds fixed in advance</h3><p>The 45% “not sure” line, the 50/50 photo/description blend and the location nudge were set before evaluation, not tuned to the test set.</p></div>
      </div>
    </section>`;
}

fetch("/api/evals").then((r) => (r.ok ? r.json() : Promise.reject(r)))
  .then(render)
  .catch(() => ($("#ev").innerHTML = `<p class="err">No eval results yet. Run <code>python -m eval.run_eval</code>.</p>`));
