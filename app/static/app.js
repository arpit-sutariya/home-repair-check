const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => "$" + Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 });
const pct = (p) => Math.round(p * 100) + "%";
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : "");
const store = { get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
                set: (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch {} } };

// ------------------------------------------------------------------ icons (24px stroke paths)
const P = {
  droplet: '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
  wrench: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
  spores: '<circle cx="8" cy="9" r="2.2"/><circle cx="15.5" cy="7" r="1.5"/><circle cx="14.5" cy="14.5" r="2.8"/><circle cx="7" cy="16.5" r="1.5"/>',
  crack: '<path d="M4 4h16v16H4z"/><path d="M12 4l-2 5 3 3-3 4 2 4"/>',
  bricks: '<path d="M3 6h18v12H3z M3 10h18 M3 14h18 M9 6v4 M15 10v4 M9 14v4"/>',
  roller: '<path d="M4 4h13v5H4z"/><path d="M17 6.5h3v5h-8v3"/><path d="M11 14.5h2v6h-2z"/>',
  roof: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-5h4v5"/>',
  bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  pin: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
  nav: '<path d="M3 11l18-8-8 18-2-8z"/>',
  star: '<path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z"/>',
  dollar: '<path d="M12 2v20M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
  msg: '<path d="M4 5h16v11H8l-4 4z"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"/>',
  hardhat: '<path d="M3 18h18"/><path d="M5 18v-3a7 7 0 0 1 14 0v3"/><path d="M10 9V6h4v3"/>',
  diag: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
  ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>',
  alert: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>',
  locate: '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
};
const icon = (n) => `<svg viewBox="0 0 24 24" aria-hidden="true">${P[n] || ""}</svg>`;
const ISSUE_ICON = { water_stain: "droplet", plumbing_leak: "wrench", mold: "spores", wall_crack: "crack",
  foundation_crack: "bricks", peeling_paint: "roller", roof_damage: "roof", outlet_damage: "bolt" };

// ------------------------------------------------------------------ theme
function currentTheme() {
  return document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}
function paintThemeButton() {
  const b = $("#theme"); if (!b) return;
  b.innerHTML = icon(currentTheme() === "dark" ? "sun" : "moon");
  b.title = currentTheme() === "dark" ? "Switch to light" : "Switch to dark";
}
$("#theme")?.addEventListener("click", () => {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next; store.set("rc.theme", next); paintThemeButton();
});
paintThemeButton();

// ------------------------------------------------------------------ data
const EXAMPLES = [
  "Brown ring on the ceiling under our upstairs bathroom, getting bigger",
  "Black fuzzy spots in the shower corner, smells musty",
  "Zigzag crack in the brick outside, and the back door started sticking",
  "Outlet in the bedroom feels warm and has black marks",
];
const SAMPLES = [
  { file: "ceiling-stain", label: "Ceiling stain", text: "Yellow-brown stain on the ceiling around the smoke detector. It showed up after heavy rain.", where: "ceiling" },
  { file: "brick-crack", label: "Brick crack", text: "Stair-step crack in the brick on the side of the house.", where: "outside wall" },
  { file: "mold", label: "Dark spots", text: "", where: null },
  { file: "peeling-paint", label: "Peeling paint", text: "", where: null },
];
const VERDICT_TITLES = { low: "Unusually low", typical: "Within the usual range", high: "Above the usual range", very_high: "Far above the usual range" };
const SHORT = { water_stain: "Water stain", plumbing_leak: "Leaking pipe", mold: "Mold", wall_crack: "Wall crack",
  foundation_crack: "Stair-step crack", peeling_paint: "Peeling paint", roof_damage: "Roof damage", outlet_damage: "Outlet damage" };

const state = { image: null, where: null, last: null, text: "", meta: null, coords: null, prosSeq: 0 };

// ------------------------------------------------------------------ photo input
async function shrink(blob, max = 1280) {
  const bmp = await createImageBitmap(blob, { imageOrientation: "from-image" });
  const s = Math.min(1, max / Math.max(bmp.width, bmp.height));
  const c = document.createElement("canvas");
  c.width = Math.round(bmp.width * s); c.height = Math.round(bmp.height * s);
  c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.86);
}
async function setPhoto(blob) {
  if (!blob || !blob.type.startsWith("image/")) return toast("That file isn't an image.");
  try { state.image = await shrink(blob); } catch { return toast("Couldn't read that photo. Try a JPG or PNG."); }
  $("#preview").src = state.image;
  $("#preview").hidden = $("#remove").hidden = false; $("#drop-empty").hidden = true;
}
function clearPhoto() {
  state.image = null; $("#file").value = "";
  $("#preview").hidden = $("#remove").hidden = true; $("#drop-empty").hidden = false;
}
$("#file").onchange = (e) => setPhoto(e.target.files[0]);
$("#remove").onclick = (e) => { e.preventDefault(); e.stopPropagation(); clearPhoto(); };
$("#drop").onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("#file").click(); } };
["dragenter", "dragover"].forEach((t) => $("#drop").addEventListener(t, (e) => { e.preventDefault(); $("#drop").classList.add("over"); }));
["dragleave", "drop"].forEach((t) => $("#drop").addEventListener(t, (e) => { e.preventDefault(); $("#drop").classList.remove("over"); }));
$("#drop").addEventListener("drop", (e) => setPhoto(e.dataTransfer.files[0]));
document.addEventListener("paste", (e) => {
  const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
  if (item) { e.preventDefault(); setPhoto(item.getAsFile()); toast("Photo pasted"); }
});
$("#samples").innerHTML = SAMPLES.map((s, i) =>
  `<button type="button" class="sample" data-i="${i}" aria-label="Try the sample photo: ${esc(s.label)}">
     <img src="/static/samples/${s.file}.jpg" alt="" loading="lazy"><span>${esc(s.label)}</span></button>`).join("");
$$(".sample").forEach((b) => (b.onclick = async () => {
  const s = SAMPLES[b.dataset.i];
  await setPhoto(await fetch(`/static/samples/${s.file}.jpg`).then((r) => r.blob()));
  $("#text").value = s.text; updateCount(); setWhere(s.where);
}));

// ------------------------------------------------------------------ text, room, area
$("#examples").innerHTML = EXAMPLES.map((x) => `<button type="button" class="chip">${esc(x)}</button>`).join("");
$$(".chip").forEach((b) => (b.onclick = () => { $("#text").value = b.textContent; updateCount(); $("#text").focus(); }));
function updateCount() { const n = $("#text").value.length; $("#count").textContent = n > 1200 ? `${n} / 1500` : ""; }
$("#text").addEventListener("input", updateCount);
$("#text").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) $("#form").requestSubmit(); });
function setWhere(loc) {
  state.where = loc;
  $$(".pill").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.l === loc)));
}

const CURRENT = "Current location";
$("#place").value = store.get("rc.place") || "";
$("#place").addEventListener("input", () => { if (state.coords && $("#place").value !== CURRENT) state.coords = null; });
$("#place").addEventListener("change", () => { if ($("#place").value !== CURRENT) store.set("rc.place", $("#place").value.trim() || null); });
$("#place").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); $("#form").requestSubmit(); } });
$("#locate").onclick = () => locate((ok) => { if (ok) { $("#place").value = CURRENT; toast("Using your current location"); } });

function locate(done) {
  if (!navigator.geolocation) { toast("Location isn't available in this browser."); return done(false); }
  navigator.geolocation.getCurrentPosition(
    (p) => { state.coords = { lat: +p.coords.latitude.toFixed(4), lon: +p.coords.longitude.toFixed(4) }; done(true); },
    () => { toast("Couldn't get your location. Type a city or ZIP instead."); done(false); },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
}

// ------------------------------------------------------------------ API
async function api(url, body) {
  const r = await fetch(url, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = j.detail;
    const e = new Error(typeof d === "string" ? d : Array.isArray(d) ? "Please check what you entered." : "Something went wrong. Please try again.");
    e.status = r.status;
    throw e;
  }
  return j;
}
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 2000);
}

// ------------------------------------------------------------------ submit
$("#form").onsubmit = async (e) => {
  e.preventDefault();
  const text = $("#text").value.trim();
  const out = $("#result");
  out.hidden = false;
  if (!state.image && !text) { out.innerHTML = `<p class="err">Add a photo or describe the problem first.</p>`; return; }
  $("#go").disabled = true; $("#go span").textContent = "Checking…";
  out.innerHTML = loadingHTML(!!state.image, !!text);
  out.scrollIntoView({ behavior: "smooth", block: "start" });
  const ticker = animateSteps();
  try {
    state.text = text;
    state.last = await api("/api/diagnose", { image: state.image, text, location: state.where });
    clearInterval(ticker);
    render(state.last);
    loadPros();
  } catch (err) {
    clearInterval(ticker);
    out.innerHTML = `<p class="err">${esc(err.message)}</p>`;
  } finally {
    $("#go").disabled = false; $("#go span").textContent = "Check it";
  }
};

function loadingHTML(photo, text) {
  const steps = ["Checking your words for safety risks",
    photo ? "Comparing the photo with what each problem looks like" : null,
    text ? "Matching your description to known symptoms" : null,
    "Looking up urgency and typical costs"].filter(Boolean);
  return `<div class="loading"><ul class="steps">${steps.map((s, i) =>
    `<li class="${i === 0 ? "on" : ""}"><span class="dot"></span>${s}</li>`).join("")}</ul><div class="skeleton"></div></div>`;
}
// The request is one call, so this only paces the list; the result replaces it the moment it arrives.
function animateSteps() {
  let i = 0;
  return setInterval(() => {
    const li = $$(".steps li");
    if (i >= li.length - 1) return;
    li[i].className = "done"; li[i].querySelector(".dot").textContent = "✓";
    li[++i].className = "on";
  }, 450);
}

// ------------------------------------------------------------------ render: diagnosis
const sureWords = (p) => (p >= 0.75 ? "Fairly sure" : p >= 0.45 ? "Probably" : "Not sure");

function hazardHTML(h) {
  const why = h.id === "model_flag" ? `<p class="why">Flagged by the AI from the photo. It can add a warning, never remove one.</p>`
    : h.matched ? `<p class="why">Shown because you wrote <mark>“${esc(h.matched)}”</mark>. This rule runs before any AI.</p>` : "";
  return `<div class="hazard" role="alert"><h3>${esc(h.title)}</h3>${why}<ol>${h.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol></div>`;
}

function ringHTML(p) {
  const r = 26, c = 2 * Math.PI * r;
  return `<div class="ring" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(p * 100)}" aria-label="Confidence">
    <svg viewBox="0 0 64 64"><circle class="trk" cx="32" cy="32" r="${r}"/><circle class="val" cx="32" cy="32" r="${r}"
      stroke-dasharray="${c}" stroke-dashoffset="${c}" data-off="${c * (1 - p)}"/></svg><b>${pct(p)}</b></div>`;
}

function howHTML(r) {
  const rows = r.breakdown || [];
  const hasP = rows.some((x) => x.photo != null), hasD = rows.some((x) => x.description != null);
  const bars = rows.map((x, i) => `
    <div class="prow ${i === 0 ? "top" : ""}" title="${esc(x.name)}: ${pct(x.final)}${x.photo != null ? ` · photo ${pct(x.photo)}` : ""}${x.description != null ? ` · description ${pct(x.description)}` : ""}${x.location_boost ? " · boosted by location" : ""}">
      <span class="pn">${esc(SHORT[x.id] || x.name)}${x.location_boost ? `<span class="boost">+loc</span>` : ""}</span>
      <span class="ptrack"><span class="f" style="width:${x.final * 100}%"></span>
        ${hasP && hasD ? `<span class="t" style="left:${x.photo * 100}%"></span><span class="t d" style="left:${x.description * 100}%"></span>` : ""}</span>
      <span class="pv">${pct(x.final)}</span></div>`).join("");
  const legend = `<div class="legend"><span><i class="sw final"></i>Combined</span>${hasP && hasD
    ? `<span><i class="sw tick"></i>Photo alone</span><span><i class="sw tick d"></i>Description alone</span>` : ""}</div>`;
  const local = r.engine === "local";
  const facts = [
    ["Engine", local ? "Local models (CLIP ViT-B/32 + BGE-small)" : `Claude (${r.model})`],
    ["Signals", r.used.join(" + ")],
    local && hasP && hasD ? ["Blend", "50% photo, 50% description"] : null,
    r.used.includes("location") ? ["Room", "×1.5 for problems common there"] : null,
    ["“Not sure” below", pct(r.thresholds?.not_sure_below ?? 0.45)],
    ["Safety rules hit", r.hazards.filter((h) => h.id !== "model_flag").length || "none"],
    ["Time", `${r.latency_ms} ms`],
    r.usage ? ["Tokens", `${r.usage.input_tokens} in / ${r.usage.output_tokens} out`] : null,
  ].filter(Boolean);
  return `<details class="how-d"><summary>How it decided</summary>
    <div class="how-grid">
      <div><p class="how-sub">How likely each of the 8 problem types is.${local ? "" : " Claude reports a top pick and a runner-up, mapped to these scores."}</p>${legend}${bars}</div>
      <div><dl class="facts">${facts.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
        <ul class="pipeline">
          <li><span class="who code">CODE</span>Safety rules on your words, before any AI</li>
          <li><span class="who ai">AI</span>Picks the problem type, and only that</li>
          <li><span class="who code">CODE</span>Urgency, prices, quote check, message and local pros</li>
        </ul></div>
    </div></details>`;
}

const rangeScale = (tiers, extra = 0) => Math.max(...tiers.map((t) => t.high), extra) * 1.15;
function tierHTML(t, max) {
  const l = (v) => Math.min(100, (v / max) * 100);
  return `<div class="tier"><div class="tier-row"><span class="tier-name">${esc(t.name)}</span><span class="tier-range">${money(t.low)} – ${money(t.high)}</span></div>
    <div class="range" aria-hidden="true"><span class="band" style="left:${l(t.low)}%;width:${l(t.high) - l(t.low)}%"></span>${t.typical ? `<span class="typ" style="left:${l(t.typical)}%"></span>` : ""}</div>
    <div class="tier-meta">${t.typical ? `Typical ${money(t.typical)} · ` : ""}${t.why ? `Included because ${esc(t.why)} · ` : ""}Source: <a href="${esc(t.url)}" target="_blank" rel="noopener">${esc(t.source)}</a></div></div>`;
}

function render(r) {
  const alt = r.alternatives[0];
  const unsure = r.not_sure && alt ? `<div class="unsure"><b>Not sure yet.</b> It could also be <b>${esc(alt.name.toLowerCase())}</b>. To tell them apart: ${esc(r.tell_apart)} Add that to your description and check again.</div>` : "";
  const c = r.issue.confidence, lvl = r.severity.level;
  const totalLo = r.costs.reduce((a, t) => a + t.low, 0), totalHi = r.costs.reduce((a, t) => a + t.high, 0);
  const max = rangeScale(r.costs);

  $("#result").innerHTML = `
    <div class="result-bar"><h2>Your result</h2><div class="actions">
      <button class="btn" id="print" type="button">Save as PDF</button>
      <button class="btn" id="again" type="button">Check something else</button></div></div>
    <nav class="jump" aria-label="Jump to section">
      <a href="#sec-diag">${icon("diag")}Diagnosis</a><a href="#sec-pros">${icon("hardhat")}Pros near you <span class="badge" id="pros-badge">…</span></a>
      <a href="#sec-cost">${icon("dollar")}Costs</a><a href="#sec-msg">${icon("msg")}Message</a></nav>
    ${r.hazards.map(hazardHTML).join("")}
    <div class="card" id="sec-diag">
      <div class="summary">
        <div class="diag"><span class="issue-ico">${icon(ISSUE_ICON[r.issue.id] || "diag")}</span>
          <div><div class="kicker">Most likely</div><div class="name">${esc(r.issue.name)}</div><div class="short">Usually means ${esc(r.issue.short)}.</div>
            <div class="conf">${ringHTML(c)}<div class="conf-t"><b>${sureWords(c)}</b><span>Based on ${esc(r.used.join(", "))}. Below ${pct(r.thresholds?.not_sure_below ?? 0.45)} it says it's not sure.</span></div></div>
            ${r.seen ? `<div class="seen">${esc(r.seen)}</div>` : ""}${unsure}</div></div>
        <div class="urgency l${lvl}"><h3 class="h">How urgent</h3><span class="tag">${esc(r.severity.label)}</span>
          <div class="scale" aria-hidden="true">${[1, 2, 3, 4, 5].map((i) => `<i class="${i <= lvl ? "on" : ""}"></i>`).join("")}</div>
          <div class="scale-ends"><span>Can wait</span><span>Act now</span></div>
          <p>${esc(r.severity.meaning)}${r.severity.reasons.length ? ` Rated higher because ${esc(r.severity.reasons.join(" and "))}.` : ""}</p></div>
      </div>
      ${howHTML(r)}
    </div>
    <div class="two">
      <div class="card"><div class="card-h"><h2><span class="ico">${icon("hardhat")}</span>Who to call</h2></div>
        <div class="trade">${esc(cap(r.trade))}</div>
        <div class="diy"><b>DIY?</b> ${esc(r.diy)}</div></div>
      <div class="card"><div class="card-h"><h2><span class="ico">${icon("list")}</span>What to do now</h2></div>
        <ol class="todo">${r.now.map((s) => `<li><span>${esc(s)}</span></li>`).join("")}</ol></div>
    </div>
    <div class="card" id="sec-pros"></div>
    <div class="card" id="sec-cost"><div class="card-h"><h2><span class="ico">${icon("dollar")}</span>What it usually costs</h2>
        ${r.costs.length > 1 ? `<span class="cost-total">All of it together: <b>${money(totalLo)} – ${money(totalHi)}</b></span>` : ""}</div>
      <div id="tiers">${r.costs.map((t) => tierHTML(t, max)).join("")}</div>
      <form class="quote" id="qform"><label class="money-in"><span>$</span><input id="amount" inputmode="decimal" autocomplete="off" aria-label="Quote total in dollars" placeholder="Got a quote? Enter the total, e.g. 1200"></label><button class="btn primary">Check quote</button></form>
      <div id="qv" aria-live="polite"></div></div>
    <div class="card" id="sec-msg"><div class="card-h"><h2><span class="ico">${icon("msg")}</span>Message to send contractors</h2>
      <div class="actions copy-btns"><a class="btn sm" id="mail" href="#">Email</a><button class="btn sm" id="copy" type="button">Copy</button></div></div>
      <textarea class="msg" id="msg" aria-label="Message to contractors">${esc(r.message)}</textarea>
      <p class="tier-meta" style="margin:6px 0 0">Edit it before you send it. Includes the questions worth asking for this problem.</p></div>`;

  requestAnimationFrame(() => $$(".ring .val").forEach((el) => (el.style.strokeDashoffset = el.dataset.off)));
  $("#qform").onsubmit = async (e) => {
    e.preventDefault();
    const amount = parseFloat($("#amount").value.replace(/[^0-9.]/g, ""));
    if (!amount) return toast("Enter the quote's total in dollars.");
    const q = await api("/api/quote", { issue_id: r.issue.id, text: state.text, amount }).catch((err) => ({ verdict: "error", message: err.message }));
    const m = rangeScale(r.costs, amount);
    $("#tiers").innerHTML = r.costs.map((t) => tierHTML(t, m)).join("");
    $$("#tiers .range").forEach((el) => el.insertAdjacentHTML("beforeend", `<span class="q" style="left:${Math.min(100, (amount / m) * 100)}%" title="Your quote: ${money(amount)}"></span>`));
    $("#qv").innerHTML = `<div class="qv v-${q.verdict}"><b>${money(amount)}: ${VERDICT_TITLES[q.verdict] || "Couldn't check"}</b>${esc(q.message)}</div>`;
  };
  $("#copy").onclick = async () => {
    try { await navigator.clipboard.writeText($("#msg").value); toast("Copied to clipboard"); }
    catch { $("#msg").select(); toast("Press ⌘C / Ctrl+C to copy"); }
  };
  $("#mail").onclick = (e) => {
    e.preventDefault();
    location.href = `mailto:?subject=${encodeURIComponent("Repair quote request: " + r.issue.name)}&body=${encodeURIComponent($("#msg").value)}`;
  };
  $("#print").onclick = () => { $$("details.how-d").forEach((d) => (d.open = true)); window.print(); };
  $("#again").onclick = () => {
    clearPhoto(); $("#text").value = ""; setWhere(null); updateCount();
    $("#result").hidden = true; window.scrollTo({ top: 0, behavior: "smooth" }); $("#text").focus();
  };
}

// ------------------------------------------------------------------ render: pros near you
const safeUrl = (u) => { if (!u) return null; const v = /^https?:\/\//i.test(u) ? u : "https://" + u; return /^https?:\/\/[^\s"'<>]+$/i.test(v) ? v : null; };
const telHref = (p) => "tel:" + String(p).replace(/[^+\d]/g, "");
const prosHead = (extra = "") => `<div class="card-h"><h2><span class="ico">${icon("hardhat")}</span>Pros near you</h2>${extra}</div>`;

function askAreaHTML(message, isError = false) {
  const msg = esc(message || "Add your city, neighborhood or ZIP to see repair pros near you.");
  return `${prosHead()}${isError ? `<p class="pros-err" role="alert">${icon("alert")}<span>${msg}</span></p>` : `<p class="sub2">${msg}</p>`}
    <form class="inline-area" id="area-form"><input id="area2" placeholder="e.g. USC, Los Angeles or 90007" aria-label="Your city, neighborhood or ZIP" value="${esc($("#place").value === CURRENT ? "" : $("#place").value)}">
      <button class="btn primary" type="submit">${icon("pin")}Find pros</button>
      <button class="btn" type="button" id="locate2">${icon("locate")}Use my location</button></form>`;
}
function bindAskArea() {
  $("#area-form").onsubmit = (e) => {
    e.preventDefault();
    const v = $("#area2").value.trim(); if (!v) return toast("Type a city, neighborhood or ZIP.");
    $("#place").value = v; state.coords = null; store.set("rc.place", v); loadPros();
  };
  $("#locate2").onclick = () => locate((ok) => { if (ok) { $("#place").value = CURRENT; loadPros(); } });
}
function setBadge(t) { const b = $("#pros-badge"); if (b) b.textContent = t; }

async function loadPros() {
  const sec = $("#sec-pros"); if (!sec || !state.last) return;
  const place = $("#place").value.trim();
  if (!state.coords && (!place || place === CURRENT)) { sec.innerHTML = askAreaHTML(); bindAskArea(); setBadge("add area"); return; }
  const seq = ++state.prosSeq;
  sec.innerHTML = `${prosHead(`<span class="where-chip">${icon("pin")}${esc(state.coords ? "your location" : place)}</span>`)}
    <p class="sub2">Finding repair pros for ${esc((SHORT[state.last.issue.id] || "this problem").toLowerCase())} near you…</p>
    <div class="pro-grid"><div class="pro skel"></div><div class="pro skel"></div></div>`;
  setBadge("…");
  try {
    const body = { issue_id: state.last.issue.id, ...(state.coords ? state.coords : { place }) };
    const p = await api("/api/pros", body);
    if (seq !== state.prosSeq) return;
    if (!p.found) { sec.innerHTML = askAreaHTML(p.message, true); bindAskArea(); setBadge("add area"); return; }
    renderPros(p);
  } catch (err) {
    if (seq !== state.prosSeq) return;
    // A 404 here means the server predates /api/pros (page files are newer than the running process).
    const msg = err.status === 404 && err.message === "Not Found"
      ? "The app server is out of date and can't look up pros. Restart it (Ctrl+C, then run uvicorn again) and reload this page."
      : err.message;
    sec.innerHTML = askAreaHTML(msg, true); bindAskArea(); setBadge("!");
  }
}

function proCard(x) {
  const web = safeUrl(x.website), dir = safeUrl(x.directions);
  const meta = [
    x.rating != null ? `<span class="stars">${icon("star")}${x.rating.toFixed(1)}<span>(${x.reviews ?? 0})</span></span>` : "",
    x.open_now === true ? `<span class="open">Open now</span>` : x.open_now === false ? `<span class="closed">Closed now</span>` : "",
    x.hours ? `<span title="Opening hours">${esc(x.hours)}</span>` : "",
  ].filter(Boolean).join("");
  return `<div class="pro">
    <div class="pro-top"><div class="pro-name">${esc(x.name)}</div>${x.distance_km != null ? `<span class="dist">${x.distance_km} km</span>` : ""}</div>
    ${meta ? `<div class="pro-meta">${meta}</div>` : ""}
    ${x.address ? `<div class="pro-addr">${icon("pin")}<span>${esc(x.address)}</span></div>` : ""}
    ${x.phone ? `<div class="pro-phone">${esc(x.phone)}</div>` : `<div class="pro-phone none">No phone number listed</div>`}
    <div class="pro-actions">
      ${x.phone ? `<a class="btn sm primary" href="${esc(telHref(x.phone))}">${icon("phone")}Call</a>` : ""}
      ${web ? `<a class="btn sm" href="${esc(web)}" target="_blank" rel="noopener nofollow">${icon("globe")}Website</a>` : ""}
      ${x.email ? `<a class="btn sm" href="mailto:${esc(x.email)}">${icon("msg")}Email</a>` : ""}
      ${dir ? `<a class="btn sm" href="${esc(dir)}" target="_blank" rel="noopener">${icon("nav")}Directions</a>` : ""}
    </div></div>`;
}

function linksHTML(t) {
  return `<a class="btn sm" href="${esc(safeUrl(t.links.google_maps))}" target="_blank" rel="noopener">${icon("ext")}Google Maps</a>
          <a class="btn sm" href="${esc(safeUrl(t.links.yelp))}" target="_blank" rel="noopener">${icon("ext")}Yelp</a>`;
}

function renderPros(p) {
  const total = p.trades.reduce((a, t) => a + t.results.length, 0);
  setBadge(String(total));
  const tabs = p.trades.length > 1 ? `<div class="tabs" role="tablist">${p.trades.map((t, i) =>
    `<button class="tab" role="tab" type="button" aria-selected="${i === 0}" data-i="${i}">${esc(t.label)}<span class="n">${t.results.length}</span></button>`).join("")}</div>` : "";
  const panes = p.trades.map((t, i) => `<div data-pane="${i}" ${i ? "hidden" : ""}>
    ${t.results.length ? `<div class="pro-grid">${t.results.map(proCard).join("")}</div>
      <div class="more-links">More ${esc(t.label.toLowerCase())} options: ${linksHTML(t)}</div>`
      : `<div class="empty"><b>No ${esc(t.label.toLowerCase())} listings within ${p.radius_km} km in ${p.source === "google" ? "Google Places" : "OpenStreetMap"}.</b>
          Search the big directories instead:<div class="search-links">${linksHTML(t)}</div></div>`}</div>`).join("");
  const changeBtn = `<button class="btn sm" type="button" id="change-area">${icon("pin")}Change</button>`;
  $("#sec-pros").innerHTML = `${prosHead(`<div class="pros-head-r"><span class="where-chip">${icon("pin")}${esc(p.where.label)}</span>${changeBtn}</div>`)}
    <p class="sub2">Real businesses for the trades this problem usually needs, within about ${p.radius_km} km, closest first.${p.errors?.length ? " Live listings are partly unavailable right now, so try the search links." : ""}</p>
    ${tabs}${panes}
    <p class="pros-note">${esc(p.attribution)}. ${esc(p.note)}</p>`;
  $$("#sec-pros .tab").forEach((b) => (b.onclick = () => {
    $$("#sec-pros .tab").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
    $$("#sec-pros [data-pane]").forEach((el) => (el.hidden = el.dataset.pane !== b.dataset.i));
  }));
  $("#change-area").onclick = () => { $("#sec-pros").innerHTML = askAreaHTML("Where should we look?"); bindAskArea(); $("#area2").focus(); };
}

// ------------------------------------------------------------------ start
(async () => {
  try {
    const m = state.meta = await api("/api/meta");
    $("#engine").textContent = m.engine === "claude" ? `Claude · ${m.model}` : "Local AI · no API key";
    $("#where").innerHTML = m.locations.map((l) => `<button type="button" class="pill" aria-pressed="false" data-l="${esc(l)}">${esc(cap(l))}</button>`).join("");
    $$(".pill").forEach((b) => (b.onclick = () => setWhere(state.where === b.dataset.l ? null : b.dataset.l)));
    if (!m.ready) {
      $("#warming").hidden = false; $("#engine").classList.add("off");
      const poll = setInterval(async () => {
        const s = await api("/api/meta").catch(() => null);
        if (s?.ready) { clearInterval(poll); $("#warming").hidden = true; $("#engine").classList.remove("off"); toast("Models ready"); }
      }, 3000);
    }
  } catch {
    $("#engine").textContent = "Offline"; $("#engine").classList.add("off");
  }
})();
