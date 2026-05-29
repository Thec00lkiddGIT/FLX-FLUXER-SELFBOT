"""Pokémon lookup via PokéAPI."""

from flx.fluxerscript import flxScript, log
from flx.pokemon import pokemon_lookup


@flxScript(
    name="Pokémon",
    author="c00lkiddtech",
    description="PokéAPI lookup (name, id, or random)",
    usage="<p>pokemon <name|id|random>",
)
def pokemon_script():
    @bot.command(name="pokemon", description="Pokemon sprite and stats")
    def pokemon_cmd(ctx, *, args: str):
        query = args.strip()
        if not query:
            ctx.send(
                "Usage: <p>pokemon <name|id|random>\n"
                "Examples: <p>pokemon pikachu  <p>pokemon 25  <p>pokemon random"
            )
            return
        try:
            text, files = pokemon_lookup(query)
        except ValueError as exc:
            ctx.send(str(exc))
            return
        except RuntimeError as exc:
            ctx.send(f"Pokémon error: {exc}")
            return
        ctx.send(text)
        for filename, data in files:
            ctx.attach(filename, data)
        log(f"pokemon {query}", type_="INFO")


pokemon_script()
