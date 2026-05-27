"""Message text helpers."""

from __future__ import annotations

MAX_MESSAGE_LENGTH = 2000


def split_message_content(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split text into chunks at or below Fluxer's message limit."""
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        window = remaining[:limit]
        cut = window.rfind("\n")
        if cut < limit // 3:
            cut = limit

        piece = remaining[:cut]
        if not piece:
            piece = remaining[:limit]
            cut = len(piece)

        chunks.append(piece.rstrip("\n") if cut < len(remaining) else piece)
        remaining = remaining[cut:].lstrip("\n")

    return [c for c in chunks if c]
