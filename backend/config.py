"""Runtime configuration resolved from the environment and the host system."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "PrismFlow"


def resource_root() -> Path:
    """Return the directory holding bundled resources, aware of PyInstaller's _MEIPASS."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle)
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Return the persistent per-user data directory, outside any temporary bundle."""
    override = os.environ.get("PRISMFLOW_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_host(raw: str) -> str:
    """Turn an OLLAMA_HOST style value into a full base URL."""
    value = raw.strip().rstrip("/")
    if not value:
        return "http://127.0.0.1:11434"
    if "://" not in value:
        value = f"http://{value}"
    scheme, rest = value.split("://", 1)
    host = rest.split("/", 1)[0]
    if ":" not in host.rsplit("]", 1)[-1]:
        value = f"{scheme}://{host}:11434"
    if "0.0.0.0" in value:
        value = value.replace("0.0.0.0", "127.0.0.1")
    return value


UI_LOCALE = "pl_PL"


def system_language() -> tuple[str, str]:
    """Return the default content (language, country), following the UI locale unless overridden."""
    raw = os.environ.get("PRISMFLOW_LOCALE") or UI_LOCALE
    code = raw.split(".", 1)[0].replace("-", "_")
    parts = code.split("_")
    lang = (parts[0] or "en").lower()
    country = parts[1].upper() if len(parts) > 1 else ""
    return lang, country


COUNTRY_FOR_LANGUAGE = {
    "pl": "PL",
    "de": "DE",
    "fr": "FR",
    "es": "ES",
    "it": "IT",
    "cs": "CZ",
    "uk": "UA",
    "pt": "PT",
    "nl": "NL",
    "en": "",
}


PREFERRED_MODELS = (
    "local/gemma3-12b",
    "gemma3:12b",
    "local/gemma3-4b",
    "gemma3:4b",
    "hf.co/speakleash/Bielik-4.5B-v3.0-Instruct-GGUF:Q8_0",
    "qwen2.5:7b",
    "llama3.1:8b",
)


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    ollama_url: str = field(default_factory=lambda: normalize_host(os.environ.get("OLLAMA_HOST", "")))
    model: str | None = field(default_factory=lambda: os.environ.get("PRISMFLOW_MODEL") or None)
    trend_anchor: str = field(default_factory=lambda: os.environ.get("PRISMFLOW_TREND_ANCHOR", "calendar"))
    cache_ttl_seconds: int = 60 * 60 * 24 * 3
    negative_cache_ttl_seconds: int = 60 * 30
    http_timeout: float = 12.0
    llm_timeout: float = 240.0
    user_agent: str = "PrismFlow/0.1 (local-first product discovery desktop app)"
    language: str = field(default_factory=lambda: system_language()[0])
    country: str = field(default_factory=lambda: system_language()[1])

    @property
    def database_path(self) -> Path:
        """Location of the SQLite workspace."""
        return data_dir() / "workspace.db"

    @property
    def frontend_dist(self) -> Path:
        """Location of the compiled frontend bundle."""
        return resource_root() / "frontend" / "dist"


settings = Settings()
