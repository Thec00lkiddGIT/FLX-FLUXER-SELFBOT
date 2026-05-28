"""Decode Fluxer snowflake IDs (fluxertools-style layout)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

# Fluxer epoch: 2015-01-01 00:00:00 UTC
FLUXER_EPOCH_MS = 1420070400000

TIMESTAMP_SHIFT = 22
INCREMENT_MASK = 0xFFF  # 12 bits
PROCESS_MASK = 0x1F  # 5 bits
WORKER_MASK = 0x1F  # 5 bits
WORKER_COMBINED_MASK = 0x3FF  # 10 bits


@dataclass(frozen=True)
class SnowflakeParts:
    snowflake: int
    timestamp_ms: int
    worker_id: int
    process_id: int
    increment: int
    worker_combined: int

    @property
    def created_at(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp_ms / 1000, tz=timezone.utc)

    def format_created_local(self) -> str:
        return self.created_at.astimezone().strftime("%A, %B %d, %Y at %I:%M:%S %p %Z")


def decode_snowflake(raw: str | int) -> SnowflakeParts:
    try:
        value = int(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f"Invalid snowflake ID: {raw!r}") from exc
    if value < 0:
        raise ValueError(f"Invalid snowflake ID: {raw!r}")

    timestamp_part = value >> TIMESTAMP_SHIFT
    timestamp_ms = timestamp_part + FLUXER_EPOCH_MS
    increment = value & INCREMENT_MASK
    process_id = (value >> 12) & PROCESS_MASK
    worker_id = (value >> 17) & WORKER_MASK
    worker_combined = (value >> 12) & WORKER_COMBINED_MASK

    return SnowflakeParts(
        snowflake=value,
        timestamp_ms=timestamp_ms,
        worker_id=worker_id,
        process_id=process_id,
        increment=increment,
        worker_combined=worker_combined,
    )


def format_snowflake_block(parts: SnowflakeParts) -> str:
    lines = [
        f"**Created:** {parts.format_created_local()}",
        f"**Unix (ms):** `{parts.timestamp_ms}`",
        f"**Worker ID:** `{parts.worker_id}` · **Process ID:** `{parts.process_id}` · **Increment:** `{parts.increment}`",
        f"**Worker (10-bit):** `{parts.worker_combined}`",
    ]
    return "\n".join(lines)
