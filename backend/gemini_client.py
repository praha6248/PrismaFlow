"""Gemini Developer API for structured generation with the user's own key."""

from typing import TypeVar

import httpx
from pydantic import BaseModel

from .ollama_client import inline_schema

T = TypeVar("T", bound=BaseModel)
MODEL = "gemini-flash-latest"
MODEL_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}"


class GeminiError(RuntimeError):
    """A user-visible error that contains no credentials or project content."""


async def request(key: str, payload: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=240 if payload is not None else 15,
                                     headers={"x-goog-api-key": key}) as client:
            if payload is None:
                response = await client.get(MODEL_URL)
            else:
                response = await client.post(f"{MODEL_URL}:generateContent", json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        message = {
            400: "Google rejected the request. Check the API key and request format.",
            401: "Check your Gemini API key.",
            403: "Check the API key and project permissions in Google AI Studio.",
            404: f"The model {MODEL} is unavailable for this project.",
            429: "Quota exceeded. Check the limits in Google AI Studio.",
        }.get(status, "Google could not complete the request.")
        raise GeminiError(f"Gemini API (HTTP {status}): {message}") from None
    except (httpx.HTTPError, ValueError):
        raise GeminiError("Gemini API: connection failed or response was invalid.") from None


def response_schema(model: type[BaseModel]) -> dict:
    """Keep Gemini's supported JSON Schema keywords and preserve property names."""
    def clean(node: dict) -> dict:
        allowed = ("type", "description", "enum", "required", "minimum", "maximum", "minItems", "maxItems")
        out = {key: node[key] for key in allowed if key in node}
        if "properties" in node:
            out["properties"] = {name: clean(field) for name, field in node["properties"].items()}
        if "items" in node:
            out["items"] = clean(node["items"])
        if "anyOf" in node:
            out["anyOf"] = [clean(option) for option in node["anyOf"]]
        if "additionalProperties" in node:
            extra = node["additionalProperties"]
            out["additionalProperties"] = clean(extra) if isinstance(extra, dict) else extra
        return out

    return clean(inline_schema(model))


async def structured(key: str, schema: type[T], system: str, prompt: str, temperature: float) -> T:
    data = await request(key, {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": response_schema(schema),
            "temperature": temperature,
        },
    })
    for candidate in data.get("candidates", []):
        if candidate.get("finishReason") == "STOP":
            parts = candidate.get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
            try:
                return schema.model_validate_json(text)
            except ValueError:
                continue
    raise GeminiError("Gemini API: the model did not return a complete answer matching the schema.")
