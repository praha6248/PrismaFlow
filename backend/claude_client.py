"""Optional Claude API backend: the "quality mode" that answers structured prompts with Claude.

The key is the user's own and lives in ~/.config/PrismaFlow/prismaflow.env (mode 600). When the
mode is off, the key is missing or Claude fails, every request goes to the local Ollama model.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from .config import user_env_path
from .ollama_client import OllamaClient, OllamaError

T = TypeVar("T", bound=BaseModel)

CLAUDE_MODEL = "claude-opus-5-5"
KEY_VARIABLE = "PRISMAFLOW_ANTHROPIC_API_KEY"
MODE_VARIABLE = "PRISMAFLOW_QUALITY_MODE"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _write_env(path: Path, values: dict[str, str | None]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    kept = [line for line in lines if not any(re.match(rf"\s*{name}\s*=", line) for name in values)]
    kept += [f"{name}={value}" for name, value in values.items() if value]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    path.chmod(0o600)


class QualityConfig:
    """Runtime switch for the Claude quality mode, persisted in the user's env file."""

    def __init__(self, env_path: Path | None = None) -> None:
        self.env_path = env_path or user_env_path()
        self.key = os.environ.get(KEY_VARIABLE, "").strip()
        self.enabled = os.environ.get(MODE_VARIABLE, "").strip() in ("1", "true", "on") and bool(self.key)

    @property
    def active(self) -> bool:
        """Whether requests should go to Claude."""
        return self.enabled and bool(self.key)

    def public(self) -> dict[str, Any]:
        """State safe to show in the UI: never the key itself."""
        return {"enabled": self.active, "has_key": bool(self.key), "model": CLAUDE_MODEL}

    def update(self, enabled: bool | None = None, key: str | None = None) -> dict[str, Any]:
        """Change the mode or the key and persist both."""
        if key is not None:
            self.key = key.strip()
        if enabled is not None:
            self.enabled = enabled
        if not self.key:
            self.enabled = False
        _write_env(self.env_path, {KEY_VARIABLE: self.key or None, MODE_VARIABLE: "1" if self.enabled else None})
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

    def _claude(self) -> Any:
        if self._client is None or self._client_key != self.config.key:
            self._client = anthropic.AsyncAnthropic(api_key=self.config.key, timeout=240.0, max_retries=2)
            self._client_key = self.config.key
        return self._client

    async def structured(self, schema: type[T], system: str, prompt: str, **kwargs: Any) -> T:
        """Structured answer from Claude when the quality mode is on, else from Ollama."""
        if self.config.active:
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
