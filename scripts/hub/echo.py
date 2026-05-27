"""Echo script - FlxScript example."""

from flx.fluxerscript import flxScript, log

# bot is injected when Flx loads this script


@flxScript(
    name="Echo Script",
    author="Flx",
    description="Echoes your message back",
    usage="<p>echo <text>",
)
def echo_script():
    @bot.command(name="echo", description="Echoes your message")
    def echo_cmd(ctx, *, args: str):
        if not args:
            ctx.send("Usage: <p>echo <text>")
            return
        ctx.send(f"🔊 {args}")
        log("echo handled", type_="INFO")


echo_script()
