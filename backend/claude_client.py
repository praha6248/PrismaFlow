"""Cloud model routing and private, per-user provider settings."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from . import gemini_client
from .config import user_env_path
from .ollama_client import OllamaClient, OllamaError

T = TypeVar("T", bound=BaseModel)

CLAUDE_MODEL = "claude-opus-5-5"
KEY_VARIABLE = "PRISMAFLOW_ANTHROPIC_API_KEY"
MODE_VARIABLE = "PRISMAFLOW_QUALITY_MODE"
GEMINI_KEY = "PRISMAFLOW_GEMINI_API_KEY"
PROVIDER = "PRISMAFLOW_PROVIDER"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _write_env(path: Path, values: dict[str, str | None]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    kept = [line for line in lines if not any(re.match(rf"\s*{name}\s*=", line) for name in values)]
    kept += [f"{name}={value}" for name, value in values.items() if value]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False, encoding="utf-8") as temp:
        try:
            temp.write("\n".join(kept) + ("\n" if kept else ""))
            temp.close()
            os.replace(temp.name, path)
        finally:
            Path(temp.name).unlink(missing_ok=True)



class QualityConfig:
    """Runtime switch for the Claude quality mode, persisted in the user's env file."""

    def __init__(self, env_path: Path | None = None) -> None:
        self.env_path = env_path or user_env_path()
        self.key = os.environ.get(KEY_VARIABLE, "").strip()
        self.gemini_key = os.environ.get(GEMINI_KEY, "").strip()
        legacy = "claude" if os.environ.get(MODE_VARIABLE, "").strip() in ("1", "true", "on") else "local"
        selected = os.environ.get(PROVIDER, legacy)
        self.provider = selected if (
            (selected == "gemini" and self.gemini_key) or (selected == "claude" and self.key)
        ) else "local"

    @property
    def active(self) -> bool:
        return self.provider != "local"

    def public(self) -> dict[str, Any]:
        return {"enabled": self.active, "provider": self.provider, "has_key": bool(self.key),
                "has_gemini_key": bool(self.gemini_key),
                "model": gemini_client.MODEL if self.provider == "gemini" else CLAUDE_MODEL}

    def update(self, enabled: bool | None = None, key: str | None = None,
               provider: str | None = None) -> dict[str, Any]:
        target = provider or "claude"
        keys = {"claude": self.key, "gemini": self.gemini_key}
        values = {}
        if key is not None and target in keys:
            keys[target] = key.strip()
            values[GEMINI_KEY if target == "gemini" else KEY_VARIABLE] = keys[target] or None
        selected = self.provider
        if target == "local" or (enabled is False and target == selected):
            selected = "local"
        elif enabled or (provider and enabled is None and key is None):
            selected = target
        if selected != "local" and not keys[selected]:
            selected = "local"
        values.update({PROVIDER: selected, MODE_VARIABLE: "1" if selected == "claude" else None})
        _write_env(self.env_path, values)
        self.key, self.gemini_key = keys["claude"], keys["gemini"]
        self.provider = selected
        return self.public()


class HybridLLM:
    """Answers with Claude in quality mode and with the local model otherwise or on failure."""

    def __init__(self, local: OllamaClient, config: QualityConfig, client: Any = None) -> None:
        self.local = local
        self.config = config
        self._client = client
        self._client_key: str | None = None
        self.last_error: str | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.local, name)

    @property
    def embed(self):
        return None if self.config.provider == "gemini" else getattr(self.local, "embed", None)

    def _claude(self) -> Any:
        if self._client is None or self._client_key != self.config.key:
            self._client = anthropic.AsyncAnthropic(api_key=self.config.key, timeout=240.0, max_retries=2)
            self._client_key = self.config.key
        return self._client

    async def structured(self, schema: type[T], system: str, prompt: str, **kwargs: Any) -> T:
        """Structured answer from Claude when the quality mode is on, else from Ollama."""
        if self.config.provider == "gemini":
            return await gemini_client.structured(self.config.gemini_key, schema, system, prompt,
                                                  kwargs.get("temperature", 0.4))
        if self.config.provider == "claude":
            try:
                return await self._ask_claude(schema, system, prompt)
            except (anthropic.APIError, ValueError) as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"[:300]
        return await self.local.structured(schema, system, prompt, **kwargs)

    async def _ask_claude(self, schema: type[T], system: str, prompt: str) -> T:
        response = await self._claude().beta.messages.parse(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
            output_config={"effort": "medium"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise ValueError("Claude declined the request")
        parsed = response.parsed_output
        if parsed is None:
            raise ValueError("Claude returned no structured output")
        self.last_error = None
        return parsed

    async def health(self) -> dict[str, Any]:
        """Local model health plus the quality mode state."""
        report = await self.local.health()
        return {**report, "quality": {**self.config.public(), "last_error": self.last_error}}


__all__ = ["HybridLLM", "QualityConfig", "OllamaError"]
