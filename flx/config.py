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


def fluxer_token() -> str:
    token = _require("FLUXER_TOKEN", "FLUXER_TOKEN")
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def api_base_url() -> str:
    url = _env("FLUXER_API_URL") or "https://api.fluxer.app"
    url = url.rstrip("/")
    if url.endswith("/api"):
        url = url[: -len("/api")]
    return url


def command_prefix() -> str:
    return _env("PREFIX") or "!"


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
