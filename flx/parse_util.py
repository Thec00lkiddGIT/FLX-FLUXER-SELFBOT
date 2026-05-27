"""Parse user IDs and mentions from command arguments."""

from __future__ import annotations

import re

MENTION_RE = re.compile(r"<@!?(\d+)>")


def parse_user_id(raw: str) -> str:
    """Extract a snowflake from `<@123>`, `<@!123>`, or a bare numeric ID."""
    text = raw.strip()
    match = MENTION_RE.fullmatch(text) or MENTION_RE.search(text)
    if match:
        return match.group(1)
    if re.fullmatch(r"\d{5,25}", text):
        return text
    raise ValueError(f"Invalid user - use a mention or numeric ID: {raw!r}")


def mention_user(user_id: str) -> str:
    return f"<@{user_id}>"
