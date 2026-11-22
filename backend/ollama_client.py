"""Async client for a local Ollama server with Pydantic-enforced structured outputs."""

from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .config import PREFERRED_MODELS, settings

T = TypeVar("T", bound=BaseModel)


class OllamaError(RuntimeError):
    """Raised when Ollama is unreachable or returns unusable output."""


def inline_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return the model's JSON schema with every $ref resolved in place."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].rsplit("/", 1)[-1]
                merged = {**resolve(defs[name]), **{k: v for k, v in node.items() if k != "$ref"}}
                return merged
            return {k: resolve(v) for k, v in node.items() if k not in ("title",)}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)


class OllamaClient:
    """Minimal Ollama API wrapper used by the discovery services."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.requested_model = model or settings.model
        self._resolved: str | None = None

    def _client(self, timeout: float | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=timeout or settings.llm_timeout)

    async def list_models(self) -> list[str]:
        """Return the names of models installed in Ollama."""
        try:
            async with self._client(timeout=5) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama is not reachable at {self.base_url}: {exc}") from exc
        return [m["name"] for m in response.json().get("models", [])]

    async def resolve_model(self) -> str:
        """Pick the configured model, or the best available one from the preference list."""
        if self._resolved:
            return self._resolved
        available = await self.list_models()
        if not available:
            raise OllamaError("Ollama has no models installed")
        names = {name: name for name in available}
        names.update({name.removesuffix(":latest"): name for name in available})
        if self.requested_model:
            match = names.get(self.requested_model) or names.get(self.requested_model.removesuffix(":latest"))
            if not match:
                raise OllamaError(f"model {self.requested_model!r} is not installed in Ollama")
            self._resolved = match
            return match
        for candidate in PREFERRED_MODELS:
            if candidate in names:
                self._resolved = names[candidate]
                return self._resolved
        self._resolved = available[0]
        return self._resolved

    async def health(self) -> dict[str, Any]:
        """Report reachability and the model that would be used."""
        try:
            models = await self.list_models()
            model = await self.resolve_model()
            return {"ok": True, "url": self.base_url, "model": model, "models": models}
        except OllamaError as exc:
            return {"ok": False, "url": self.base_url, "model": None, "models": [], "error": str(exc)}

    async def structured(
        self,
        schema: type[T],
        system: str,
        prompt: str,
        *,
        temperature: float = 0.4,
        retries: int = 1,
    ) -> T:
        """Ask the model for a JSON answer constrained to the given Pydantic schema."""
        model = await self.resolve_model()
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        payload = {
            "model": model,
            "messages": messages,
            "format": inline_schema(schema),
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 8192},
        }
        last_error: Exception | None = None
        for _ in range(retries + 1):
            try:
                async with self._client() as client:
                    response = await client.post("/api/chat", json=payload)
                    response.raise_for_status()
            except httpx.HTTPError as exc:
                raise OllamaError(f"Ollama request failed: {exc}") from exc
            content = response.json().get("message", {}).get("content", "")
            try:
                return schema.model_validate(json.loads(content))
            except (ValueError, ValidationError) as exc:
                last_error = exc
                payload["options"]["temperature"] = max(0.1, temperature - 0.2)
        raise OllamaError(f"model returned output that does not match the schema: {last_error}")
