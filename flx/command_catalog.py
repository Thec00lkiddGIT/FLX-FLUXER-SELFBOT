"""Built-in command categories for help text and the dashboard."""

from __future__ import annotations

from flx.commands import COMMANDS

# Populated after utility/danger modules define their lists (see bottom).
GENERAL_UTILITY_COMMANDS: list[tuple[str, str]] = []
MOD_UTILITY_COMMANDS: list[tuple[str, str]] = []
ABUSE_UTILITY_COMMANDS: list[tuple[str, str]] = []
MOD_COMMANDS: list[tuple[str, str]] = []
ABUSE_COMMANDS: list[tuple[str, str]] = []

CATEGORY_LABELS = {
    "general": "General",
    "mod": "Mod",
    "abuse": "Abuse",
}

CATEGORY_HINTS = {
    "general": "",
    "mod": "Server moderation — you need permission on Fluxer.",
    "abuse": "Enable with `!abuse` and confirm in the FLX app first.",
}

# Core builtins listed under mod instead of general.
_MOD_CORE_NAMES = frozenset({"purge"})


def _split_core_commands() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    general: list[tuple[str, str]] = []
    mod: list[tuple[str, str]] = []
    for name, help_text in COMMANDS:
        if name in _MOD_CORE_NAMES:
            mod.append((name, help_text))
        else:
            general.append((name, help_text))
    return general, mod


def _bind_catalog() -> None:
    from flx.danger_cmds import ABUSE_COMMANDS as _abuse
    from flx.danger_cmds import MOD_COMMANDS as _mod
    from flx.utility_cmds import (
        ABUSE_UTILITY_COMMANDS as _abuse_util,
        GENERAL_UTILITY_COMMANDS as _general_util,
        MOD_UTILITY_COMMANDS as _mod_util,
    )

    global MOD_COMMANDS, ABUSE_COMMANDS
    global GENERAL_UTILITY_COMMANDS, MOD_UTILITY_COMMANDS, ABUSE_UTILITY_COMMANDS
    MOD_COMMANDS = _mod
    ABUSE_COMMANDS = _abuse
    GENERAL_UTILITY_COMMANDS = _general_util
    MOD_UTILITY_COMMANDS = _mod_util
    ABUSE_UTILITY_COMMANDS = _abuse_util


def iter_categories() -> list[tuple[str, list[tuple[str, str]]]]:
    _bind_catalog()
    general_core, mod_core = _split_core_commands()
    return [
        ("general", general_core + list(GENERAL_UTILITY_COMMANDS)),
        ("mod", mod_core + list(MOD_COMMANDS) + list(MOD_UTILITY_COMMANDS)),
        ("abuse", list(ABUSE_COMMANDS) + list(ABUSE_UTILITY_COMMANDS)),
    ]


def all_builtin_command_names() -> frozenset[str]:
    names: set[str] = set()
    for _, cmds in iter_categories():
        names.update(name for name, _ in cmds)
    return frozenset(names)


def dashboard_command_rows() -> list[dict[str, str]]:
    """Rows for GET /api/status command list."""
    rows: list[dict[str, str]] = []
    for category, cmds in iter_categories():
        for name, help_text in cmds:
            rows.append(
                {
                    "name": name,
                    "help": help_text,
                    "source": category,
                }
            )
    return rows


def format_help(prefix: str) -> str:
    lines = [f"**Commands** (prefix `{prefix}`)", ""]
    seen: set[str] = set()

    for category, cmds in iter_categories():
        label = CATEGORY_LABELS[category]
        hint = CATEGORY_HINTS[category]
        lines.append(f"**{label}**")
        if hint:
            lines.append(hint)
        lines.append("")
        for cmd, help_text in cmds:
            if cmd in seen:
                continue
            seen.add(cmd)
            lines.append(f"`{prefix}{cmd}` - {help_text}")
        lines.append("")

    from flx.script_hub import hub_command_specs

    hub_specs = hub_command_specs()
    if hub_specs:
        lines.append("**Script Hub** (your installed scripts)")
        lines.append("")
        for spec in hub_specs:
            name = spec["name"]
            if name in seen:
                continue
            seen.add(name)
            lines.append(f"`{prefix}{name}` - {spec.get('help', '')}")
        lines.append("")

    return "\n".join(lines).rstrip()
