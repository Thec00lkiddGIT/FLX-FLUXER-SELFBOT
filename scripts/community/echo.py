"""Echo - repeat your message."""

from flx.fluxerscript import flxScript, log


@flxScript(
    name="Echo",
    author="c00lkiddtech",
    description="Repeat your text",
    usage="<p>echo <text>",
)
def echo_script():
    @bot.command(name="echo", description="Repeat your text")
    def echo_cmd(ctx, *, args: str):
        if not args.strip():
            ctx.send("Usage: <p>echo <text>")
            return
        ctx.send(args.strip())
        log("echo handled", type_="INFO")


echo_script()
