# FlxScript guide

*Write your own commands for [Fluxer](https://fluxer.app) with FLX.*

## 1. Overview

**FlxScript** is how you add custom Python commands and listeners. FLX handles talking to Fluxer (`api.fluxer.app` / `gateway.fluxer.app`); your script is just "what should happen when I run `!something` or when a message shows up."

> **IMPORTANT - do not import these:**
> - `import discord` / `from discord import *`
> - `import fluxer` / unofficial Fluxer SDKs inside hub scripts
> - `matplotlib`, `numpy`, `pydub`, or other packages that need `pip install` in the hub
>
> Use the standard library plus FlxScript helpers. Put all docs and requirements in the script docstring.

> **Replies:** Use `ctx.send("...")` with normal markdown (`**bold**`, links, newlines) — same as bundled scripts (echo, httpcat, pokemon). `forwardEmbedMethod()` exists for legacy scripts but **new scripts should not use it**; FLX Assistant will not generate it.

## 2. Script structure

```python
from flx.fluxerscript import flxScript, log

# `bot` is injected automatically - do not import it

@flxScript(
    name="Script Name",
    author="YourName",
    description="What it does",
    usage="<p>mycommand <args>",
)
def script_function():
  @bot.command(name="mycommand", description="Does something")
  def mycommand_handler(ctx, *, args: str):
    ctx.send(f"You said: {args}")
    log("handled mycommand", type_="INFO")

script_function()  # REQUIRED - registers commands
```

| Field | Purpose |
|-------|---------|
| `name` | Display name in Script Hub |
| `author` | Your name |
| `description` | Short summary |
| `usage` | `<p>` = your prefix from config (`!` by default). `[optional]`, `--flags` |

## 2.1 Documentation standards

```python
def script_function():
    """
    MY SCRIPT
    ---------

    Brief description.

    COMMANDS:
    <p>command1 <args> - Does X
    <p>command2 [args] - Does Y

    EXAMPLES:
    <p>command1 hello - Example

    NOTES:
    - Bot must be Running on the dashboard
    """
```

## 3. Command prefix

`<p>` in `usage` means the value of `PREFIX` in `config.env` (default `!`). You type commands **as your user** in Fluxer. Flx strips the prefix; handlers receive only `args`.

## 4. Core API

### 4.1 Config - `getConfigData()`, `updateConfigData()`

```python
value = getConfigData().get("my_key", "default")
updateConfigData("my_key", "new_value")
```

Stored per script in your Flx app data folder (`Flx/scripts/hub/config.json`, namespaced keys). See README for macOS / Windows paths.

### 4.2 JSON storage

```python
from pathlib import Path
import json

BASE_DIR = Path(getScriptsPath()) / "json"
DATA_FILE = BASE_DIR / "my_data.json"
BASE_DIR.mkdir(parents=True, exist_ok=True)
```

### 4.3 Commands - `@bot.command`

```python
@bot.command(name="command", usage="<p>command <arg>", description="Desc", aliases=["c"])
def command_handler(ctx, *, args: str):
    if not args:
        ctx.send("Usage: <p>command <arg>")
        return
    ctx.send("Done!")
```

**`ctx` fields:**

- `ctx.message` - `FlxMessage` (`content`, `channel_id`, `author_id`, …)
- `ctx.send(text)` - queue a reply (Flx sends after the handler returns) — **preferred for all new scripts**
- `ctx.reply_embed(...)` - legacy; prefer `ctx.send()` with markdown instead

**Delete command message:** enable **Delete command messages** on the dashboard, or call `ctx.request_delete_invocation()`.

**Async handlers:** `async def` handlers are supported; use `await` only with async APIs you provide. `ctx.send()` is synchronous.

**Guild / API helpers on `bot`** (bot must be **Running** on the dashboard):

- `bot.get_guild_channels(guild_id)` / `bot.list_guild_channels(guild_id)` — use with or without `await` in `async def` handlers
- `bot.get_guild_members(guild_id, limit=1000, after=None)`
- `bot.get_guild(guild_id)`, `bot.get_user(user_id)`
- `bot.get_channel_messages(channel_id, limit=50, before=None)`
- `bot.send_message(channel_id, content, reply_to=None, guild_id=None)`
- `bot.rest()` — raw `FluxerREST` client

### 4.4 Event listeners - `@bot.listen`

```python
@bot.listen("on_message")
def message_handler(message):
    if message.author_id == ...:  # see note below
        return
    if "hello" in message.content.lower():
        return "Hi!"  # optional auto-reply string
```

For selfbots, commands are usually triggered by **your** messages with the prefix. Listeners fire on **other** people's messages (and optionally yours if you add logic).

### 4.5 `forwardEmbedMethod`

```python
text = forwardEmbedMethod(
    content="Body **markdown** supported",
    title="Title",
    image="https://example.com/image.png",
    color=0x3B82F6,  # or "#3B82F6" — shown as a subtle footer tag in plain text
    footer="Optional footer",
    description="Alias for content",
)
ctx.send(text)
```

### 4.6 Logging

```python
log("Something happened", type_="INFO")   # INFO | WARNING | ERROR
```

## 5. Script Hub (GUI)

1. Run `python3 gui.py` (or `python3 gui.py --web`)
2. Open **Script Hub**
3. **New script** -> edit -> **Save to hub**
4. **Test** runs the handler locally without sending to Fluxer

Scripts live in:

`Flx/scripts/hub/` under your OS app data directory (see README).

## 6. Complete example

```python
from flx.fluxerscript import flxScript, getConfigData, updateConfigData, log

@flxScript(
    name="Greeter",
    author="You",
    description="Says hi",
    usage="<p>hi <name>",
)
def greeter():
    if getConfigData().get("greet_enabled") is None:
        updateConfigData("greet_enabled", True)

    @bot.command(name="hi", description="Say hi")
    def hi_cmd(ctx, *, args: str):
        name = args.strip() or "friend"
        ctx.send(f"Hello, **{name}**!")

    @bot.listen("on_message")
    def on_msg(message):
        if "flx" in message.content.lower() and not message.author_id.startswith("0"):
            return None  # customize auto-reply logic

greeter()
```

## 7. Attachments

Use `ctx.attach(filename, bytes)` after `ctx.send()` for images or files (for example `httpcat` or `pokemon` community scripts).

## 8. Community hub

Bundled scripts live under `scripts/community/` in the repo and sync into **Script Hub -> Community** on launch. Users click **Add to Script Hub** to copy a script into their personal hub.

## 9. Getting your token

1. Log in at [web.fluxer.app](https://web.fluxer.app)
2. DevTools -> Network -> request to `api.fluxer.app`
3. Copy the `Authorization` header value into `FLUXER_TOKEN` in **Settings -> Edit config**

Never share or commit your token.
