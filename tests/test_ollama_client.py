"""Model selection of the Ollama client, including task-specific fine-tunes."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

from backend.ollama_client import OllamaClient


def client(installed: list[str], model: str | None = None) -> OllamaClient:
    instance = OllamaClient(base_url="http://ollama.test", model=model)
    instance.requested_model = model

    async def list_models() -> list[str]:
        return installed

    instance.list_models = list_models
    return instance


def test_deliver_prefers_the_ux_fine_tune_when_installed() -> None:
    llm = client(["local/gemma3-12b:latest", "local/gemma3-4b-ux:latest", "local/gemma3-4b:latest"])
    assert asyncio.run(llm.model_for("deliver")) == "local/gemma3-4b-ux:latest"


def test_case_study_prefers_its_fine_tune_when_installed() -> None:
    llm = client(["local/gemma3-12b:latest", "local/gemma3-4b-ux:latest", "local/gemma3-4b-case:latest"])
    assert asyncio.run(llm.model_for("case_study")) == "local/gemma3-4b-case:latest"
    assert asyncio.run(client(["local/gemma3-12b:latest", "local/gemma3-4b-ux:latest"]).model_for("case_study")) == "local/gemma3-12b:latest"


def test_other_tasks_keep_the_general_preference() -> None:
    llm = client(["local/gemma3-12b:latest", "local/gemma3-4b-ux:latest"])
    assert asyncio.run(llm.model_for(None)) == "local/gemma3-12b:latest"
    assert asyncio.run(llm.model_for("discover")) == "local/gemma3-12b:latest"


def test_deliver_falls_back_without_the_fine_tune() -> None:
    llm = client(["local/gemma3-4b:latest", "local/gemma3-12b:latest"])
    assert asyncio.run(llm.model_for("deliver")) == "local/gemma3-12b:latest"


def test_explicit_model_overrides_the_task_preference() -> None:
    llm = client(["local/gemma3-4b-ux:latest", "local/gemma3-4b:latest"], model="local/gemma3-4b")
    assert asyncio.run(llm.model_for("deliver")) == "local/gemma3-4b:latest"


class Answer(BaseModel):
    ok: bool


def test_structured_sends_the_task_model(monkeypatch: Any) -> None:
    llm = client(["local/gemma3-12b:latest", "local/gemma3-4b-ux:latest"])
    sent: list[str] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"message": {"content": '{"ok": true}'}}

    class Session:
        async def __aenter__(self) -> "Session":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, path: str, json: dict[str, Any]) -> Response:
            sent.append(json["model"])
            return Response()

    monkeypatch.setattr(llm, "_client", lambda timeout=None: Session())
    assert asyncio.run(llm.structured(Answer, "s", "p", task="deliver")).ok
    assert asyncio.run(llm.structured(Answer, "s", "p")).ok
    assert sent == ["local/gemma3-4b-ux:latest", "local/gemma3-12b:latest"]
