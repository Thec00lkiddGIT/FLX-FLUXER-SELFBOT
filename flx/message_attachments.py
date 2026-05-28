"""Download image attachments from Fluxer messages."""

from __future__ import annotations

import mimetypes
import urllib.error
import urllib.request

_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
_IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp"})


def first_image_attachment(raw: dict) -> dict | None:
    attachments = raw.get("attachments")
    if not isinstance(attachments, list):
        return None
    for item in attachments:
        if not isinstance(item, dict):
            continue
        content_type = str(item.get("content_type") or "").lower().split(";")[0].strip()
        filename = str(item.get("filename") or "")
        lower_name = filename.lower()
        if content_type in _IMAGE_TYPES:
            return item
        if any(lower_name.endswith(ext) for ext in _IMAGE_EXTS):
            return item
    return None


def attachment_url(attachment: dict) -> str:
    for key in ("url", "proxy_url"):
        value = attachment.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    raise ValueError("Attachment has no download URL")


def download_attachment(url: str, *, auth_token: str) -> tuple[bytes, str, str]:
    headers = {"User-Agent": "Flx/1.0 (Fluxer selfbot)"}
    if auth_token:
        headers["Authorization"] = auth_token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "application/octet-stream").split(";")[0]
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Could not download attachment (HTTP {exc.code})") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not download attachment: {exc.reason}") from exc

    filename = "image.png"
    if url:
        guess = url.split("?", 1)[0].rsplit("/", 1)[-1]
        if "." in guess:
            filename = guess
    ext = mimetypes.guess_extension(ctype) or ".png"
    if "." not in filename:
        filename = f"{filename}{ext}"
    return data, filename, ctype
