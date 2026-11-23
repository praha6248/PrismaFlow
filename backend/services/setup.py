"""First-run checks: is Ollama reachable and which models should be pulled."""

from __future__ import annotations

import os
from typing import Any

OLLAMA_DOWNLOAD = "https://ollama.com/download"
CHAT_MODELS = ("gemma3:12b", "gemma3:4b", "local/gemma3-12b", "local/gemma3-4b")


def memory_gb() -> float | None:
    """Return total system memory in GiB, or None when it cannot be read."""
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
    except (AttributeError, OSError, ValueError):
        return None


def _installed(name: str, models: list[str]) -> bool:
    names = {m.removesuffix(":latest") for m in models}
    return name.removesuffix(":latest") in names


def setup_status(ok: bool, models: list[str], url: str, ram_gb: float | None, ux_repo: str) -> dict[str, Any]:
    """Describe the models PrismaFlow needs, which are installed and the command to pull each missing one."""
    large = ram_gb is None or ram_gb >= 16
    chat = "gemma3:12b" if large else "gemma3:4b"
    entries = [
        {
            "id": "chat",
            "name": chat,
            "size": "8,1 GB" if large else "3,3 GB",
            "required": True,
            "installed": any(_installed(m, models) for m in CHAT_MODELS),
            "command": f"ollama pull {chat}",
            "source": f"https://ollama.com/library/{chat.split(':')[0]}",
        },
        {
            "id": "embed",
            "name": "bge-m3",
            "size": "1,2 GB",
            "required": False,
            "installed": _installed("bge-m3", models),
            "command": "ollama pull bge-m3",
            "source": "https://ollama.com/library/bge-m3",
        },
    ]
    if ux_repo:
        entries.append(
            {
                "id": "ux",
                "name": "local/gemma3-4b-ux",
                "size": "3,3 GB",
                "required": False,
                "installed": _installed("local/gemma3-4b-ux", models) or _installed(f"hf.co/{ux_repo}", models),
                "command": f"ollama pull hf.co/{ux_repo} && ollama cp hf.co/{ux_repo} local/gemma3-4b-ux",
                "source": f"https://huggingface.co/{ux_repo}",
            }
        )
    ready = ok and entries[0]["installed"]
    return {
        "ready": ready,
        "ollama": {"ok": ok, "url": url, "download": OLLAMA_DOWNLOAD},
        "memory_gb": round(ram_gb, 1) if ram_gb else None,
        "models": entries,
    }
