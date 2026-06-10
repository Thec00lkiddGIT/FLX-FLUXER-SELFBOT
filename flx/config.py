"""Load config from Application Support config.env."""

from __future__ import annotations

import os

from flx.paths import ensure_env_file, env_file


def config_env_path() -> str:
    return str(env_file())


def load_dotenv() -> None:
    path = ensure_env_file()
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _env(key: str) -> str:
    load_dotenv()
    return os.environ.get(key, "").strip()


def _require(key: str, label: str | None = None) -> str:
    value = _env(key)
    if not value:
        name = label or key
        raise ValueError(f"Missing {name}. Edit {config_env_path()}")
    return value


def _normalize_token(raw: str) -> str:
    token = raw.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def has_fluxer_token() -> bool:
    load_dotenv()
    return bool(_normalize_token(os.environ.get("FLUXER_TOKEN", "")))


def fluxer_token() -> str:
    token = _normalize_token(_require("FLUXER_TOKEN", "FLUXER_TOKEN"))
    if not token:
        raise ValueError(f"Missing FLUXER_TOKEN. Edit {config_env_path()}")
    return token


def set_fluxer_token(raw: str) -> str:
    """Save FLUXER_TOKEN to config.env and the current process."""
    token = _normalize_token(raw)
    if not token:
        raise ValueError("Token can't be empty.")
    path = ensure_env_file()
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    out: list[str] = []
    found = False
    for line in lines:
        if line.strip().startswith("FLUXER_TOKEN="):
            out.append(f"FLUXER_TOKEN={token}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"FLUXER_TOKEN={token}")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    os.environ["FLUXER_TOKEN"] = token
    return token


def api_base_url() -> str:
    url = _env("FLUXER_API_URL") or "https://api.fluxer.app"
    url = url.rstrip("/")
    if url.endswith("/api"):
        url = url[: -len("/api")]
    return url


def command_prefix() -> str:
    return _env("PREFIX") or "!"


def ollama_base_url() -> str:
    url = _env("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"
    return url.rstrip("/")


def ollama_model() -> str:
    return _env("OLLAMA_MODEL") or "llama3.2"


def set_command_prefix(new_prefix: str) -> str:
    """Update PREFIX in config.env and the current process."""
    prefix = new_prefix.strip()
    if not prefix or len(prefix) > 8 or any(c.isspace() for c in prefix):
        raise ValueError("Prefix must be 1–8 non-space characters.")
    path = ensure_env_file()
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    out: list[str] = []
    found = False
    for line in lines:
        if line.strip().startswith("PREFIX="):
            out.append(f"PREFIX={prefix}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"PREFIX={prefix}")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    os.environ["PREFIX"] = prefix
    return prefix


def weather_api_key() -> str:
    return _require("C99_WEATHER_KEY")


def glseries_api_token() -> str:
    return _require("GLSERIES_TOKEN")


def glseries_base_url() -> str:
    return _env("GLSERIES_BASE_URL") or "https://live.glseries.net/api/v1"


def serpapi_key() -> str:
    return _require("SERPAPI_KEY")


def api_ninjas_key() -> str:
    return _require("API_NINJAS_KEY")


def osint_api_key() -> str:
    return _require("OSINT_INDUSTRIES_KEY")


def poof_api_key() -> str:
    return _require("POOF_API_KEY")
