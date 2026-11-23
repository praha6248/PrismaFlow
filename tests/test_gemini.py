import httpx
import pytest
from fastapi.testclient import TestClient

from backend import gemini_client
from backend.api import create_app
from backend.claude_client import HybridLLM, QualityConfig
from backend.database import Database
from tests.test_quality import Answer, Local


async def test_gemini_posts_schema_and_parses_output(tmp_path, monkeypatch):
    cfg = QualityConfig(tmp_path / "settings.env")
    cfg.update(provider="gemini", enabled=True, key="test-key")
    local = Local()
    async def fake_request(key, payload):
        assert key == "test-key"
        assert payload["generationConfig"]["responseJsonSchema"]["required"] == ["text"]
        assert payload["contents"][0]["parts"] == [{"text": "example"}]
        return {"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"thought": True, "text": "ignore"}, {"text": '{"text":"ok"}'}]}}]}
    monkeypatch.setattr(gemini_client, "request", fake_request)
    llm = HybridLLM(local, cfg)
    assert (await llm.structured(Answer, "system", "example")).text == "ok"
    assert llm.embed is None and local.calls == 0


def test_provider_settings_and_setup_without_ollama(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for name in ("PRISMAFLOW_PROVIDER", "PRISMAFLOW_QUALITY_MODE", "PRISMAFLOW_GEMINI_API_KEY", "PRISMAFLOW_ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    async def check(key):
        if key != "gemini-test":
            raise gemini_client.GeminiError("Gemini API: invalid key")
        return {"name": "models/example"}
    monkeypatch.setattr(gemini_client, "request", check)
    with TestClient(create_app(db=Database(":memory:"))) as client:
        def select(provider, key=None):
            body = {"provider": provider, "enabled": True}
            if key is not None:
                body["key"] = key
            return client.put("/api/settings/quality", json=body)
        select("claude", "claude-test")
        saved = select("gemini", "gemini-test").json()
        assert saved["provider"] == "gemini" and saved["has_key"] and saved["has_gemini_key"]
        assert "gemini-test" not in str(saved)
        assert client.get("/api/setup").json()["ready"]
        assert select("gemini", "wrong").status_code == 400
        assert select("local").json()["provider"] == "local"
        assert select("gemini").json()["provider"] == "gemini"
        assert client.put("/api/settings/quality", json={"provider": "gemini", "enabled": False, "key": ""}).json()["has_key"]
        assert select("claude").json()["provider"] == "claude"


async def test_google_errors_never_expose_the_key(monkeypatch):
    original = httpx.AsyncClient
    def reject(req):
        assert req.headers["x-goog-api-key"] == "secret-test"
        return httpx.Response(429, json={"error": "secret-test"})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(reject), **kw))
    with pytest.raises(gemini_client.GeminiError, match="429") as error:
        await gemini_client.request("secret-test")
    assert "secret-test" not in str(error.value)
