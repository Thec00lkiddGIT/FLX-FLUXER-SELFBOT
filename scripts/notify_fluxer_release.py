#!/usr/bin/env python3
"""Post a GitHub release announcement to a Fluxer #releases webhook."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

WEBHOOK_URL_RE = re.compile(
    r"https?://[^/]+/v1/webhooks/(\d+)/([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


def _webhook_execute_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise ValueError("FLUXER_RELEASES_WEBHOOK_URL is empty")

    match = WEBHOOK_URL_RE.search(raw)
    if match:
        base = raw.split("/v1/webhooks/")[0].rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        wid, token = match.group(1), match.group(2)
        return f"{base}/webhooks/{wid}/{token}?wait=true"

    if raw.endswith("/github") or raw.endswith("/slack"):
        return f"{raw}?wait=true" if "?" not in raw else raw
    return f"{raw}?wait=true" if "?" not in raw else raw


def _build_payload() -> dict:
    tag = os.environ.get("RELEASE_TAG", "").strip() or "unknown"
    name = os.environ.get("RELEASE_NAME", "").strip() or tag
    body = (os.environ.get("RELEASE_BODY") or "").strip()
    url = os.environ.get("RELEASE_URL", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()

    description = f"**{name}**"
    if body:
        excerpt = body[:1200]
        if len(body) > 1200:
            excerpt += "\n…"
        description += f"\n\n{excerpt}"

    embed = {
        "title": f"FLX {tag} is out",
        "description": description[:4096],
        "color": 0x3B82F6,
        "url": url or None,
        "fields": [],
    }
    if url:
        embed["fields"].append(
            {"name": "Grab it", "value": f"[Download on GitHub]({url})", "inline": False}
        )
    if repo:
        embed["fields"].append({"name": "Source", "value": f"`{repo}`", "inline": True})

    payload: dict = {
        "username": os.environ.get("WEBHOOK_USERNAME", "updates"),
        "embeds": [embed],
    }
    content = os.environ.get("RELEASE_CONTENT", "").strip()
    if content:
        payload["content"] = content[:2000]
    elif url:
        payload["content"] = f"**{tag}** just dropped — Mac, Windows, and Chromebook builds are on GitHub."
    return payload


def main() -> int:
    webhook_raw = os.environ.get("FLUXER_RELEASES_WEBHOOK_URL", "").strip()
    if not webhook_raw:
        print("FLUXER_RELEASES_WEBHOOK_URL not set; skipping Fluxer notification.")
        return 0

    try:
        execute_url = _webhook_execute_url(webhook_raw)
    except ValueError as exc:
        print(f"Invalid webhook config: {exc}", file=sys.stderr)
        return 1

    payload = _build_payload()
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        execute_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "FLX-GitHub-Release-Notify/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read()
            print(f"Posted to Fluxer (HTTP {resp.status}).")
            if body.strip():
                print(body.decode("utf-8", errors="replace")[:500])
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"Fluxer webhook failed: HTTP {exc.code}: {detail[:500]}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Fluxer webhook network error: {exc.reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
