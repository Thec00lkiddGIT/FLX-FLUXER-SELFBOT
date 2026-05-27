const API = "";
let lastEventId = 0;
let activeScriptId = "";
let hubScripts = [];

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
  el("version").textContent = "v" + (s.version || "1.0.0");
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

function setScriptStatus(msg, isError) {
  const node = el("script-status");
  if (!node) return;
  node.textContent = msg || "";
  node.style.color = isError ? "var(--error)" : "";
}

function loadScriptIntoEditor(script) {
  activeScriptId = script?.id || "";
  el("script-name").value = script?.name || "";
  el("script-author").value = script?.author || "Flx";
  el("script-description").value = script?.description || script?.help || "";
  el("script-usage").value = script?.usage || (script?.command ? "<p>" + script.command + " <args>" : "");
  el("script-command").value = script?.command || "";
  el("script-enabled").checked = script?.enabled !== false;
  el("script-code").value = script?.code || "";
  el("script-test-out").textContent = "";
  setScriptStatus("");
  document.querySelectorAll("#hub-script-list button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.id === activeScriptId);
  });
}

function renderHubList() {
  const list = el("hub-script-list");
  if (!list) return;
  if (!hubScripts.length) {
    list.innerHTML =
      '<li class="muted" style="padding:8px">No scripts yet. Click New script.</li>';
    return;
  }
  list.innerHTML = hubScripts
    .map(
      (s) =>
        `<li><button type="button" data-id="${escapeHtml(s.id)}" class="${s.id === activeScriptId ? "active" : ""}">
          <span class="hub-item-name">${escapeHtml(s.name || s.command)}${s.enabled ? "" : " (off)"}</span>
          <span class="hub-item-help">${escapeHtml(s.description || s.help || "")}</span>
        </button></li>`
    )
    .join("");
  list.querySelectorAll("button[data-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const script = hubScripts.find((s) => s.id === btn.dataset.id);
      if (script) loadScriptIntoEditor(script);
    });
  });
}

async function refreshScripts() {
  try {
    const data = await api("/api/scripts");
    hubScripts = data.scripts || [];
    renderHubList();
    if (activeScriptId) {
      const current = hubScripts.find((s) => s.id === activeScriptId);
      if (current) loadScriptIntoEditor(current);
    } else if (hubScripts.length) {
      loadScriptIntoEditor(hubScripts[0]);
    }
    await refreshStatus();
  } catch (_) {
    setScriptStatus("Could not load Script Hub.", true);
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

function setupScriptHub() {
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
      setScriptStatus("Saved to Script Hub.");
      await refreshScripts();
    } catch (err) {
      setScriptStatus(err.message || String(err), true);
    }
  });

  el("btn-script-test")?.addEventListener("click", async () => {
    el("script-test-out").textContent = "…";
    try {
      const data = await postScript({
        action: "test",
        id: activeScriptId || undefined,
        command: el("script-command").value,
        code: el("script-code").value,
        args: el("script-test-args").value,
      });
      const r = data.result;
      el("script-test-out").textContent = Array.isArray(r) ? r.join(" | ") : String(r);
      setScriptStatus("");
    } catch (err) {
      el("script-test-out").textContent = "";
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
    if (!activeScriptId) return;
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
}

setupNav();
setupControls();
setupScriptHub();
refreshStatus();
refreshScripts();
setInterval(refreshStatus, 2000);
setInterval(pollEvents, 800);
