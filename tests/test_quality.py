"""Tests for the optional Claude quality mode."""

from types import SimpleNamespace
from typing import Any

import anthropic
from pydantic import BaseModel

from backend.claude_client import HybridLLM, QualityConfig


class Answer(BaseModel):
    text: str


class Local:
    def __init__(self) -> None:
        self.calls = 0

    async def structured(self, schema: Any, system: str, prompt: str, **_: Any) -> Any:
        self.calls += 1
        return schema(text="local")


class FakeClaude:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.requests: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))

    async def parse(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        if self.fail:
            raise anthropic.APIConnectionError(request=None)
        return SimpleNamespace(stop_reason="end_turn", parsed_output=kwargs["output_format"](text="claude"))


def config(tmp_path, enabled: bool, key: str = "sk-test") -> QualityConfig:
    cfg = QualityConfig(tmp_path / "prismaflow.env")
    cfg.update(enabled=enabled, key=key)
    return cfg


async def test_quality_mode_routes_to_claude(tmp_path) -> None:
    claude, local = FakeClaude(), Local()
    llm = HybridLLM(local, config(tmp_path, True), client=claude)
    llm._client_key = "sk-test"
    assert (await llm.structured(Answer, "s", "p", temperature=0.3)).text == "claude"
    assert claude.requests[0]["model"] == "claude-opus-5-5" and "temperature" not in claude.requests[0]
    assert local.calls == 0


async def test_falls_back_to_local_when_off_or_failing(tmp_path) -> None:
    local = Local()
    off = HybridLLM(local, config(tmp_path, False), client=FakeClaude())
    assert (await off.structured(Answer, "s", "p")).text == "local"
    failing = HybridLLM(local, config(tmp_path, True), client=FakeClaude(fail=True))
    failing._client_key = "sk-test"
    assert (await failing.structured(Answer, "s", "p")).text == "local"
    assert failing.last_error


def test_key_is_persisted_privately_and_never_shown(tmp_path) -> None:
    cfg = config(tmp_path, True, "sk-secret")
    path = tmp_path / "prismaflow.env"
    assert "PRISMAFLOW_ANTHROPIC_API_KEY=sk-secret" in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600
    assert "sk-secret" not in str(cfg.public())
    assert cfg.update(key="")["enabled"] is False
    assert "sk-secret" not in path.read_text()
