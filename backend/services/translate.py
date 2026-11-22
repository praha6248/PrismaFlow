"""Batch translation of short texts with the local LLM."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, create_model

from ..ollama_client import OllamaError

TRANSLATE_SYSTEM = """You are a precise translator. Translate every numbered line into {target}.
Keep the meaning, tone and brand names, write natural everyday {target}, do not add explanations.
Return the translations in the same order, exactly one per input line."""


def _schema(count: int) -> type[BaseModel]:
    return create_model(
        "Translations",
        items=(list[str], Field(json_schema_extra={"minItems": count, "maxItems": count})),
    )


async def translate(llm: Any, texts: list[str], target: str, chunk: int = 25) -> list[str]:
    """Translate texts into the target language, returning the originals for anything that fails."""
    results = list(texts)
    for start in range(0, len(texts), chunk):
        batch = texts[start : start + chunk]
        if not batch:
            continue
        prompt = "\n".join(f"{i + 1}. {text}" for i, text in enumerate(batch))
        try:
            answer = await llm.structured(
                _schema(len(batch)), TRANSLATE_SYSTEM.format(target=target), prompt, temperature=0.1
            )
        except OllamaError:
            continue
        items = [str(item).strip() for item in answer.items]
        if len(items) != len(batch):
            continue
        for offset, item in enumerate(items):
            if item:
                results[start + offset] = item.removeprefix(f"{offset + 1}.").strip()
    return results
