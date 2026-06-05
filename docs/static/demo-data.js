/** Mock API for GitHub Pages (static preview — no Python server). */
(function () {
  const DEMO_COMMANDS = [
    { name: "ping", help: "Returns bot latency (ms)", source: "general" },
    { name: "gay", help: "Random percentage joke", source: "general" },
    { name: "word", help: "Random word (API Ninjas)", source: "general" },
    { name: "dadjoke", help: "Random dad joke", source: "general" },
    { name: "qr", help: "QR code image + caption", source: "general" },
    { name: "youtube", help: "search | video | trans (SerpAPI)", source: "general" },
    { name: "weather", help: "City weather (C99.nl)", source: "general" },
    { name: "bulk", help: "Bulk URL check (up to 3)", source: "general" },
    { name: "osint", help: "OSINT Industries lookup", source: "general" },
    { name: "help", help: "List built-in and hub commands", source: "general" },
    { name: "status", help: "Set presence: online | idle | dnd | invisible", source: "general" },
    { name: "purge", help: "Delete your recent messages in this channel", source: "mod" },
    { name: "poof", help: "Remove image background (attach image, Poof.bg)", source: "general" },
    { name: "screenshot", help: "Screenshot a URL (Microlink)", source: "general" },
    { name: "info", help: "user - profile, avatar, snowflake decode", source: "general" },
    { name: "wb", help: "Webhook send/delete via URL", source: "general" },
    { name: "httpcat", help: "HTTP status cat image", source: "hub", enabled: true },
    { name: "pokemon", help: "Look up a Pokémon", source: "hub", enabled: true },
  ];

  const DEMO_SCRIPTS = [
    {
      id: "httpcat",
      name: "HTTP Cat",
      author: "Flx",
      command: "httpcat",
      description: "Fetch a cat image for an HTTP status code",
      help: "Fetch a cat image for an HTTP status code",
      enabled: true,
      code: "# demo preview",
    },
    {
      id: "pokemon",
      name: "Pokémon",
      author: "Flx",
      command: "pokemon",
      description: "Look up a Pokémon by name",
      help: "Look up a Pokémon by name",
      enabled: true,
      code: "# demo preview",
    },
  ];

  let demoRunning = false;
  let eventId = 2;

  function demoStatus() {
    return {
      running: demoRunning,
      delete_commands: true,
      verbose: true,
      display_name: "c00lkiddtech",
      handle: "c00lkiddtech",
      user_id: "1498795484896895545",
      version: "1.1.3",
      commands_used: 0,
      messages_seen: 0,
      error: null,
      token_ok: true,
      api_url: "https://api.fluxer.app",
      prefix: "!",
      latest_event_id: eventId,
      abuse_mode: false,
      abuse_pending_confirm: false,
      abuse_warning: "",
      platform: "desktop",
      commands: DEMO_COMMANDS,
      env_path: "~/Documents/Flx/config.env",
      app_support: "~/Documents/Flx",
    };
  }

  window.demoApi = async function demoApi(path, options) {
    const method = (options && options.method) || "GET";
    const url = new URL(path, "https://demo.local");

    if (path.startsWith("/api/status") && method === "GET") {
      return demoStatus();
    }

    if (path.startsWith("/api/events") && method === "GET") {
      return { latest_id: eventId, events: [] };
    }

    if (path.startsWith("/api/control") && method === "POST") {
      let body = {};
      try {
        body = JSON.parse((options && options.body) || "{}");
      } catch (_) {
        /* ignore */
      }
      if (body.action === "start") {
        demoRunning = true;
        eventId += 1;
      }
      if (body.action === "stop") {
        demoRunning = false;
        eventId += 1;
      }
      return { ok: true, message: "Demo preview" };
    }

    if (path.startsWith("/api/scripts") && method === "GET") {
      const id = url.searchParams.get("id");
      if (id) {
        const script = DEMO_SCRIPTS.find((s) => s.id === id);
        if (!script) throw new Error("Script not found.");
        return { ok: true, script };
      }
      return { scripts: DEMO_SCRIPTS.map((s) => ({ ...s })) };
    }

    if (path.startsWith("/api/community/scripts") && method === "GET") {
      return { scripts: [], readonly: true };
    }

    if (path.startsWith("/api/assistant/status") && method === "GET") {
      return {
        ok: false,
        error: "Assistant runs locally with Ollama — not on GitHub Pages.",
      };
    }

    if (path.startsWith("/api/assistant/chat") && method === "POST") {
      throw new Error("Assistant is desktop-only in the full FLX app.");
    }

    if (path.startsWith("/api/scripts") && method === "POST") {
      return { ok: true, script: DEMO_SCRIPTS[0] };
    }

    throw new Error("Demo preview — install FLX for full features.");
  };
})();
