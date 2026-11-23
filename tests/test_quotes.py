"""Forum quotes pasted by the user as evidence, and richer flow elements."""

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.database import Database
from backend.models import Flow, FlowElement, FlowScreen
from backend.services import discover
from backend.services.define import pasted
from backend.services.deliver import audit, choice_sets
from backend.services.quotes import quote_notes, split_quotes

from .conftest import FakeLLM


def _client(tmp_path) -> tuple[TestClient, Database]:
    db = Database(":memory:")
    llm = FakeLLM()
    app = create_app(db=db, llm=llm, service=discover.DiscoverService(db, llm), frontend_dist=tmp_path)
    return TestClient(app), db


def test_split_quotes_by_paragraph_or_line() -> None:
    text = "„Podlewam ręcznie co wieczór, bo nie ufam automatom.”\n\nza krótkie\n\nSystem kropelkowy kosztował za dużo jak na działkę."
    assert split_quotes(text) == ["Podlewam ręcznie co wieczór, bo nie ufam automatom.", "System kropelkowy kosztował za dużo jak na działkę."]
    lines = "I water by hand every evening now.\nThe drip kit was far too expensive for me."
    assert len(split_quotes(lines)) == 2
    wrapped = "This is one long post that\nwraps over two lines"
    assert split_quotes(wrapped + "\n\nAnd a second post with enough words") == ["This is one long post that wraps over two lines", "And a second post with enough words"]


def test_pasted_quotes_become_community_evidence(tmp_path) -> None:
    client, db = _client(tmp_path)
    with client:
        project_id = client.post("/api/projects", json={"seed": "ogród"}).json()["project"]["id"]
        added = client.post(
            f"/api/projects/{project_id}/quotes",
            json={"text": "Podlewam ręcznie co wieczór, bo nie ufam automatom.", "url": "https://www.reddit.com/r/ogrod/1"},
        ).json()
        assert added["added"] == 1
        quote = added["quotes"][0]
        assert quote["source"] == "community" and quote["meta"]["platform"] == "reddit.com" and pasted(quote)
        again = client.post(f"/api/projects/{project_id}/quotes", json={"text": "Podlewam ręcznie co wieczór, bo nie ufam automatom."}).json()
        assert again["added"] == 0
        assert client.post(f"/api/projects/{project_id}/quotes", json={"text": "za krótko"}).status_code == 400
        assert quote_notes(db, project_id) == [{"text": quote["body"], "source": "forum", "label": "reddit.com"}]
        assert client.delete(f"/api/projects/{project_id}/quotes/{quote['id']}").json()["quotes"] == []
        assert client.post("/api/projects/999/quotes", json={"text": "Podlewam ręcznie co wieczór, bo nie ufam"}).status_code == 404


def test_named_options_set_the_choice_count() -> None:
    element = FlowElement(id="e1", label="Kolor", type="radio", items=["Czerwony", " ", "Zielony", "Niebieski"])
    assert element.items == ["Czerwony", "Zielony", "Niebieski"] and element.options == 3
    screen = FlowScreen(
        id="s1",
        name="Start",
        kind="start",
        elements=[element, FlowElement(id="e2", label="Opis", type="text", size="S"), FlowElement(id="e3", label="Dalej", size="L")],
    )
    assert {"element_id": "e1", "element": "Kolor", "options": 3} in choice_sets(screen)
    targets = audit(Flow(screens=[screen]))["targets"]
    assert targets["total"] == 2
