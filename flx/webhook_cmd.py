"""!wb - send or delete via Fluxer webhook URL (token in URL)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from flx.config import api_base_url
from flx.rate_limit import urlopen_with_rate_limit

WEBHOOK_URL_RE = re.compile(
    r"https?://[^\s]+?/webhooks/(\d+)/([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


def parse_webhook_url(raw: str) -> tuple[str, str]:
    match = WEBHOOK_URL_RE.search(raw.strip())
    if not match:
        raise ValueError(
            "Invalid webhook URL. Use a full Fluxer webhook URL "
            "(…/webhooks/{id}/{token})."
        )
    return match.group(1), match.group(2)


def _api_base_v1() -> str:
    base = api_base_url().rstrip("/")
    if base.endswith("/api"):
        base = base[: -len("/api")]
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def _webhook_request(
    method: str,
    webhook_id: str,
    token: str,
    *,
    body: dict | None = None,
) -> None:
    url = f"{_api_base_v1()}/webhooks/{webhook_id}/{token}"
    data = None
    headers = {
        "User-Agent": "Flx/1.0 (Fluxer selfbot)",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen_with_rate_limit(req, timeout=30) as resp:
            resp.read()
    except RuntimeError:
        raise
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Webhook HTTP {exc.code}: {detail}") from exc


def parse_wb_args(args: str) -> tuple[str, str, str | None]:
    text = args.strip()
    if not text:
        raise ValueError("missing webhook URL and action")

    match = re.search(r"\s+(send|delete)\b", text, re.IGNORECASE)
    if not match:
        raise ValueError("action must be `send` or `delete`")

    action = match.group(1).lower()
    url_part = text[: match.start()].strip()
    rest = text[match.end() :].strip()

    if not url_part:
        raise ValueError("missing webhook URL before send/delete")

    if action == "delete":
        if rest:
            raise ValueError("`delete` does not take message text.")
        return url_part, action, None

    if not rest:
        raise ValueError("missing message text after `send`")
    return url_part, action, rest


def run_webhook_command(args: str) -> str:
    url_part, action, message_text = parse_wb_args(args)
    webhook_id, token = parse_webhook_url(url_part)

    if action == "send":
        assert message_text is not None
        _webhook_request(
            "POST",
            webhook_id,
            token,
            body={"content": message_text[:2000]},
        )
        return "Webhook message **sent**."

    _webhook_request("DELETE", webhook_id, token)
    return "Webhook **deleted** (token URL - no server admin needed)."
