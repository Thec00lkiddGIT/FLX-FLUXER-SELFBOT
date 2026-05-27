import { Client, Events } from "fluxer-selfbot";
import { config } from "./config.js";
import { handleCommand } from "./commands/index.js";

const client = new Client({
  rest: {
    api: config.apiUrl,
    authPrefix: "",
  },
  properties: {
    os: "Windows",
    browser: "Chrome",
    device: "Chrome",
  },
});

client.on(Events.Ready, () => {
  console.log(`Logged in as ${client.user?.username} (${client.user?.id})`);
  console.log(`Prefix: ${config.prefix}  |  API: ${config.apiUrl}`);
});

client.on(Events.MessageCreate, async (message) => {
  if (message.author.id !== client.user?.id) return;
  if (!message.content?.startsWith(config.prefix)) return;
  await handleCommand(client, message);
});

client.on(Events.Error, (err) => {
  console.error("Client error:", err);
});

client.on(Events.Debug, (info) => {
  if (process.env.DEBUG) console.debug("[fluxer]", info);
});

console.log("Connecting to Fluxer…");
await client.login(config.token);
