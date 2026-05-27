import type { Client, Message } from "fluxer-selfbot";
import { config } from "../config.js";

export type CommandContext = {
  client: Client;
  message: Message;
  args: string[];
};

export type Command = {
  name: string;
  description: string;
  aliases?: string[];
  run: (ctx: CommandContext) => Promise<void>;
};

const commands: Command[] = [
  {
    name: "ping",
    description: "Check if the selfbot is online",
    async run({ message }) {
      const start = Date.now();
      const reply = await message.reply("Pinging…");
      const ms = Date.now() - start;
      await reply.edit({ content: `Pong — ${ms}ms` });
    },
  },
  {
    name: "help",
    description: "List available commands",
    aliases: ["h", "commands"],
    async run({ message }) {
      const lines = commands
        .map((c) => `\`${config.prefix}${c.name}\` — ${c.description}`)
        .join("\n");
      await message.reply(`**Commands**\n${lines}`);
    },
  },
  {
    name: "echo",
    description: "Repeat your message",
    async run({ message, args }) {
      const text = args.join(" ").trim();
      if (!text) {
        await message.reply(`Usage: \`${config.prefix}echo <text>\``);
        return;
      }
      await message.reply(text);
    },
  },
  {
    name: "status",
    description: "Set your status (online | idle | dnd | invisible)",
    async run({ client, message, args }) {
      const status = (args[0]?.toLowerCase() ?? "online") as
        | "online"
        | "idle"
        | "dnd"
        | "invisible";

      if (!["online", "idle", "dnd", "invisible"].includes(status)) {
        await message.reply(
          `Usage: \`${config.prefix}status online|idle|dnd|invisible\``,
        );
        return;
      }

      await client.user?.setPresence({ status });
      await message.reply(`Status set to **${status}**`);
    },
  },
  {
    name: "purge",
    description: "Delete your recent messages in this channel",
    aliases: ["clear"],
    async run({ client, message, args }) {
      const limit = Math.min(Math.max(Number(args[0]) || 10, 1), 50);
      const channelId = message.channelId;
      const me = client.user?.id;
      if (!me) return;

      const batch = await client.rest.get<{ id: string; author: { id: string } }[]>(
        `/channels/${channelId}/messages?limit=100`,
      );

      let deleted = 0;
      for (const msg of batch) {
        if (deleted >= limit) break;
        if (msg.author.id !== me) continue;
        try {
          await client.rest.delete(`/channels/${channelId}/messages/${msg.id}`);
          deleted++;
        } catch {
          // skip messages we cannot delete
        }
      }

      const note = await message.reply(`Deleted **${deleted}** of your messages.`);
      setTimeout(() => note.delete().catch(() => {}), 4000);
    },
  },
];

const byName = new Map<string, Command>();
for (const cmd of commands) {
  byName.set(cmd.name, cmd);
  for (const alias of cmd.aliases ?? []) {
    byName.set(alias, cmd);
  }
}

export function parseCommand(content: string): { name: string; args: string[] } | null {
  if (!content.startsWith(config.prefix)) return null;
  const body = content.slice(config.prefix.length).trim();
  if (!body) return null;
  const [name, ...args] = body.split(/\s+/);
  return { name: name.toLowerCase(), args };
}

export async function handleCommand(
  client: Client,
  message: Message,
): Promise<boolean> {
  const parsed = parseCommand(message.content);
  if (!parsed) return false;

  const cmd = byName.get(parsed.name);
  if (!cmd) return false;

  try {
    await cmd.run({ client, message, args: parsed.args });
  } catch (err) {
    console.error(`Command ${cmd.name} failed:`, err);
    await message.reply("That command failed. Check the terminal for details.").catch(() => {});
  }
  return true;
}
