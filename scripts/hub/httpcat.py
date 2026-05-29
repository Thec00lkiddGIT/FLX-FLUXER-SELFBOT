"""HTTP Cat - status code images from http.cat."""

from flx.fluxerscript import flxScript, log
from flx.httpcat import fetch_httpcat_image, httpcat_caption


@flxScript(
    name="HTTP Cat",
    author="c00lkiddtech",
    description="http.cat status image (e.g. 404)",
    usage="<p>httpcat <status code>",
)
def httpcat_script():
    @bot.command(name="httpcat", description="Post an http.cat status image")
    def httpcat_cmd(ctx, *, args: str):
        code_s = args.strip()
        if not code_s:
            ctx.send("Usage: <p>httpcat <status code>\nExample: <p>httpcat 404")
            return
        try:
            code = int(code_s)
        except ValueError:
            ctx.send("Status code must be a number (100-599).")
            return
        try:
            image, filename = fetch_httpcat_image(code)
        except ValueError as exc:
            ctx.send(str(exc))
            return
        except RuntimeError as exc:
            ctx.send(f"httpcat error: {exc}")
            return
        ctx.send(httpcat_caption(code))
        ctx.attach(filename, image)
        log(f"httpcat {code}", type_="INFO")


httpcat_script()
