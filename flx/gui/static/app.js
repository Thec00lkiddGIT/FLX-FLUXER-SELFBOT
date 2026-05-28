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
  if (s.token_ok) {
    return `<div class="perm-card ok"><h4>Fluxer token</h4><p>Token is set and the API accepted it when you last started the bot.</p></div>`;
  }
  return `<div class="perm-card bad">
    <h4>Fluxer token</h4>
    <p>Set <code>FLUXER_TOKEN</code> in your config file, then click <strong>Start bot</strong>.</p>
  </div>`;
}

function renderConfigCard(s) {
  const envPath = s.env_path || "";
  const support = s.app_support || "";
  if (!envPath && !support) return "";
  return `<div class="perm-card ok">
    <h4>Config &amp; data</h4>
    <p>Token, prefix, and Script Hub live in Application Support.</p>
    <div class="fda-path-row">
      <input type="text" class="fda-path" readonly value="${escapeHtml(envPath)}" aria-label="Config path" />
      <button type="button" class="btn ghost env-open">Edit config</button>
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
}

function applyStatus(s) {
  const name = s.display_name || "Flx";
  el("display-name").textContent = name;
  el("profile-name").textContent = name;
  el("profile-handle").textContent = "@" + (s.handle || "fluxer");
  el("version").textContent = "v" + (s.version || "1.0.8");
  el("user-id").textContent = String(s.user_id ?? "-");
  el("api-url").textContent = s.api_url || "-";
  if (el("prefix-display")) el("prefix-display").textContent = s.prefix || "!";
  el("commands-count").textContent = s.commands_used ?? 0;
  el("messages-count").textContent = s.messages_seen ?? 0;
  el("commands-used-footer").textContent = s.commands_used ?? 0;
  setRing("ring-commands", s.commands_used || 0, 500);
  setRing("ring-messages", s.messages_seen || 0, 5000);

  const av = el("avatar-initials");
  if (av) av.textContent = initials(name);

  const badge = el("status-badge");
  if (s.running) {
    badge.textContent = "Running";
    badge.className = "badge running";
  } else {
    badge.textContent = "Stopped";
    badge.className = "badge muted";
  }

  const tokenBadge = el("token-badge");
  if (s.token_ok) {
    tokenBadge.textContent = "Token OK";
    tokenBadge.className = "badge";
  } else {
    tokenBadge.textContent = "No token";
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
      msg = "Add FLUXER_TOKEN in Settings -> Edit config, then Start bot.";
    } else if (s.error) {
      msg = s.error;
    } else if (!s.running) {
      msg = "Bot is stopped. Click Start bot to connect to Fluxer.";
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
    const p = s.prefix || "!";
    cmdList.innerHTML = s.commands
      .map((c) => {
        const tag =
          c.source === "hub"
            ? `<span class="cmd-tag${c.enabled === false ? " off" : ""}">hub</span>`
            : "";
        return `<li><div><code>${escapeHtml(p)}${escapeHtml(c.name)}</code><span class="muted">${escapeHtml(c.help)}</span></div>${tag}</li>`;
      })
      .join("");
  }

  const perms = el("perm-cards");
  if (perms) {
    perms.innerHTML = renderTokenCard(s) + renderConfigCard(s);
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
      el("page-" + btn.dataset.page)?.classList.add("active");
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
    "script-code",
    "script-test-args",
  ];
  ids.forEach((id) => {
    const node = el(id);
    if (node) node.readOnly = readonly;
  });
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

function loadScriptIntoEditor(script) {
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
  el("script-code").value = script?.code || "";
  el("script-test-out").textContent = "";
  setScriptStatus("");
  markHubSaved();
  updateHubEditorChrome(script);
  document.querySelectorAll("#hub-script-list button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.id === activeScriptId);
  });
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

  const emptyMine = "No scripts installed. Use Community -> Add to Script Hub, or New script.";
  const emptyCommunity = "No community scripts yet.";
  const emptySearch = "No scripts match your search.";

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
      if (script) loadScriptIntoEditor(script);
    });
  });
}

function setHubTab(tab) {
  hubTab = tab === "community" ? "community" : "mine";
  activeScriptId = "";
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
  setCommunityEditorReadonly(hubTab === "community" && communityReadonly);
  renderHubList();
  const scripts = currentHubList();
  if (scripts.length) {
    loadScriptIntoEditor(scripts[0]);
  } else {
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

async function refreshScripts() {
  try {
    const data = await api("/api/scripts");
    hubScripts = data.scripts || [];
    if (hubTab === "mine") {
      renderHubList();
      if (activeScriptId) {
        const current = hubScripts.find((s) => s.id === activeScriptId);
        if (current) loadScriptIntoEditor(current);
      } else if (hubScripts.length) {
        loadScriptIntoEditor(hubScripts[0]);
      }
    }
    await refreshStatus();
  } catch (_) {
    setScriptStatus("Could not load Script Hub.", true);
  }
}

async function refreshCommunityScripts() {
  try {
    const data = await api("/api/community/scripts");
    communityScripts = data.scripts || [];
    if (data.readonly !== undefined) setCommunityEditorReadonly(!!data.readonly);
    if (hubTab === "community") {
      renderHubList();
      if (activeScriptId) {
        const current = communityScripts.find((s) => s.id === activeScriptId);
        if (current) loadScriptIntoEditor(current);
      } else if (communityScripts.length) {
        loadScriptIntoEditor(communityScripts[0]);
      }
    }
  } catch (_) {
    setScriptStatus("Could not load community scripts.", true);
  }
}

async function postScript(body) {
  const data = await api("/api/scripts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!data.ok) throw new Error(data.error || "Request failed");
  return data;
}

async function postCommunity(body) {
  const data = await api("/api/community/scripts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!data.ok) throw new Error(data.error || "Request failed");
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
      const tpl = await api("/api/scripts/template?name=My+Script");
      activeScriptId = "";
      loadScriptIntoEditor(tpl);
      renderHubList();
      setScriptStatus("New script ready - edit and save.");
    } catch (_) {
      setScriptStatus("Could not load template.", true);
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
      setScriptStatus("Saved to Script Hub.");
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
    if (!activeScriptId) {
      setScriptStatus("Pick a community script first.", true);
      return;
    }
    try {
      await postCommunity({ action: "import", id: activeScriptId });
      setScriptStatus("Added to your Script Hub.");
      await refreshScripts();
      setHubTab("mine");
    } catch (err) {
      setScriptStatus(err.message || String(err), true);
    }
  });

  el("btn-script-delete")?.addEventListener("click", async () => {
    if (!activeScriptId) {
      setScriptStatus("Pick a script to delete.", true);
      return;
    }
    if (!confirm("Delete this script?")) return;
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
      setScriptStatus("Deleted.");
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

setupNav();
setupControls();
setupScriptHub();
refreshStatus();
refreshScripts();
refreshCommunityScripts();
setInterval(refreshStatus, 2000);
setInterval(pollEvents, 800);
