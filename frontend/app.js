const $ = (id) => document.getElementById(id);

const PLATFORM_LABELS = {
  linkedin: "LinkedIn",
  whatsapp: "WhatsApp",
  upwork: "Upwork",
  fiverr: "Fiverr",
  facebook: "Facebook",
  instagram: "Instagram",
  google_maps: "Google Maps",
  other: "Other / Paste",
};

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

function currentPlatform() {
  return platformInput.value || "other";
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

function badge(text, className = "") {
  const span = document.createElement("span");
  span.className = className ? `badge ${className}` : "badge";
  span.textContent = text;
  return span;
}

function renderCard(item, isMatch) {
  const card = document.createElement("article");
  card.className = `card ${isMatch ? "match" : "reject"}`;

  const top = document.createElement("div");
  top.className = "card-top";
  top.appendChild(badge(platformLabel(item.source), "platform"));
  top.appendChild(badge(item.category || "unknown", isMatch ? "accent" : ""));
  if (item.work_type && item.work_type !== "unknown") {
    top.appendChild(badge(item.work_type));
  }
  if (item.company_type && item.company_type !== "unknown") {
    top.appendChild(badge(item.company_type));
  }
  top.appendChild(badge(`confidence ${(item.confidence ?? 0).toFixed(2)}`));
  if (item.is_lead) top.appendChild(badge("lead", "accent"));

  const text = document.createElement("p");
  text.textContent = item.raw_text;

  const reason = document.createElement("p");
  reason.className = "reason";
  reason.textContent = item.reason || "";

  const footer = document.createElement("div");
  footer.className = "card-footer";

  if (item.url) {
    const link = document.createElement("a");
    link.className = "open-link";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Open original post →";
    footer.appendChild(link);
  } else {
    const missing = document.createElement("span");
    missing.className = "no-link";
    missing.textContent = "No link pasted — add URL under each post next time";
    footer.appendChild(missing);
  }

  card.append(top, text, reason, footer);
  return card;
}

function renderResults(data) {
  matchesList.innerHTML = "";
  rejectedList.innerHTML = "";

  const matches = data.matches || [];
  const rejected = data.rejected || [];
  const source = data.source || currentPlatform();

  sourceTag.textContent = `Platform: ${platformLabel(source)}`;
  matchCount.textContent = String(matches.length);
  rejectCount.textContent = String(rejected.length);
  summary.textContent = `${data.total_items} items on ${platformLabel(source)} · ${matches.length} match · ${rejected.length} rejected`;

  if (!matches.length) {
    matchesList.innerHTML = `<p class="empty">No matches for this intent on ${platformLabel(source)}.</p>`;
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

async function runFilter() {
  showError("");
  runBtn.disabled = true;
  $("hint").textContent = "Creating profile & calling AI…";

  const profilePayload = {
    name: $("name").value.trim() || "Untitled",
    intent: $("intent").value.trim(),
    want_remote: $("want_remote").checked,
    want_onsite: $("want_onsite").checked,
    want_hiring: $("want_hiring").checked,
    want_startups: $("want_startups").checked,
    want_no_website: $("want_no_website").checked,
    min_confidence: Number(confInput.value),
  };

  const paste = $("paste").value.trim();
  const source = currentPlatform();

  if (!profilePayload.intent) {
    showError("Write what you are looking for in the Intent box.");
    runBtn.disabled = false;
    $("hint").textContent = "AI will sort matches vs rejected.";
    return;
  }
  if (!paste) {
    showError("Paste at least one message.");
    runBtn.disabled = false;
    $("hint").textContent = "AI will sort matches vs rejected.";
    return;
  }

  try {
    const profileRes = await fetch("/profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profilePayload),
    });
    if (!profileRes.ok) {
      const err = await profileRes.text();
      throw new Error(err || "Failed to create profile");
    }
    const profile = await profileRes.json();

    const filterRes = await fetch("/filter/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: profile.id,
        text: paste,
        source,
      }),
    });
    if (!filterRes.ok) {
      const err = await filterRes.text();
      throw new Error(err || "Filter failed");
    }
    const data = await filterRes.json();
    renderResults(data);
    $("hint").textContent = `Done on ${platformLabel(source)} · Profile #${profile.id}`;
  } catch (err) {
    showError(err.message || "Something went wrong");
    $("hint").textContent = "AI will sort matches vs rejected.";
  } finally {
    runBtn.disabled = false;
  }
}

runBtn.addEventListener("click", runFilter);

$("paste").value = `Looking for a React developer for our startup, remote, start next week. Budget negotiable.
https://www.linkedin.com/posts/example-react-hire

Anyone selling Instagram followers cheap? Easy money guaranteed.
https://www.linkedin.com/posts/example-spam

Need someone onsite in Lahore to fix AC unit tomorrow morning.
https://www.linkedin.com/posts/example-ac`;

setPlatform("linkedin");
checkHealth();
