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

let itemIndex = {};
const selectedIds = new Set();
let elapsedTimer = null;
let searchStartedAt = 0;
const stats = { queries: 0, found: 0, checked: 0, matches: 0 };

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
const livePlatform = $("livePlatform");
const liveQuery = $("liveQuery");
const activityFeed = $("activityFeed");

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
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

function updateStats() {
  $("statQueries").textContent = String(stats.queries);
  $("statFound").textContent = String(stats.found);
  $("statChecked").textContent = String(stats.checked);
  $("statMatches").textContent = String(stats.matches);
}

function addActivity(platform, message, kind = "") {
  const row = document.createElement("div");
  row.className = `activity-item ${kind}`.trim();
  const plat = document.createElement("span");
  plat.className = "plat";
  plat.textContent = platformLabel(platform || "all");
  const msg = document.createElement("div");
  msg.className = "msg";
  msg.textContent = message;
  row.append(plat, msg);
  activityFeed.prepend(row);
  while (activityFeed.children.length > 80) {
    activityFeed.removeChild(activityFeed.lastChild);
  }
}

function setProgress(pct) {
  progressBar.style.width = `${Math.max(4, Math.min(100, pct))}%`;
}

function startLoadingVisual() {
  emptyState.hidden = true;
  resultsContent.hidden = true;
  loadingPanel.hidden = false;
  activityFeed.innerHTML = "";
  stats.queries = 0;
  stats.found = 0;
  stats.checked = 0;
  stats.matches = 0;
  updateStats();
  livePlatform.textContent = "—";
  liveQuery.textContent = "Starting deep search…";
  loadingTitle.textContent = "Deep search running…";
  loadingSub.textContent = "Watch each platform and query below";
  setProgress(4);
  searchStartedAt = Date.now();
  elapsedEl.textContent = "0:00";
  clearInterval(elapsedTimer);
  elapsedTimer = setInterval(() => {
    elapsedEl.textContent = formatElapsed(Date.now() - searchStartedAt);
  }, 1000);
}

function stopLoadingVisual(showEmpty) {
  clearInterval(elapsedTimer);
  elapsedTimer = null;
  loadingPanel.hidden = true;
  if (showEmpty) {
    emptyState.hidden = false;
    resultsContent.hidden = true;
  }
}

function handleProgressEvent(ev) {
  const type = ev.type;
  const platform = ev.platform || ev.source || currentPlatform();

  if (type === "stage") {
    loadingTitle.textContent = ev.message || "Working…";
    if (ev.stage === "profile") setProgress(8);
    if (ev.stage === "queries") setProgress(12);
    if (ev.stage === "search_complete") setProgress(45);
    if (ev.stage === "classify") setProgress(55);
    if (ev.stage === "rank") setProgress(92);
    addActivity(platform, ev.message || "Stage update");
  }

  if (type === "queries_ready") {
    liveQuery.textContent = ev.message || "Queries ready";
    addActivity("all", ev.message || "Queries ready");
    setProgress(15);
  }

  if (type === "searching") {
    stats.queries = ev.index || stats.queries + 1;
    updateStats();
    livePlatform.textContent = platformLabel(platform);
    liveQuery.textContent = ev.query || ev.message || "Searching…";
    loadingTitle.textContent = `Searching ${platformLabel(platform)}`;
    loadingSub.textContent = `Pass ${ev.index || "?"} / ${ev.total || "?"}`;
    const pct = 15 + (35 * (ev.index || 1)) / Math.max(1, ev.total || 1);
    setProgress(pct);
    addActivity(platform, `Looking for: ${ev.query || ev.message}`);
  }

  if (type === "found") {
    stats.found = ev.candidates || stats.found + 1;
    updateStats();
    addActivity(platform, ev.message || ev.title || "Found listing");
  }

  if (type === "search_done") {
    addActivity(platform, ev.message || "Search pass done");
  }

  if (type === "pause") {
    liveQuery.textContent = ev.message || "Pacing…";
    addActivity(platform, ev.message || "Pacing before next search");
  }

  if (type === "classify") {
    stats.checked = ev.index || stats.checked + 1;
    updateStats();
    livePlatform.textContent = platformLabel(platform);
    liveQuery.textContent = ev.preview || ev.message || "Classifying…";
    loadingTitle.textContent = `AI on ${platformLabel(platform)}`;
    loadingSub.textContent = `Candidate ${ev.index}/${ev.total}`;
    const pct = 50 + (40 * (ev.index || 1)) / Math.max(1, ev.total || 1);
    setProgress(pct);
    addActivity(platform, ev.message || `Checking ${ev.index}/${ev.total}`);
  }

  if (type === "match") {
    stats.matches += 1;
    updateStats();
    addActivity(platform, ev.message || "Match found", "match-row");
  }

  if (type === "reject") {
    addActivity(platform, ev.message || "Rejected", "reject-row");
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
  summary.textContent = `${data.total_items} scanned · ${matches.length} strong · ${rejected.length} rejected · ${elapsed}`;

  emptyState.hidden = true;
  resultsContent.hidden = false;
  loadingPanel.hidden = true;
  setProgress(100);

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
  $("hint").textContent = "Live search running — watch platforms below…";
  summary.textContent = "Deep search in progress…";
  startLoadingVisual();

  try {
    const profileRes = await fetch("/profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profilePayload),
    });
    if (!profileRes.ok) throw new Error(await readError(profileRes));
    const profile = await profileRes.json();

    const res = await fetch("/discover/stream", {
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
    if (!res.ok) throw new Error(await readError(res));
    if (!res.body) throw new Error("No live stream from server");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        let ev;
        try {
          ev = JSON.parse(line);
        } catch {
          continue;
        }
        if (ev.type === "done") {
          finalResult = ev.result;
          addActivity(source, ev.message || "Finished", "match-row");
          setProgress(100);
        } else if (ev.type === "error") {
          throw new Error(ev.message || "Search failed");
        } else {
          handleProgressEvent(ev);
        }
      }
    }

    if (!finalResult) throw new Error("Search ended without results");
    renderResults(finalResult);
    $("hint").textContent = `Done · ${finalResult.matches?.length || 0} strong match(es)`;
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
