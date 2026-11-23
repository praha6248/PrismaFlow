from backend.services.setup import setup_status


def test_missing_ollama_is_not_ready():
    status = setup_status(False, [], "http://127.0.0.1:11434", 32, "")
    assert not status["ready"]
    assert status["ollama"]["download"].startswith("https://ollama.com")


def test_small_machine_gets_the_4b_model():
    status = setup_status(True, [], "u", 8, "")
    chat = status["models"][0]
    assert chat["name"] == "gemma3:4b"
    assert chat["command"] == "ollama pull gemma3:4b"
    assert not status["ready"]


def test_any_supported_chat_model_counts_as_ready():
    status = setup_status(True, ["local/gemma3-4b:latest", "bge-m3:latest"], "u", 32, "")
    assert status["ready"]
    assert all(m["installed"] for m in status["models"])


def test_ux_model_listed_only_when_repo_is_known():
    assert [m["id"] for m in setup_status(True, [], "u", 32, "")["models"]] == ["chat", "embed"]
    ux = setup_status(True, [], "u", 32, "someone/model-GGUF")["models"][-1]
    assert ux["source"] == "https://huggingface.co/someone/model-GGUF"
    assert "ollama pull hf.co/someone/model-GGUF" in ux["command"]
