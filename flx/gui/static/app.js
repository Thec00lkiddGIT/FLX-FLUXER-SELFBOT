const API = "";
let lastEventId = 0;
let activeScriptId = "";
let hubScripts = [];
let communityScripts = [];
let hubTab = "mine";
let hubSearchQuery = "";
let hubDirty = false;
let hubSavedSnapshot = "";
let communityReadonly = true;
let isIos = false;

const PAGE_CHROME = {
  dashboard: { title: "Overview", sub: "Account & bot status" },
  commands: { title: "Commands", sub: "Built-ins and Script Hub" },
  scripts: { title: "Script Hub", sub: "Custom Python commands" },
  assistant: { title: "FLX Assistant", sub: "Local Llama via Ollama" },
  perms: { title: "Settings", sub: "Token, files & options" },
};

const CMD_CATEGORIES = [
  { id: "general", label: "General", hint: "" },
  { id: "mod", label: "Mod", hint: "Server moderation — you need permission on Fluxer." },
  { id: "abuse", label: "Abuse", hint: "Enable with !abuse and confirm in FLX first." },
  { id: "hub", label: "Script Hub", hint: "Your installed hub scripts." },
];

function el(id) {
  return document.getElementById(id);
}

function initials(name) {
  return (name || "FX")
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function timeAgo(iso) {
  const t = new Date(iso).getTime();
  const sec = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (sec < 60) return `${sec} seconds ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} minute${min === 1 ? "" : "s"} ago`;
  const hr = Math.floor(min / 60);
  return `${hr} hour${hr === 1 ? "" : "s"} ago`;
}

function setRing(id, value, max) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  const ring = el(id);
  if (!ring) return;
  const fg = ring.querySelector(".fg");
  if (fg) fg.setAttribute("stroke-dasharray", `${pct}, 100`);
}

async function api(path, options) {
  const res = await fetch(API + path, options);
  const data = await res.json();
  if (!res.ok && data && data.error) {
    throw new Error(data.error);
  }
  return data;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function renderEvent(ev) {
  const card = document.createElement("article");
  card.className = `notify-card ${ev.kind}`;
  card.dataset.id = ev.id;
  card.innerHTML = `
    <h4>${escapeHtml(ev.title)}</h4>
    <p>${escapeHtml(ev.body)}</p>
    <div class="notify-meta">
      <span>${escapeHtml(ev.source)}</span>
      <span>${timeAgo(ev.ts)}</span>
    </div>
  `;
  return card;
}

function prependEvents(events) {
  const list = el("notify-list");
  if (!list || !events.length) return;
  const existing = new Set(
    [...list.querySelectorAll(".notify-card")].map((n) => n.dataset.id)
  );
  for (const ev of events) {
    if (existing.has(String(ev.id))) continue;
    list.prepend(renderEvent(ev));
    lastEventId = Math.max(lastEventId, ev.id);
  }
  while (list.children.length > 40) {
    list.removeChild(list.lastChild);
  }
}

async function pollEvents() {
  try {
    const data = await api(`/api/events?after=${lastEventId}`);
    prependEvents(data.events || []);
  } catch (_) {
    /* server down */
  }
}

function copyText(text) {
  if (navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(text);
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
  return Promise.resolve();
}

function renderTokenCard(s) {
  const enterBtn = `<button type="button" class="btn primary token-enter">Enter token</button>`;
  if (s.token_ok) {
    return `<div class="perm-card ok">
      <h4>Fluxer token</h4>
      <p>You're logged in — FLX checked your token the last time you started the bot.</p>
      <div class="perm-actions">${enterBtn.replace("Enter token", "Change token")}</div>
    </div>`;
  }
  return `<div class="perm-card bad">
    <h4>Fluxer token</h4>
    <p>Paste your Fluxer token to connect. On iPhone you can also edit <code>config.env</code> in the Files app.</p>
    <div class="perm-actions">${enterBtn}</div>
  </div>`;
}

function renderFilesCard(s) {
  if (s.platform !== "ios") return "";
  const folder = s.app_support || "Documents/Flx";
  return `<div class="perm-card ok">
    <h4>Files on iPhone</h4>
    <p>Your config and scripts live here. Open them in Apple's Files app:</p>
    <ol class="fda-step-list">
      <li>Open <strong>Files</strong></li>
      <li>Tap <strong>On My iPhone</strong></li>
      <li>Open <strong>FLX</strong> → <strong>Flx</strong></li>
    </ol>
    <p class="muted small-path">Folder: ${escapeHtml(folder)}</p>
    <p class="muted small-path">Edit <code>config.env</code> in Files, or use <strong>Enter token</strong> above.</p>
  </div>`;
}

function renderConfigCard(s) {
  const envPath = s.env_path || "";
  const support = s.app_support || "";
  if (!envPath && !support) return "";
  const editBtn = s.platform === "ios"
    ? ""
    : `<button type="button" class="btn ghost env-open">Edit config</button>`;
  return `<div class="perm-card ok">
    <h4>Config &amp; data</h4>
    <p>Your token, prefix, and scripts all live in this folder.</p>
    <div class="fda-path-row">
      <input type="text" class="fda-path" readonly value="${escapeHtml(envPath)}" aria-label="Config path" />
      ${editBtn}
      <button type="button" class="btn ghost env-copy" data-path="${escapeHtml(envPath)}">Copy path</button>
    </div>
    <p class="muted small-path">${support ? "Folder: " + escapeHtml(support) : ""}</p>
  </div>`;
}

function setupSettingsButtons(root) {
  root.querySelector(".env-open")?.addEventListener("click", async () => {
    await postControl({ action: "open_env" });
  });
  root.querySelector(".env-copy")?.addEventListener("click", async (e) => {
    const path = e.currentTarget.dataset.path || "";
    try {
      await copyText(path);
      e.currentTarget.textContent = "Copied!";
      setTimeout(() => {
        e.currentTarget.textContent = "Copy path";
      }, 1500);
    } catch (_) {
      /* ignore */
    }
  });
  root.querySelectorAll(".token-enter").forEach((btn) => {
    btn.addEventListener("click", () => openTokenModal());
  });
}

function openTokenModal() {
  const modal = el("token-modal");
  const input = el("token-input");
  const err = el("token-modal-error");
  if (!modal || !input) return;
  input.value = "";
  if (err) {
    err.textContent = "";
    err.classList.add("hidden");
  }
  modal.classList.remove("hidden");
  setTimeout(() => input.focus(), 50);
}

function closeTokenModal() {
  el("token-modal")?.classList.add("hidden");
}

function setupTokenModal() {
  el("token-cancel")?.addEventListener("click", closeTokenModal);
  el("token-modal")?.addEventListener("click", (e) => {
    if (e.target === el("token-modal")) closeTokenModal();
  });
  el("token-save")?.addEventListener("click", async () => {
    const input = el("token-input");
    const err = el("token-modal-error");
    const token = (input?.value || "").trim();
    if (!token) {
      if (err) {
        err.textContent = "Paste your token first.";
        err.classList.remove("hidden");
      }
      return;
    }
    try {
      await postControl({ action: "save_token", token });
      closeTokenModal();
    } catch (exc) {
      if (err) {
        err.textContent = exc.message || String(exc);
        err.classList.remove("hidden");
      }
    }
  });
  el("token-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") el("token-save")?.click();
  });
}

function renderCommandList(commands, prefix) {
  const groups = new Map();
  for (const c of commands) {
    const cat = c.source || "general";
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat).push(c);
  }

  let html = "";
  for (const cat of CMD_CATEGORIES) {
    const items = groups.get(cat.id);
    if (!items?.length) continue;
    html += `<section class="cmd-category glass">`;
    html += `<header class="cmd-category-head"><h3>${escapeHtml(cat.label)}</h3>`;
    if (cat.hint) html += `<p class="cmd-category-hint">${escapeHtml(cat.hint)}</p>`;
    html += `</header><ul class="cmd-list">`;
    for (const c of items) {
      let tag = "";
      if (c.source === "hub") {
        tag = `<span class="cmd-tag${c.enabled === false ? " off" : ""}">hub</span>`;
      } else if (c.source === "mod") {
        tag = `<span class="cmd-tag mod">mod</span>`;
      } else if (c.source === "abuse") {
        tag = `<span class="cmd-tag abuse">abuse</span>`;
      }
      html += `<li><div><code>${escapeHtml(prefix)}${escapeHtml(c.name)}</code><span class="muted">${escapeHtml(c.help)}</span></div>${tag}</li>`;
    }
    html += `</ul></section>`;
  }
  return html || `<p class="muted cmd-empty">No commands loaded yet.</p>`;
}

function setTextAll(selector, text) {
  document.querySelectorAll(selector).forEach((node) => {
    node.textContent = text;
  });
}

function applyPlatformChrome(s) {
  const mobile = s.platform === "ios" || s.platform === "android";
  if (mobile !== isIos) {
    isIos = mobile;
    document.body.classList.toggle("ios", mobile);
  }
  document.body.classList.toggle("mobile-shell", mobile);
}

function applyStatus(s) {
  applyPlatformChrome(s);
  const name = s.display_name || "Flx";
  el("display-name").textContent = name;
  el("profile-name").textContent = name;
  el("profile-handle").textContent = "@" + (s.handle || "fluxer");
  el("version").textContent = "v" + (s.version || "1.1.2");
  if (el("sidebar-version")) el("sidebar-version").textContent = "v" + (s.version || "1.1.2");
  el("user-id").textContent = String(s.user_id ?? "-");
  el("api-url").textContent = s.api_url || "-";
  const prefix = s.prefix || "!";
  if (el("prefix-display")) el("prefix-display").textContent = prefix;
  setTextAll(".js-prefix", prefix);
  if (el("cmd-prefix-label")) el("cmd-prefix-label").textContent = prefix;
  const cmdUsed = s.commands_used ?? 0;
  const msgSeen = s.messages_seen ?? 0;
  if (el("commands-count")) el("commands-count").textContent = cmdUsed;
  if (el("messages-count")) el("messages-count").textContent = msgSeen;
  setTextAll(".js-commands-count", String(cmdUsed));
  setTextAll(".js-messages-count", String(msgSeen));
  el("commands-used-footer").textContent = cmdUsed;
  setRing("ring-commands", s.commands_used || 0, 500);
  setRing("ring-messages", s.messages_seen || 0, 5000);

  const av = el("avatar-initials");
  if (av) av.textContent = initials(name);

  const badge = el("status-badge");
  const topPill = el("topbar-status-pill");
  if (s.running) {
    badge.textContent = "Running";
    badge.className = "badge running";
    if (topPill) {
      topPill.textContent = "Running";
      topPill.className = "topbar-pill running";
    }
  } else {
    badge.textContent = "Stopped";
    badge.className = "badge muted";
    if (topPill) {
      topPill.textContent = "Stopped";
      topPill.className = "topbar-pill";
    }
  }

  const tokenBadge = el("token-badge");
  if (s.token_ok) {
    tokenBadge.textContent = "Logged in";
    tokenBadge.className = "badge";
  } else {
    tokenBadge.textContent = "No token yet";
    tokenBadge.className = "badge bad";
  }

  el("btn-start").disabled = !!s.running;
  el("btn-stop").disabled = !s.running;
  el("toggle-delete-cmd").checked = !!s.delete_commands;
  el("toggle-verbose").checked = !!s.verbose;

  const banner = el("alert-banner");
  if (banner) {
    let msg = "";
    let kind = "error";
    if (!s.token_ok) {
      msg = isIos
        ? "Tap Settings → Enter token, then press Start bot."
        : "Pop your Fluxer token into Settings → Enter token, then press Start bot.";
    } else if (s.error) {
      msg = s.error;
    } else if (!s.running) {
      msg = "FLX is asleep. Hit Start bot when you're ready to connect.";
      kind = "warn";
    }
    if (msg) {
      banner.textContent = msg;
      banner.className = "alert-banner " + kind;
    } else {
      banner.className = "alert-banner hidden";
    }
  }

  const cmdList = el("cmd-list");
  if (cmdList && s.commands) {
    cmdList.innerHTML = renderCommandList(s.commands, s.prefix || "!");
  }

  const perms = el("perm-cards");
  if (perms) {
    perms.innerHTML = renderTokenCard(s) + renderFilesCard(s) + renderConfigCard(s);
    setupSettingsButtons(perms);
  }

  const abuseModal = el("abuse-modal");
  const abuseText = el("abuse-modal-text");
  if (abuseText && s.abuse_warning) abuseText.textContent = s.abuse_warning;
  if (abuseModal) {
    if (s.abuse_pending_confirm) abuseModal.classList.remove("hidden");
    else abuseModal.classList.add("hidden");
  }
}

async function refreshStatus() {
  try {
    const s = await api("/api/status");
    applyStatus(s);
  } catch (_) {
    /* ignore */
  }
}

async function postControl(body) {
  await api("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await refreshStatus();
}

function setupNav() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const page = btn.dataset.page;
      el("page-" + page)?.classList.add("active");
      const chrome = PAGE_CHROME[page];
      if (chrome) {
        if (el("topbar-title")) el("topbar-title").textContent = chrome.title;
        if (el("topbar-sub")) el("topbar-sub").textContent = chrome.sub;
      }
    });
  });
}

function setupAbuseModal() {
  el("abuse-confirm")?.addEventListener("click", async () => {
    await postControl({ action: "abuse_confirm" });
    el("abuse-modal")?.classList.add("hidden");
  });
  el("abuse-cancel")?.addEventListener("click", async () => {
    await postControl({ action: "abuse_cancel" });
    el("abuse-modal")?.classList.add("hidden");
  });
}

function setupControls() {
  el("btn-start")?.addEventListener("click", () => postControl({ action: "start" }));
  el("btn-stop")?.addEventListener("click", () => postControl({ action: "stop" }));
  setupAbuseModal();

  const bindToggle = (id, key) => {
    el(id)?.addEventListener("change", (e) => {
      postControl({ action: "settings", [key]: e.target.checked });
    });
  };
  bindToggle("toggle-delete-cmd", "delete_commands");
  bindToggle("toggle-verbose", "verbose");
}

function hubEditorSnapshot() {
  return JSON.stringify({
    id: activeScriptId,
    name: el("script-name")?.value || "",
    author: el("script-author")?.value || "",
    description: el("script-description")?.value || "",
    usage: el("script-usage")?.value || "",
    command: el("script-command")?.value || "",
    submitted_by: el("script-submitted-by")?.value || "",
    enabled: el("script-enabled")?.checked,
    code: el("script-code")?.value || "",
  });
}

function markHubSaved() {
  hubSavedSnapshot = hubEditorSnapshot();
  hubDirty = false;
  el("hub-unsaved")?.classList.add("hidden");
}

function markHubDirty() {
  if (hubTab === "community" && communityReadonly) return;
  if (hubEditorSnapshot() === hubSavedSnapshot) return;
  hubDirty = true;
  el("hub-unsaved")?.classList.remove("hidden");
}

function setCommunityEditorReadonly(readonly) {
  communityReadonly = readonly;
  const ids = [
    "script-name",
    "script-author",
    "script-description",
    "script-usage",
    "script-command",
    "script-submitted-by",
    "script-test-args",
  ];
  ids.forEach((id) => {
    const node = el(id);
    if (node) node.readOnly = readonly;
  });
  const codeEl = el("script-code");
  if (codeEl) {
    // WebKit/pywebview often hides textarea content when readOnly is set.
    codeEl.readOnly = false;
    codeEl.disabled = false;
    codeEl.classList.toggle("hub-code-viewonly", readonly);
  }
  el("btn-script-test")?.classList.toggle("hidden", readonly && hubTab === "community");
  if (readonly && hubTab === "community") {
    hubDirty = false;
    el("hub-unsaved")?.classList.add("hidden");
  }
}

function setScriptStatus(msg, isError) {
  const node = el("script-status");
  if (!node) return;
  node.textContent = msg || "";
  node.classList.remove("ok", "err");
  if (!msg) return;
  node.classList.add(isError ? "err" : "ok");
}

function syncHubLineNumbers() {
  const code = el("script-code");
  const nums = el("hub-line-nums");
  if (!code || !nums) return;
  const lines = Math.max(1, (code.value.match(/\n/g) || []).length + 1);
  nums.textContent = Array.from({ length: lines }, (_, i) => i + 1).join("\n");
  const meta = el("hub-code-meta");
  if (meta) meta.textContent = `${lines} line${lines === 1 ? "" : "s"}`;
}

function updateHubEditorChrome(script) {
  const title = el("hub-editor-title");
  const cmdBadge = el("hub-editor-cmd");
  const name = (script?.name || script?.command || "").trim();
  if (title) {
    title.textContent = name || (activeScriptId ? "Untitled script" : "Select a script");
  }
  if (cmdBadge) {
    const cmd = (script?.command || el("script-command")?.value || "").trim();
    cmdBadge.textContent = cmd ? `!${cmd}` : "";
  }
  syncHubLineNumbers();
}

function applyScriptToEditorFields(script) {
  activeScriptId = script?.id || "";
  el("script-name").value = script?.name || "";
  el("script-author").value =
    script?.author || (hubTab === "community" ? "c00lkiddtech" : "Flx");
  el("script-description").value = script?.description || script?.help || "";
  el("script-usage").value =
    script?.usage || (script?.command ? "<p>" + script.command + " <args>" : "");
  el("script-command").value = script?.command || "";
  el("script-enabled").checked = script?.enabled !== false;
  if (el("script-submitted-by")) {
    el("script-submitted-by").value = script?.submitted_by || "";
  }
  const codeEl = el("script-code");
  const body = script?.code || "";
  if (hubTab === "community" && communityReadonly) {
    setCommunityEditorReadonly(true);
  } else {
    setCommunityEditorReadonly(false);
  }
  if (codeEl) {
    codeEl.value = body;
    codeEl.scrollTop = 0;
  }
  el("script-test-out").textContent = "";
  setScriptStatus("");
  syncHubLineNumbers();
  markHubSaved();
  updateHubEditorChrome(script);
  document.querySelectorAll("#hub-script-list button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.id === activeScriptId);
  });
}

function loadScriptIntoEditor(script) {
  applyScriptToEditorFields(script);
}

async function fetchCommunityScriptById(scriptId) {
  const data = await api(
    `/api/community/scripts?id=${encodeURIComponent(scriptId)}`
  );
  return data.script || null;
}

async function fetchPersonalScriptById(scriptId) {
  const data = await api(`/api/scripts?id=${encodeURIComponent(scriptId)}`);
  return data.script || null;
}

async function loadCommunityScriptIntoEditor(script) {
  if (!script?.id) {
    loadScriptIntoEditor(script);
    return;
  }
  let full = script;
  try {
    const loaded = await fetchCommunityScriptById(script.id);
    if (loaded) {
      full = { ...script, ...loaded };
      const idx = communityScripts.findIndex((s) => s.id === script.id);
      if (idx >= 0) communityScripts[idx] = { ...communityScripts[idx], ...full };
    }
  } catch (_) {
    /* keep partial script */
  }
  applyScriptToEditorFields(full);
  if (!(full.code || "").trim()) {
    setScriptStatus("Couldn't load script source — try another script.", true);
  }
}

async function loadPersonalScriptIntoEditor(script) {
  if (!script?.id) {
    loadScriptIntoEditor(script);
    return;
  }
  let full = script;
  if (!(full.code || "").trim()) {
    try {
      const loaded = await fetchPersonalScriptById(script.id);
      if (loaded) full = { ...script, ...loaded };
    } catch (_) {
      /* keep partial */
    }
  }
  applyScriptToEditorFields(full);
}

function filteredHubScripts(scripts) {
  const q = hubSearchQuery.trim().toLowerCase();
  if (!q) return scripts;
  return scripts.filter((s) => {
    const hay = [
      s.name,
      s.command,
      s.author,
      s.description,
      s.help,
      s.submitted_by,
      ...(s.commands || []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });
}

function currentHubList() {
  return hubTab === "community" ? communityScripts : hubScripts;
}

function renderHubList() {
  const list = el("hub-script-list");
  const countNode = el("hub-list-count");
  if (!list) return;
  const all = currentHubList();
  const scripts = filteredHubScripts(all);
  if (countNode) countNode.textContent = String(all.length);

  const emptyMine = "Nothing here yet — grab something from Community, or start a new script.";
  const emptyCommunity = "No community scripts loaded right now.";
  const emptySearch = "Nothing matched that search.";

  if (!all.length) {
    list.innerHTML = `<li class="muted hub-empty">${hubTab === "community" ? emptyCommunity : emptyMine}</li>`;
    return;
  }
  if (!scripts.length) {
    list.innerHTML = `<li class="muted hub-empty">${emptySearch}</li>`;
    return;
  }

  list.innerHTML = scripts
    .map((s) => {
      const cmd = s.command || (s.commands && s.commands[0]) || "";
      const cmdClass = hubTab === "mine" && !s.enabled ? "hub-item-cmd off" : "hub-item-cmd";
      const authorLine =
        hubTab === "community" && s.author
          ? `<span class="hub-item-sub">by ${escapeHtml(s.author)}</span>`
          : "";
      return `<li><button type="button" data-id="${escapeHtml(s.id)}" class="${s.id === activeScriptId ? "active" : ""}">
          <span class="hub-item-row">
            <span class="hub-item-name">${escapeHtml(s.name || cmd || "Script")}</span>
            ${cmd ? `<span class="${cmdClass}">!${escapeHtml(cmd)}</span>` : ""}
          </span>
          <span class="hub-item-help">${escapeHtml(s.description || s.help || "")}</span>
          ${authorLine}
        </button></li>`;
    })
    .join("");
  list.querySelectorAll("button[data-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const script = all.find((s) => s.id === btn.dataset.id);
      if (!script) return;
      if (hubTab === "community") loadCommunityScriptIntoEditor(script);
      else loadPersonalScriptIntoEditor(script);
    });
  });
}

function applyHubTabChrome(tab) {
  hubTab = tab === "community" ? "community" : "mine";
  document.querySelectorAll(".hub-tab").forEach((btn) => {
    const on = btn.dataset.hubTab === hubTab;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
  el("hub-list-title").textContent = hubTab === "community" ? "Community" : "My scripts";
  el("community-tab-hint")?.classList.toggle("hidden", hubTab !== "community");
  el("btn-script-new")?.classList.toggle("hidden", hubTab !== "mine");
  el("btn-script-save")?.classList.toggle("hidden", hubTab !== "mine");
  el("btn-script-delete")?.classList.toggle("hidden", hubTab !== "mine");
  el("btn-community-import")?.classList.toggle("hidden", hubTab !== "community");
  el("script-submitted-wrap")?.classList.toggle("hidden", hubTab !== "community");
  el("hub-enable-wrap")?.classList.toggle("hidden", hubTab === "community");
}

function upsertHubScript(script) {
  if (!script?.id) return;
  const idx = hubScripts.findIndex((s) => s.id === script.id);
  if (idx >= 0) hubScripts[idx] = script;
  else hubScripts.push(script);
}

async function showScriptInMine(script) {
  if (!script) return;
  upsertHubScript(script);
  applyHubTabChrome("mine");
  await loadPersonalScriptIntoEditor(script);
  renderHubList();
}

function setHubTab(tab, selectScriptId = null) {
  applyHubTabChrome(tab);
  renderHubList();
  const list = currentHubList();
  if (selectScriptId) {
    const picked = list.find((s) => s.id === selectScriptId);
    if (picked) {
      if (hubTab === "community") loadCommunityScriptIntoEditor(picked);
      else loadPersonalScriptIntoEditor(picked);
      return;
    }
  }
  if (!selectScriptId) activeScriptId = "";
  if (list.length) {
    if (hubTab === "community") loadCommunityScriptIntoEditor(list[0]);
    else loadPersonalScriptIntoEditor(list[0]);
  } else {
    setCommunityEditorReadonly(hubTab === "community" && communityReadonly);
    loadScriptIntoEditor({
      name: "",
      author: hubTab === "community" ? "c00lkiddtech" : "Flx",
      command: "",
      description: "",
      usage: "",
      code: "",
      enabled: true,
      submitted_by: hubTab === "community" ? "c00lkiddtech" : "",
    });
  }
}

async function refreshScripts(opts = {}) {
  const keepId = opts.keepId || null;
  try {
    const data = await api("/api/scripts");
    hubScripts = data.scripts || [];
    if (hubTab === "mine") {
      renderHubList();
      const wantId = keepId || activeScriptId;
      if (wantId) {
        const current = hubScripts.find((s) => s.id === wantId);
        if (current) {
          await loadPersonalScriptIntoEditor(current);
          return;
        }
      }
      if (hubScripts.length) {
        await loadPersonalScriptIntoEditor(hubScripts[0]);
      }
    }
    await refreshStatus();
  } catch (_) {
    if (!keepId) {
      setScriptStatus("Couldn't load your scripts — try refreshing.", true);
    }
  }
}

async function refreshCommunityScripts() {
  try {
    const data = await api("/api/community/scripts");
    communityScripts = data.scripts || [];
    if (data.readonly !== undefined) communityReadonly = !!data.readonly;
    if (hubTab === "community") {
      renderHubList();
      if (activeScriptId) {
        const current = communityScripts.find((s) => s.id === activeScriptId);
        if (current) await loadCommunityScriptIntoEditor(current);
      } else if (communityScripts.length) {
        await loadCommunityScriptIntoEditor(communityScripts[0]);
      } else {
        setCommunityEditorReadonly(communityReadonly);
      }
    }
  } catch (_) {
    setScriptStatus("Couldn't load community scripts — try again in a sec.", true);
  }
}

async function postScript(body) {
  const data = await api("/api/scripts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!data.ok) throw new Error(data.error || "Something went wrong — try again.");
  return data;
}

async function postCommunity(body) {
  const data = await api("/api/community/scripts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!data.ok) throw new Error(data.error || "Something went wrong — try again.");
  return data;
}

function setupHubEditorInputs() {
  const watchIds = [
    "script-name",
    "script-author",
    "script-description",
    "script-usage",
    "script-command",
    "script-submitted-by",
    "script-code",
  ];
  watchIds.forEach((id) => {
    const node = el(id);
    if (!node) return;
    node.addEventListener("input", () => {
      markHubDirty();
      updateHubEditorChrome({
        name: el("script-name")?.value,
        command: el("script-command")?.value,
      });
      if (id === "script-code") syncHubLineNumbers();
    });
  });

  el("script-enabled")?.addEventListener("change", () => markHubDirty());

  const code = el("script-code");
  const nums = el("hub-line-nums");
  if (code && nums) {
    code.addEventListener("scroll", () => {
      nums.scrollTop = code.scrollTop;
    });
  }

  el("hub-search")?.addEventListener("input", (e) => {
    hubSearchQuery = e.target.value;
    renderHubList();
  });
}

function setupScriptHub() {
  setupHubEditorInputs();

  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "s") {
      const page = document.querySelector("#page-scripts.active");
      if (!page) return;
      e.preventDefault();
      if (hubTab !== "community") el("btn-script-save")?.click();
    }
  });

  document.querySelectorAll(".hub-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.hubTab;
      if (tab === hubTab) return;
      setHubTab(tab);
      if (tab === "community") refreshCommunityScripts();
      else refreshScripts();
    });
  });

  el("btn-script-new")?.addEventListener("click", async () => {
    try {
      const data = await postScript({
        action: "create",
        name: "My Script",
        author: "Flx",
        command: "mycommand",
        description: "My custom command",
      });
      const script = data.script;
      if (!script?.id) {
        throw new Error("Script was created but no id came back.");
      }
      activeScriptId = script.id;
      loadScriptIntoEditor(script);
      markHubSaved();
      renderHubList();
      await refreshScripts({ keepId: script.id });
      setScriptStatus(`Created ${script.id}.py — edit and save anytime.`);
    } catch (err) {
      setScriptStatus(err.message || "Couldn't create script.", true);
    }
  });

  el("btn-script-save")?.addEventListener("click", async () => {
    try {
      const data = await postScript({
        action: "save",
        id: activeScriptId || undefined,
        name: el("script-name").value,
        author: el("script-author").value,
        description: el("script-description").value,
        usage: el("script-usage").value,
        command: el("script-command").value,
        help: el("script-description").value,
        code: el("script-code").value,
        enabled: el("script-enabled").checked,
      });
      activeScriptId = data.script?.id || activeScriptId;
      markHubSaved();
      setScriptStatus("Saved!");
      await refreshScripts();
    } catch (err) {
      setScriptStatus(err.message || String(err), true);
    }
  });

  el("btn-script-test")?.addEventListener("click", async () => {
    el("script-test-out").textContent = "…";
    try {
      const payload = {
        action: "test",
        command: el("script-command").value,
        code: el("script-code").value,
        args: el("script-test-args").value,
      };
      if (hubTab === "mine") payload.id = activeScriptId || undefined;
      const data =
        hubTab === "community" ? await postCommunity(payload) : await postScript(payload);
      const r = data.result;
      el("script-test-out").textContent = Array.isArray(r) ? r.join(" | ") : String(r);
      setScriptStatus("");
    } catch (err) {
      el("script-test-out").textContent = "";
      setScriptStatus(err.message || String(err), true);
    }
  });

  el("btn-community-import")?.addEventListener("click", async () => {
    const communityId = activeScriptId;
    if (!communityId) {
      setScriptStatus("Choose a community script from the list first.", true);
      return;
    }
    const btn = el("btn-community-import");
    if (btn) btn.disabled = true;
    try {
      const source = await fetchCommunityScriptById(communityId);
      if (!source?.code?.trim()) {
        throw new Error("Couldn't read script source — try picking the script again.");
      }
      const data = await postCommunity({
        action: "import",
        id: communityId,
        code: source.code,
      });
      const imported = data.script;
      if (!imported?.id) {
        throw new Error("Import worked but no script came back — weird.");
      }
      if (!imported.code?.trim()) {
        imported.code = source.code;
      }
      let mine = imported;
      try {
        const loaded = await fetchPersonalScriptById(imported.id);
        if (loaded?.code?.trim()) mine = { ...imported, ...loaded };
      } catch (_) {
        /* use import payload */
      }
      await showScriptInMine(mine);
      setScriptStatus("Added to My scripts — you're looking at it now.");
      await refreshScripts({ keepId: mine.id });
    } catch (err) {
      setScriptStatus(err.message || String(err), true);
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  el("btn-script-delete")?.addEventListener("click", async () => {
    if (!activeScriptId) {
      setScriptStatus("Select a script first.", true);
      return;
    }
    if (!confirm("Delete this script for good?")) return;
    try {
      await postScript({ action: "delete", id: activeScriptId });
      activeScriptId = "";
      loadScriptIntoEditor({
        name: "",
        author: "Flx",
        command: "",
        description: "",
        usage: "",
        code: "",
        enabled: true,
      });
      setScriptStatus("Gone.");
      await refreshScripts();
    } catch (err) {
      setScriptStatus(err.message || String(err), true);
    }
  });

  el("script-enabled")?.addEventListener("change", async () => {
    if (!activeScriptId || hubTab !== "mine") return;
    try {
      await postScript({
        action: "toggle",
        id: activeScriptId,
        enabled: el("script-enabled").checked,
      });
      await refreshScripts();
    } catch (err) {
      setScriptStatus(err.message || String(err), true);
    }
  });

  setHubTab("mine");
}

let assistantHistory = [];
let pendingAssistantCode = null;
let pendingAssistantMeta = null;

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function formatAssistantReply(text) {
  const parts = [];
  const re = /```(?:python)?\s*\n([\s\S]*?)```/gi;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      parts.push({ type: "text", value: text.slice(last, m.index) });
    }
    parts.push({ type: "code", value: m[1].trim() });
    last = re.lastIndex;
  }
  if (last < text.length) {
    parts.push({ type: "text", value: text.slice(last) });
  }
  if (!parts.length) {
    parts.push({ type: "text", value: text });
  }
  return parts
    .map((p) => {
      if (p.type === "code") {
        return `<pre><code>${escapeHtml(p.value)}</code></pre>`;
      }
      const t = escapeHtml(p.value).replace(/\n/g, "<br>");
      return `<p>${t}</p>`;
    })
    .join("");
}

function appendAssistantMessage(role, content, html) {
  const box = el("assistant-messages");
  if (!box) return;
  const div = document.createElement("div");
  div.className =
    "assistant-msg " + (role === "user" ? "assistant-msg-user" : "assistant-msg-bot");
  if (html) {
    div.innerHTML = html;
  } else {
    const p = document.createElement("p");
    p.textContent = content;
    div.appendChild(p);
  }
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

async function refreshAssistantStatus() {
  const dot = el("assistant-dot");
  const text = el("assistant-status-text");
  const mobileNote = el("assistant-mobile-note");
  try {
    const st = await api("/api/assistant/status");
    if (mobileNote) {
      mobileNote.classList.toggle(
        "hidden",
        !(st.mobile && (st.remote_required || !st.ok))
      );
      if (st.remote_required) {
        mobileNote.innerHTML =
          "<p><strong>Mobile setup:</strong> FLX AI runs on your Mac, not on the phone. " +
          "Open Ollama on the Mac, turn on network access, then add " +
          "<code>OLLAMA_BASE_URL=http://YOUR_MAC_IP:11434</code> to " +
          "<code>config.env</code> (Files → FLX → Flx).</p>";
      } else if (st.mobile && !st.ok) {
        mobileNote.innerHTML =
          `<p class="muted">${escapeHtml(st.error || "Cannot reach Ollama on your Mac.")}</p>`;
      }
    }
    if (st.ok) {
      dot?.classList.add("ok");
      dot?.classList.remove("err");
      const model = st.model || "llama";
      const tag = st.bundled ? "bundled · " : "";
      text.textContent = st.warning ? st.warning : `${tag}Ollama · ${model}`;
    } else if (st.remote_required) {
      dot?.classList.add("err");
      dot?.classList.remove("ok");
      text.textContent = "Set OLLAMA_BASE_URL to your Mac";
    } else if (st.starting || st.bundled) {
      dot?.classList.remove("ok");
      dot?.classList.remove("err");
      text.textContent = st.error || "Starting bundled Ollama…";
    } else {
      dot?.classList.add("err");
      dot?.classList.remove("ok");
      text.textContent = st.error || "Ollama offline";
    }
  } catch (err) {
    dot?.classList.add("err");
    text.textContent = err.message || "Status error";
  }
}

async function sendAssistantMessage() {
  const input = el("assistant-input");
  const sendBtn = el("assistant-send");
  const msg = (input?.value || "").trim();
  if (!msg) return;
  appendAssistantMessage("user", msg);
  assistantHistory.push({ role: "user", content: msg });
  if (input) input.value = "";
  if (sendBtn) sendBtn.disabled = true;
  try {
    const data = await api("/api/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, history: assistantHistory.slice(0, -1) }),
    });
    const reply = data.reply || "";
    assistantHistory.push({ role: "assistant", content: reply });
    appendAssistantMessage("assistant", reply, formatAssistantReply(reply));
    if (data.script_code) {
      pendingAssistantCode = data.script_code;
      pendingAssistantMeta = data.script_meta || {};
      el("assistant-script-bar")?.classList.remove("hidden");
    }
  } catch (err) {
    appendAssistantMessage("assistant", err.message || String(err));
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    input?.focus();
  }
}

async function saveAssistantScript() {
  if (!pendingAssistantCode) return;
  const meta = pendingAssistantMeta || {};
  try {
    const saved = await postScript({
      action: "save",
      name: meta.name || "AI Script",
      author: meta.author || "FLX Assistant",
      description: meta.description || "Generated by FLX Assistant",
      usage: meta.usage || "<p>mycommand <args>",
      command: meta.command || "mycommand",
      help: meta.description || "Generated by FLX Assistant",
      code: pendingAssistantCode,
      enabled: true,
    });
    appendAssistantMessage(
      "assistant",
      `Saved to Script Hub as "${saved.script?.name || meta.name}". Open My scripts to test it.`
    );
    await refreshScripts();
  } catch (err) {
    appendAssistantMessage("assistant", err.message || String(err));
  }
}

function setupAssistant() {
  el("assistant-send")?.addEventListener("click", () => sendAssistantMessage());
  el("assistant-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendAssistantMessage();
    }
  });
  el("assistant-clear")?.addEventListener("click", () => {
    assistantHistory = [];
    pendingAssistantCode = null;
    pendingAssistantMeta = null;
    el("assistant-script-bar")?.classList.add("hidden");
    const box = el("assistant-messages");
    if (box) {
      box.innerHTML = "";
      appendAssistantMessage(
        "assistant",
        "Chat cleared. Ask for a script or FLX / Fluxer help anytime."
      );
    }
  });
  el("assistant-save-script")?.addEventListener("click", () => saveAssistantScript());
  el("assistant-open-scripts")?.addEventListener("click", () => {
    document.querySelector('.nav-item[data-page="scripts"]')?.click();
  });
  refreshAssistantStatus();
  setInterval(refreshAssistantStatus, 15000);
}

setupNav();
setupControls();
setupTokenModal();
setupAssistant();
setupScriptHub();
(function detectMobileShell() {
  const ua = navigator.userAgent || "";
  const appleMobile =
    /iPad|iPhone|iPod/.test(ua) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const android = /Android/i.test(ua);
  if (appleMobile || android || window.matchMedia("(max-width: 720px)").matches) {
    document.body.classList.add("ios", "mobile-shell");
    isIos = true;
  }
})();
refreshStatus();
refreshScripts();
refreshCommunityScripts();
setInterval(refreshStatus, 2000);
setInterval(pollEvents, 800);
