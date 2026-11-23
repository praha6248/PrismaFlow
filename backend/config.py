"""Runtime configuration resolved from the environment and the host system."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "PrismaFlow"
LEGACY_NAME = "PrismFlow"


def adopt_legacy(path: Path) -> None:
    """Rename a directory left by the app's former name so existing settings and projects carry over."""
    legacy = path.with_name(LEGACY_NAME)
    if not path.exists() and legacy.is_dir():
        legacy.rename(path)


def config_base() -> str:
    """Return the per-user configuration root: XDG on Linux, %APPDATA% on Windows."""
    if os.environ.get("XDG_CONFIG_HOME"):
        return os.environ["XDG_CONFIG_HOME"]
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return os.environ["APPDATA"]
    return str(Path.home() / ".config")


def data_base() -> str:
    """Return the per-user data root: XDG on Linux, %LOCALAPPDATA% on Windows."""
    if os.environ.get("XDG_DATA_HOME"):
        return os.environ["XDG_DATA_HOME"]
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return os.environ["LOCALAPPDATA"]
    return str(Path.home() / ".local" / "share")


def user_env_path() -> Path:
    """Location of the user's settings file, ~/.config/PrismaFlow/prismaflow.env."""
    base = config_base()
    return Path(base) / APP_NAME / "prismaflow.env"


def load_user_env() -> None:
    """Load KEY=VALUE pairs from ~/.config/PrismaFlow/prismaflow.env without overriding the environment."""
    base = config_base()
    adopt_legacy(Path(base) / APP_NAME)
    path = Path(base) / APP_NAME / "prismaflow.env"
    legacy = path.with_name("prismflow.env")
    if not path.exists() and legacy.is_file():
        legacy.write_text(legacy.read_text(encoding="utf-8").replace("PRISMFLOW_", "PRISMAFLOW_"), encoding="utf-8")
        legacy.rename(path)
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_user_env()


def resource_root() -> Path:
    """Return the directory holding bundled resources, aware of PyInstaller's _MEIPASS."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle)
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Return the persistent per-user data directory, outside any temporary bundle."""
    override = os.environ.get("PRISMAFLOW_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    else:
        base = data_base()
        path = Path(base) / APP_NAME
        adopt_legacy(path)
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
    raw = os.environ.get("PRISMAFLOW_LOCALE") or UI_LOCALE
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

TASK_MODELS = {
    "deliver": ("local/gemma3-4b-ux",),
}


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    ollama_url: str = field(default_factory=lambda: normalize_host(os.environ.get("OLLAMA_HOST", "")))
    model: str | None = field(default_factory=lambda: os.environ.get("PRISMAFLOW_MODEL") or None)
    embed_model: str = field(default_factory=lambda: os.environ.get("PRISMAFLOW_EMBED_MODEL", "bge-m3"))
    ux_model_repo: str = field(default_factory=lambda: os.environ.get("PRISMAFLOW_UX_MODEL_REPO", ""))
    trend_anchor: str = field(default_factory=lambda: os.environ.get("PRISMAFLOW_TREND_ANCHOR", "calendar"))
    discussion_max_age_days: int = field(default_factory=lambda: int(os.environ.get("PRISMAFLOW_DISCUSSION_MAX_AGE_DAYS") or 365 * 3))
    cache_ttl_seconds: int = 60 * 60 * 24 * 3
    negative_cache_ttl_seconds: int = 60 * 30
    http_timeout: float = 12.0
    llm_timeout: float = 240.0
    user_agent: str = "PrismaFlow/0.1 (local-first product discovery desktop app)"
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
