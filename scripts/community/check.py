"""URL filter check (GLSeries)."""

from flx.fluxerscript import flxScript, log
from flx.glcheck import check_reply, parse_check_args


@flxScript(
    name="URL Check",
    author="c00lkiddtech",
    description="URL filter check (GLSeries)",
    usage="<p>check <url>",
)
def check_script():
    @bot.command(name="check", description="Check a URL against web filters")
    def check_cmd(ctx, *, args: str):
        if not args.strip():
            ctx.send(
                "Usage: <p>check <url>\nOptional: <p>check linewize example.com"
            )
            return
        try:
            filter_key, url = parse_check_args(args)
            chunks = check_reply(url, filter_key=filter_key)
        except ValueError as exc:
            ctx.send(str(exc))
            return
        except RuntimeError as exc:
            ctx.send(f"Check error: {exc}")
            return
        for chunk in chunks:
            ctx.send(chunk)
        log(f"check {url}", type_="INFO")


check_script()
