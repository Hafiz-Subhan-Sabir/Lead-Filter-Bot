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
  other: "Other / Web",
};

const STAGES = [
  { id: "profile", title: "Saving your intent", sub: "Creating search profile…", pct: 12 },
  { id: "search", title: "Searching platforms", sub: "Looking through public listings…", pct: 40 },
  { id: "ai", title: "AI matching & contacts", sub: "Checking genuineness…", pct: 70 },
  { id: "filters", title: "Applying filters", sub: "Time + contact rules…", pct: 88 },
  { id: "rank", title: "Ranking genuine leads", sub: "Preparing final results…", pct: 97 },
];

let itemIndex = {};
const selectedIds = new Set();
let stageTimer = null;

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

function currentPlatform() {
  return platformInput.value || "all";
}

function platformLabel(key) {
  return PLATFORM_LABELS[key] || key || "Unknown";
}

function setPlatform(key) {
  platformInput.value = key;
  lookingLabel.textContent = platformLabel(key);
  sourceTag.textContent = `Platform: ${platformLabel(key)}`;
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
    const which = tab.dataset.tab;
    matchesList.hidden = which !== "matches";
    rejectedList.hidden = which !== "rejected";
    selectAll.checked = false;
    syncSelectionButtons();
  });
});

async function checkHealth() {
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error("API down");
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

function setStage(stageId) {
  const stage = STAGES.find((s) => s.id === stageId) || STAGES[0];
  loadingTitle.textContent = stage.title;
  loadingSub.textContent = stage.sub;
  progressBar.style.width = `${stage.pct}%`;
  document.querySelectorAll("#stageList li").forEach((li) => {
    const id = li.dataset.stage;
    li.classList.remove("active", "done");
    const idx = STAGES.findIndex((s) => s.id === id);
    const cur = STAGES.findIndex((s) => s.id === stageId);
    if (idx < cur) li.classList.add("done");
    if (idx === cur) li.classList.add("active");
  });
}

function startLoadingVisual() {
  emptyState.hidden = true;
  resultsContent.hidden = true;
  loadingPanel.hidden = false;
  progressBar.style.width = "8%";
  setStage("profile");
  let i = 0;
  clearInterval(stageTimer);
  stageTimer = setInterval(() => {
    i = Math.min(i + 1, STAGES.length - 2);
    setStage(STAGES[i].id);
  }, 1600);
}

function finishLoadingVisual() {
  clearInterval(stageTimer);
  stageTimer = null;
  setStage("rank");
  progressBar.style.width = "100%";
}

function stopLoadingVisual(showEmpty) {
  clearInterval(stageTimer);
  stageTimer = null;
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
  inspectBtn.textContent = n ? `Inspect selected (${n})` : "Inspect selected";
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
  const boxes = visibleList().querySelectorAll('input[type="checkbox"][data-id]');
  boxes.forEach((box) => {
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
  top.appendChild(badge(`confidence ${(item.confidence ?? 0).toFixed(2)}`));
  if (item.has_contact) top.appendChild(badge("contact", "accent"));

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
  inspectOne.textContent = "View details";
  inspectOne.addEventListener("click", () => openDrawer([item]));

  if (item.url) {
    const link = document.createElement("a");
    link.className = "open-link";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Open source →";
    footer.append(inspectOne, link);
  } else {
    footer.append(inspectOne);
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

  const matches = data.matches || [];
  const rejected = data.rejected || [];
  const source = data.source || currentPlatform();
  const filteredOut = data.filtered_out || 0;

  sourceTag.textContent = `Platform: ${platformLabel(source)}`;
  matchCount.textContent = String(matches.length);
  rejectCount.textContent = String(rejected.length);
  summary.textContent = `${data.total_items} found · ${matches.length} match · ${rejected.length} rejected${filteredOut ? ` · ${filteredOut} filtered` : ""}`;

  emptyState.hidden = true;
  resultsContent.hidden = false;
  loadingPanel.hidden = true;

  if (!matches.length) {
    matchesList.innerHTML = `<p class="empty">No strong matches. Try a clearer intent or turn off strict contact filters.</p>`;
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
      <p><strong>Company:</strong> ${escapeHtml(item.company_name || "—")}</p>
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
    showError("No emails in the selected leads.");
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
    name: $("name").value.trim() || "Search",
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
    showError("Enter what you want to find (intent).");
    return;
  }

  runBtn.disabled = true;
  $("hint").textContent = "Searching platforms…";
  summary.textContent = "Looking across platforms…";
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
        max_results: 20,
      }),
    });
    if (!discoverRes.ok) throw new Error(await readError(discoverRes));

    setStage("ai");
    const data = await discoverRes.json();
    setStage("filters");
    finishLoadingVisual();
    await new Promise((r) => setTimeout(r, 300));
    renderResults(data);
    $("hint").textContent = `Done · ${data.matches?.length || 0} match(es) from auto search`;
  } catch (err) {
    stopLoadingVisual(true);
    summary.textContent = "Waiting for your intent…";
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
