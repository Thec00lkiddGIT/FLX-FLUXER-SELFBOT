"""Wait and retry when Fluxer returns rate limits / channel slowmode."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

log = logging.getLogger("flx.rate_limit")

MAX_ATTEMPTS = 30
MAX_TOTAL_SLEEP = 900.0
DEFAULT_RETRY_SECONDS = 1.0
MAX_SINGLE_WAIT = 600.0

_RETRY_HTTP_CODES = frozenset({429, 503})
_RETRY_API_CODES = frozenset(
    {
        "RATE_LIMITED",
        "SLOWMODE_RATE_LIMIT",
        "CHANNEL_SLOWMODE",
        "MESSAGE_SEND_RATE_LIMIT",
        "RESOURCE_COOLDOWN",
    }
)


def _parse_json(body: bytes) -> dict | None:
    try:
        data = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _normalize_delay_seconds(value: object, *, key: str = "") -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None

    lower_key = key.lower()
    now = time.time()
    if "ms" in lower_key:
        number /= 1000.0
    elif "reset" in lower_key and number > now:
        # Absolute reset timestamp (epoch seconds) -> delta.
        number -= now
    elif number > 1000:
        # Many APIs return retry_after in milliseconds.
        number /= 1000.0
    return max(0.0, number)


def _header_retry_seconds(headers) -> float | None:
    if headers is None:
        return None
    for key in ("Retry-After", "X-RateLimit-Reset-After", "X-RateLimit-Reset"):
        raw = headers.get(key)
        if not raw:
            continue
        text = str(raw).strip()
        value = _normalize_delay_seconds(text, key=key)
        if value is not None:
            return value
        try:
            when = parsedate_to_datetime(text)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            delta = (when - datetime.now(timezone.utc)).total_seconds()
            if delta > 0:
                return delta
        except (TypeError, ValueError, OverflowError):
            continue
    return None


def retry_delay_seconds(status: int, body: bytes, headers) -> float | None:
    data = _parse_json(body)
    if data is not None:
        for key in (
            "retry_after",
            "retryAfter",
            "retry_after_ms",
            "retryAfterMs",
            "cooldown",
            "cooldown_ms",
            "wait",
            "wait_ms",
            "reset_after",
            "resetAt",
        ):
            if key in data and data[key] is not None:
                value = _normalize_delay_seconds(data[key], key=key)
                if value is not None:
                    return value
        nested = data.get("errors")
        if isinstance(nested, list):
            for item in nested:
                if isinstance(item, Mapping):
                    for key in ("retry_after", "retry_after_ms", "cooldown", "wait"):
                        if item.get(key) is None:
                            continue
                        value = _normalize_delay_seconds(item.get(key), key=key)
                        if value is not None:
                            return value

    header_wait = _header_retry_seconds(headers)
    if header_wait is not None:
        return header_wait

    if status in _RETRY_HTTP_CODES:
        return DEFAULT_RETRY_SECONDS

    return None


def should_retry(status: int, body: bytes) -> bool:
    if status in _RETRY_HTTP_CODES:
        return True

    data = _parse_json(body)
    if data is not None:
        code = str(data.get("code") or "").upper()
        if code in _RETRY_API_CODES or "RATE" in code or "SLOW" in code:
            return True
        message = str(data.get("message") or "").lower()
        if any(
            phrase in message
            for phrase in (
                "rate limit",
                "slowmode",
                "slow mode",
                "cooldown",
                "try again",
            )
        ):
            return True

    text = body.decode("utf-8", errors="replace").lower()
    return any(
        phrase in text
        for phrase in ("rate limit", "slowmode", "slow mode", "cooldown", "retry_after")
    )


def urlopen_with_rate_limit(
    req: urllib.request.Request,
    *,
    timeout: float = 30,
) -> object:
    """Open URL; on 429/slowmode, sleep and retry until success or limits hit."""
    total_slept = 0.0
    last_status = 0
    last_body = b""

    for attempt in range(MAX_ATTEMPTS):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            last_status = exc.code
            last_body = exc.read()
            if not should_retry(exc.code, last_body) or attempt >= MAX_ATTEMPTS - 1:
                detail = last_body.decode("utf-8", errors="replace")
                raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc

            delay = retry_delay_seconds(exc.code, last_body, exc.headers)
            if delay is None:
                delay = DEFAULT_RETRY_SECONDS
            delay = min(max(delay, 0.05), MAX_SINGLE_WAIT)
            if total_slept + delay > MAX_TOTAL_SLEEP:
                detail = last_body.decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"HTTP {exc.code}: rate limit exceeded max wait ({MAX_TOTAL_SLEEP}s): {detail}"
                ) from exc

            log.info(
                "Chat cooldown / rate limit (HTTP %s), waiting %.2fs before retry %s/%s",
                exc.code,
                delay,
                attempt + 2,
                MAX_ATTEMPTS,
            )
            time.sleep(delay)
            total_slept += delay

    detail = last_body.decode("utf-8", errors="replace") if last_body else ""
    raise RuntimeError(f"HTTP {last_status}: {detail}")
