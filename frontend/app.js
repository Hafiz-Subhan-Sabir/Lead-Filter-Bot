const $ = (id) => document.getElementById(id);

const PLATFORM_LABELS = {
  all: "All Platforms",
  linkedin: "LinkedIn",
  whatsapp: "WhatsApp",
  upwork: "Upwork",
  fiverr: "Fiverr",
  facebook: "Facebook",
  instagram: "Instagram",
  google_maps: "Google Maps",
  other: "Web",
};

const STAGES = [
  { id: "profile", title: "Saving intent profile", sub: "Preparing deep search…", pct: 8 },
  { id: "search", title: "Multi-pass platform search", sub: "Querying platforms thoroughly…", pct: 35 },
  { id: "ai", title: "AI classifying candidates", sub: "Scoring genuineness one by one…", pct: 68 },
  { id: "filters", title: "Strict quality filters", sub: "Removing weak / spam results…", pct: 86 },
  { id: "rank", title: "Final ranking", sub: "Ordering best leads first…", pct: 96 },
];

let itemIndex = {};
const selectedIds = new Set();
let stageTimer = null;
let elapsedTimer = null;
let searchStartedAt = 0;

const apiStatus = $("apiStatus");
const errorEl = $("error");
const runBtn = $("runBtn");
const confInput = $("min_confidence");
const confLabel = $("confLabel");
const matchesList = $("matchesList");
const rejectedList = $("rejectedList");
const matchCount = $("matchCount");
const rejectCount = $("rejectCount");
const summary = $("summary");
const platformInput = $("platform");
const lookingLabel = $("lookingLabel");
const sourceTag = $("sourceTag");
const selectAll = $("selectAll");
const inspectBtn = $("inspectBtn");
const copyEmailsBtn = $("copyEmailsBtn");
const drawer = $("drawer");
const drawerBody = $("drawerBody");
const loadingPanel = $("loadingPanel");
const emptyState = $("emptyState");
const resultsContent = $("resultsContent");
const progressBar = $("progressBar");
const loadingTitle = $("loadingTitle");
const loadingSub = $("loadingSub");
const elapsedEl = $("elapsedTimer");

function currentPlatform() {
  return platformInput.value || "all";
}
function platformLabel(key) {
  return PLATFORM_LABELS[key] || key || "Unknown";
}
function setPlatform(key) {
  platformInput.value = key;
  lookingLabel.textContent = platformLabel(key);
  sourceTag.textContent = platformLabel(key);
  document.querySelectorAll(".platform-chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.platform === key);
  });
}
document.querySelectorAll(".platform-chip").forEach((chip) => {
  chip.addEventListener("click", () => setPlatform(chip.dataset.platform));
});
confInput.addEventListener("input", () => {
  confLabel.textContent = Number(confInput.value).toFixed(2);
});
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    matchesList.hidden = tab.dataset.tab !== "matches";
    rejectedList.hidden = tab.dataset.tab !== "rejected";
    selectAll.checked = false;
    syncSelectionButtons();
  });
});

async function checkHealth() {
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error("down");
    apiStatus.textContent = "API online";
    apiStatus.className = "status ok";
  } catch {
    apiStatus.textContent = "API offline";
    apiStatus.className = "status bad";
  }
}

function showError(msg) {
  errorEl.hidden = !msg;
  errorEl.textContent = msg || "";
}

async function readError(res) {
  const text = await res.text();
  try {
    const data = JSON.parse(text);
    if (typeof data.detail === "string") return data.detail;
    return JSON.stringify(data.detail || data);
  } catch {
    return text.slice(0, 300) || `HTTP ${res.status}`;
  }
}

function formatElapsed(ms) {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

function setStage(stageId) {
  const stage = STAGES.find((s) => s.id === stageId) || STAGES[0];
  loadingTitle.textContent = stage.title;
  const elapsed = formatElapsed(Date.now() - searchStartedAt);
  loadingSub.textContent = `${stage.sub} · ${elapsed} elapsed (target 3–5 min)`;
  progressBar.style.width = `${stage.pct}%`;
  document.querySelectorAll("#stageList li").forEach((li) => {
    li.classList.remove("active", "done");
    const idx = STAGES.findIndex((s) => s.id === li.dataset.stage);
    const cur = STAGES.findIndex((s) => s.id === stageId);
    if (idx < cur) li.classList.add("done");
    if (idx === cur) li.classList.add("active");
  });
}

function startLoadingVisual() {
  emptyState.hidden = true;
  resultsContent.hidden = true;
  loadingPanel.hidden = false;
  progressBar.style.width = "6%";
  searchStartedAt = Date.now();
  elapsedEl.textContent = "0:00";
  setStage("profile");

  clearInterval(elapsedTimer);
  elapsedTimer = setInterval(() => {
    elapsedEl.textContent = formatElapsed(Date.now() - searchStartedAt);
  }, 1000);

  let i = 0;
  clearInterval(stageTimer);
  // Slow visual stage advances to match deep search duration
  stageTimer = setInterval(() => {
    i = Math.min(i + 1, STAGES.length - 2);
    setStage(STAGES[i].id);
  }, 45000);
}

function finishLoadingVisual() {
  clearInterval(stageTimer);
  stageTimer = null;
  setStage("rank");
  progressBar.style.width = "100%";
}

function stopLoadingVisual(showEmpty) {
  clearInterval(stageTimer);
  clearInterval(elapsedTimer);
  stageTimer = null;
  elapsedTimer = null;
  loadingPanel.hidden = true;
  if (showEmpty) {
    emptyState.hidden = false;
    resultsContent.hidden = true;
  }
}

function badge(text, className = "") {
  const span = document.createElement("span");
  span.className = className ? `badge ${className}` : "badge";
  span.textContent = text;
  return span;
}

function syncSelectionButtons() {
  const n = selectedIds.size;
  inspectBtn.disabled = n === 0;
  copyEmailsBtn.disabled = n === 0;
  inspectBtn.textContent = n ? `Inspect (${n})` : "Inspect";
}

function toggleSelect(id, checked) {
  if (checked) selectedIds.add(id);
  else selectedIds.delete(id);
  syncSelectionButtons();
}

function visibleList() {
  return matchesList.hidden ? rejectedList : matchesList;
}

selectAll.addEventListener("change", () => {
  visibleList().querySelectorAll('input[type="checkbox"][data-id]').forEach((box) => {
    box.checked = selectAll.checked;
    toggleSelect(Number(box.dataset.id), selectAll.checked);
  });
});

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function contactLines(item) {
  const name = item.contact_name || item.uploader_name;
  const bits = [];
  if (name) bits.push(`<span><strong>Name:</strong> ${escapeHtml(name)}</span>`);
  if (item.email) bits.push(`<span><strong>Email:</strong> ${escapeHtml(item.email)}</span>`);
  if (item.phone) bits.push(`<span><strong>Phone:</strong> ${escapeHtml(item.phone)}</span>`);
  if (item.company_name) bits.push(`<span><strong>Company:</strong> ${escapeHtml(item.company_name)}</span>`);
  return bits;
}

function renderCard(item, isMatch) {
  itemIndex[item.item_id] = item;
  const card = document.createElement("article");
  card.className = `card ${isMatch ? "match" : "reject"}`;
  const head = document.createElement("div");
  head.className = "card-head";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.dataset.id = String(item.item_id);
  cb.checked = selectedIds.has(item.item_id);
  cb.addEventListener("change", () => toggleSelect(item.item_id, cb.checked));
  const body = document.createElement("div");
  body.style.flex = "1";
  const top = document.createElement("div");
  top.className = "card-top";
  top.appendChild(badge(platformLabel(item.source), "platform"));
  top.appendChild(badge(item.category || "unknown", isMatch ? "accent" : ""));
  top.appendChild(badge(`genuine ${Math.round(item.genuine_score || 0)}`, "genuine"));
  top.appendChild(badge(`${(item.confidence ?? 0).toFixed(2)} conf`));
  const text = document.createElement("p");
  text.textContent = item.raw_text;
  const reason = document.createElement("p");
  reason.className = "reason";
  reason.textContent = item.reason || "";
  const contacts = contactLines(item);
  let contactBox = null;
  if (contacts.length) {
    contactBox = document.createElement("div");
    contactBox.className = "contact-box";
    contactBox.innerHTML = `<div class="row">${contacts.join("")}</div>`;
  }
  const footer = document.createElement("div");
  footer.className = "card-footer";
  const inspectOne = document.createElement("button");
  inspectOne.type = "button";
  inspectOne.className = "ghost-btn";
  inspectOne.textContent = "Details";
  inspectOne.addEventListener("click", () => openDrawer([item]));
  footer.appendChild(inspectOne);
  if (item.url) {
    const link = document.createElement("a");
    link.className = "open-link";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Open source →";
    footer.appendChild(link);
  }
  body.append(top, text, reason);
  if (contactBox) body.appendChild(contactBox);
  body.appendChild(footer);
  head.append(cb, body);
  card.appendChild(head);
  return card;
}

function renderResults(data) {
  matchesList.innerHTML = "";
  rejectedList.innerHTML = "";
  itemIndex = {};
  selectedIds.clear();
  selectAll.checked = false;
  syncSelectionButtons();
  clearInterval(elapsedTimer);

  const matches = data.matches || [];
  const rejected = data.rejected || [];
  const source = data.source || currentPlatform();
  const elapsed = formatElapsed(Date.now() - searchStartedAt);

  sourceTag.textContent = platformLabel(source);
  matchCount.textContent = String(matches.length);
  rejectCount.textContent = String(rejected.length);
  summary.textContent = `${data.total_items} scanned · ${matches.length} strong matches · ${rejected.length} rejected · ${elapsed}`;

  emptyState.hidden = true;
  resultsContent.hidden = false;
  loadingPanel.hidden = true;

  if (!matches.length) {
    matchesList.innerHTML = `<p class="empty">No strong matches after deep filtering. Try a clearer intent.</p>`;
  } else {
    matches.forEach((m) => matchesList.appendChild(renderCard(m, true)));
  }
  if (!rejected.length) {
    rejectedList.innerHTML = `<p class="empty">Nothing rejected.</p>`;
  } else {
    rejected.forEach((m) => rejectedList.appendChild(renderCard(m, false)));
  }
  document.querySelector('.tab[data-tab="matches"]').click();
}

function openDrawer(items) {
  drawerBody.innerHTML = "";
  items.forEach((item) => {
    const el = document.createElement("article");
    el.className = "detail-card";
    const name = item.contact_name || item.uploader_name || "Unknown contact";
    el.innerHTML = `
      <h3>${escapeHtml(name)}</h3>
      <p><strong>Platform:</strong> ${escapeHtml(platformLabel(item.source))}</p>
      <p><strong>Genuine:</strong> ${Math.round(item.genuine_score || 0)} / 100</p>
      <p><strong>Email:</strong> ${escapeHtml(item.email || "—")}</p>
      <p><strong>Phone:</strong> ${escapeHtml(item.phone || "—")}</p>
      <p class="muted">${escapeHtml(item.raw_text)}</p>
      <p class="muted">${escapeHtml(item.reason || "")}</p>
      ${item.url ? `<p><a class="open-link" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">Open source →</a></p>` : ""}
    `;
    drawerBody.appendChild(el);
  });
  drawer.hidden = false;
}

function closeDrawer() {
  drawer.hidden = true;
}

inspectBtn.addEventListener("click", () => {
  openDrawer([...selectedIds].map((id) => itemIndex[id]).filter(Boolean));
});
copyEmailsBtn.addEventListener("click", async () => {
  const emails = [...selectedIds]
    .map((id) => itemIndex[id])
    .filter(Boolean)
    .flatMap((i) => (i.emails?.length ? i.emails : i.email ? [i.email] : []));
  const unique = [...new Set(emails)];
  if (!unique.length) {
    showError("No emails in selected leads.");
    return;
  }
  await navigator.clipboard.writeText(unique.join("\n"));
  $("hint").textContent = `Copied ${unique.length} email(s).`;
});
$("closeDrawer").addEventListener("click", closeDrawer);
$("drawerBackdrop").addEventListener("click", closeDrawer);

async function runDiscover() {
  showError("");
  const profilePayload = {
    name: $("name").value.trim() || "Deep search",
    intent: $("intent").value.trim(),
    want_remote: $("want_remote").checked,
    want_onsite: $("want_onsite").checked,
    want_hiring: $("want_hiring").checked,
    want_startups: $("want_startups").checked,
    want_no_website: $("want_no_website").checked,
    min_confidence: Number(confInput.value),
  };
  const source = currentPlatform();
  const maxHoursRaw = $("max_hours").value;
  const extra = ($("paste")?.value || "").trim();

  if (!profilePayload.intent) {
    showError("Enter what you want to find.");
    return;
  }

  runBtn.disabled = true;
  $("hint").textContent = "Deep search running — keep this tab open…";
  summary.textContent = "Deep search in progress (3–5 min)…";
  startLoadingVisual();

  try {
    setStage("profile");
    const profileRes = await fetch("/profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profilePayload),
    });
    if (!profileRes.ok) throw new Error(await readError(profileRes));
    const profile = await profileRes.json();

    setStage("search");
    const discoverRes = await fetch("/discover/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: profile.id,
        source,
        max_hours_ago: maxHoursRaw ? Number(maxHoursRaw) : null,
        require_email: $("require_email").checked,
        require_phone: $("require_phone").checked,
        require_name: $("require_name").checked,
        extra_text: extra,
        max_results: 40,
        deep: true,
      }),
    });
    if (!discoverRes.ok) throw new Error(await readError(discoverRes));
    setStage("ai");
    const data = await discoverRes.json();
    setStage("filters");
    finishLoadingVisual();
    await new Promise((r) => setTimeout(r, 400));
    renderResults(data);
    $("hint").textContent = `Done · ${data.matches?.length || 0} strong match(es)`;
  } catch (err) {
    stopLoadingVisual(true);
    summary.textContent = "Ready when you are.";
    showError(err.message || "Search failed");
    $("hint").textContent = "Try again with a clearer intent.";
  } finally {
    runBtn.disabled = false;
  }
}

runBtn.addEventListener("click", runDiscover);
$("paste").value = "";
$("intent").value = "";
$("name").value = "";
setPlatform("all");
checkHealth();
