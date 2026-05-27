# FlxScript Guide v1.0

*Nighty-style custom Python for [Fluxer](https://fluxer.app) selfbots.*

## 1. Overview

**FlxScript** extends **Flx** with your own Python commands and event handlers. Flx connects to `api.fluxer.app` / `gateway.fluxer.app`; scripts focus on what happens when you send a command or when messages arrive.

> **IMPORTANT - do not import these:**
> - `import discord` / `from discord import *`
> - `import fluxer` / unofficial Fluxer SDKs inside hub scripts
> - `matplotlib`, `numpy`, `pydub`, or other packages that need `pip install` in the hub
>
> Use the standard library plus FlxScript helpers. Put all docs and requirements in the script docstring.

> **Embeds:** Fluxer supports rich embeds on the API. In FlxScript, use `forwardEmbedMethod()` for formatted text replies (works everywhere). For full API embeds, use `ctx.send()` with markdown or extend via REST in advanced scripts.

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

**Aliases:** `@flxScript` and `@nightyScript` are the same decorator.

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
- `ctx.send(text)` - queue a reply (Flx sends after the handler returns)
- `ctx.reply_embed(content=..., title=..., image=...)` - formatted block via `forwardEmbedMethod`

**Delete command message:** enable **Delete command messages** on the dashboard, or call `ctx.request_delete_invocation()`.

**Async handlers:** `async def` handlers are supported; use `await` only with async APIs you provide. `ctx.send()` is synchronous.

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

## 7. Differences from Nighty

| Nighty | Flx |
|--------|-----|
| `await ctx.message.delete()` | Dashboard toggle or `ctx.request_delete_invocation()` |
| `await ctx.send()` | `ctx.send()` (sync) |
| Discord channels/guilds | Fluxer channels/guilds (same IDs in API) |
| `nightyScript` | `flxScript` or `nightyScript` (alias) |

## 8. Getting your token

1. Log in at [web.fluxer.app](https://web.fluxer.app)
2. DevTools -> Network -> request to `api.fluxer.app`
3. Copy the `Authorization` header value into `FLUXER_TOKEN` in **Settings -> Edit config**

Never share or commit your token.
