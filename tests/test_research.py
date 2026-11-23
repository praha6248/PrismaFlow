"""Tests for the affinity board, empathy map, RICE, usability tests and the research report."""

from typing import Any

from backend.database import Database
from backend.services.define import DefineService
from backend.services.develop import confidence, develop_state, rice
from backend.services.report import markdown_html, prototype_svg, report_markdown
from backend.services.research import ResearchService, board_lines, real_notes, split_notes
from backend.models import short_phrase
from backend.services.usability import UsabilityService, addresses_participant, deviation, optimal_path

from .test_define import SchemaLLM, _noop, define_collectors
from .test_deliver import sample_flow
from .test_develop import _defined

EMPATHY = {
    "says": [
        {"text": "Nie mam czasu na długi trening", "note": 1},
        {"text": "Zaczynam każdy poniedziałek z ogromnym zapałem, ale po kilku dniach praca i dom zabierają mi cały wolny czas", "note": 0},
    ],
    "thinks": [{"text": "Znowu odpuszczę", "note": 0}, {"text": "Inni dają radę", "note": 99}],
    "does": [{"text": "Zapisuje treningi w notatkach", "note": 2}, {"text": "Ćwiczy wieczorem", "note": 0}],
    "feels": [{"text": "Wstyd po przerwie", "note": 1}, {"text": "Zmęczenie", "note": 0}],
    "journey": [
        {"phase": "after", "name": "Przerwa", "action": "Opuszcza tydzień treningów", "thought": "Już po planie", "emotion": -5, "pain": "Trudno wrócić"},
        {"phase": "before", "name": "Postanowienie", "action": "Wybiera plan w internecie", "thought": "Tym razem się uda", "emotion": 2},
        {"phase": "during", "name": "Pierwszy tydzień", "action": "Ćwiczy trzy razy", "thought": "Idzie dobrze", "emotion": 1},
        {"phase": "during", "name": "Nadgodziny", "action": "Przesuwa trening", "thought": "Nie zdążę", "emotion": -1, "pain": "Sztywny plan"},
        {"phase": "after", "name": "Powrót", "action": "Szuka nowego planu", "thought": "Od nowa", "emotion": 0},
    ],
    "hmw": ["Jak moglibyśmy ułatwić powrót po przerwie?", "Jak moglibyśmy dopasować plan do nadgodzin?", "Jak moglibyśmy zmniejszyć wstyd?"],
}


class ResearchLLM(SchemaLLM):
    async def structured(self, schema: Any, system: str, prompt: str, **kwargs: Any) -> Any:
        if schema.__name__ == "AffinityDraft":
            self.prompts.append(prompt)
            return schema.model_validate(
                {
                    "themes": [{"name": "Brak czasu", "insight": "Praca wypiera trening.", "notes": [1, 2, 1, 4]}, {"name": "Powroty", "insight": "Przerwa kończy plan.", "notes": [3]}],
                    "off_topic": [1, 4],
                }
            )
        if schema.__name__ == "ShortTexts":
            count = len([line for line in prompt.splitlines() if line.strip()])
            return schema.model_validate({"items": [f"Krótko {i}" for i in range(count)]})
        if schema.__name__ == "EmpathyDraft":
            self.prompts.append(prompt)
            return schema.model_validate(EMPATHY)
        if schema.__name__ == "TaskSet":
            self.task_calls = getattr(self, "task_calls", 0) + 1
            if self.task_calls == 1:
                return schema.model_validate({"tasks": [{"goal": "s3", "scenario": "Marta chce zacząć dzisiejszy trening."}]})
            return schema.model_validate({"tasks": [{"goal": "s3", "scenario": "Masz wolny wieczór i chcesz zacząć dzisiejszy trening."}]})
        return await super().structured(schema, system, prompt, **kwargs)


def test_split_notes() -> None:
    assert split_notes("- pierwsza\n- druga\n\n") == ["pierwsza", "druga"]
    assert split_notes("akapit jeden\nciąg dalszy\n\nakapit dwa") == ["akapit jeden ciąg dalszy", "akapit dwa"]


async def test_board_groups_notes_and_feeds_problems(db: Database) -> None:
    llm = ResearchLLM()
    project_id = await _defined(db, llm)
    service = ResearchService(db, llm)
    board = service.board(project_id)
    assert board["notes"] and all(n["source"] == "evidence" for n in board["notes"])
    service.add_notes(project_id, "Rzucam plan, gdy mam nadgodziny\n\nNotatki w telefonie wystarczają", "interview", "Ola")
    service.add_notes(project_id, "Wracam po przerwie z poczuciem winy", "note", "")
    before = len(service.board(project_id)["notes"])
    state = await service.cluster(project_id, _noop, _noop)
    assert [t["name"] for t in state["themes"]] == ["Brak czasu", "Powroty"]
    first, second = state["themes"]
    assert [n["theme"] for n in state["notes"][:3]] == [first["id"], first["id"], second["id"]]
    assert state["dropped"] == 1 and len(state["notes"]) == before - 1
    note = state["notes"][2]["id"]
    state = service.move_note(project_id, note, first["id"])
    assert state["notes"][2]["theme"] == first["id"]
    state = service.remove_theme(project_id, second["id"])
    assert len(state["themes"]) == 1
    assert board_lines(db, project_id)[0].startswith("- Brak czasu (3 notes)")
    assert {n["text"] for n in real_notes(db, project_id)} >= {"Rzucam plan, gdy mam nadgodziny"}

    await DefineService(db, llm, define_collectors()).generate_problems(project_id, _noop, _noop)
    prompt = [p for p in llm.prompts if "Return exactly three problem statements" in p][-1]
    assert "affinity board" in prompt and "Brak czasu" in prompt


async def test_personas_reuse_quotes_from_notes(db: Database) -> None:
    llm = ResearchLLM()
    project_id = await _defined(db, llm)
    ResearchService(db, llm).add_notes(project_id, "Mam mało czasu.", "interview", "Ola")
    state = await DefineService(db, llm, define_collectors()).generate_personas(project_id, _noop, _noop)
    assert "Notes from real people" in llm.prompts[-1]
    karolina = next(p for p in state["personas"] if p["name"] == "Karolina")
    assert karolina["profile"]["quote_source"] == "note:Ola" or karolina["profile"]["quote_source"].startswith("interview")
    assert "quote_source" not in next(p for p in state["personas"] if p["name"] == "Julia")["profile"]


async def test_empathy_map_links_items_to_notes_and_frames_develop(db: Database) -> None:
    llm = ResearchLLM()
    project_id = await _defined(db, llm)
    service = ResearchService(db, llm)
    service.add_notes(project_id, "Nie mam czasu na długi trening\n\nZapisuję treningi w notatkach", "interview", "Ola")
    state = await service.generate_empathy(project_id, _noop, _noop)
    data = state["map"]
    assert data["says"][0]["from"]["text"] == "Nie mam czasu na długi trening" and data["says"][1]["from"] is None
    assert data["says"][0]["text"] == "Nie mam czasu na długi trening" and data["says"][1]["text"] == "Krótko 0"
    assert data["thinks"][1]["from"] is None
    assert [s["phase"] for s in data["journey"]] == ["before", "during", "during", "after", "after"]
    assert data["journey"][3]["emotion"] == -2
    assert data["hmw_chosen"] == EMPATHY["hmw"][0]
    state = service.choose_hmw(project_id, "Jak moglibyśmy skrócić trening do 15 minut?")
    assert state["map"]["hmw_chosen"] in state["map"]["hmw"]
    assert develop_state(db, project_id)["hmw"] == "Jak moglibyśmy skrócić trening do 15 minut?"


def test_short_texts_and_second_person() -> None:
    assert short_phrase("Sprawdza pogodę codziennie.") == "Sprawdza pogodę codziennie"
    assert short_phrase("jeden dwa trzy cztery pięć sześć siedem, osiem dziewięć dziesięć jedenaście", 8) == "jeden dwa trzy cztery pięć sześć siedem"
    assert addresses_participant("Masz wolny wieczór i chcesz ćwiczyć.", "pl")
    assert not addresses_participant("Marta chce ćwiczyć wieczorem.", "pl", "Marta")
    assert not addresses_participant("Chce zobaczyć wynik.", "pl")
    assert addresses_participant("You want to train tonight.", "en")


def test_rice_scores() -> None:
    assert confidence({"support": 0}, True) == 0.5
    assert confidence({"support": 2}, False) == 0.8 and confidence({"support": 2}, True) == 1.0
    score = rice({"support": 4, "impact": 2, "effort": 2}, False)
    assert score == {"reach": 4, "impact": 2.0, "confidence": 1.0, "effort": 2.0, "score": 4.0}


async def test_usability_sessions_reveal_issues(db: Database) -> None:
    llm = ResearchLLM()
    project_id = await _defined(db, llm)
    flow = sample_flow()
    db.save_flow(project_id, flow.model_dump())
    assert optimal_path(flow, "s3") == ["s1", "s2", "s3"]
    assert deviation(["s1", "s4"], ["s1", "s2", "s3"]) == "s1" and deviation(["s1", "s2", "s3"], ["s1", "s2", "s3"]) is None
    service = UsabilityService(db, llm)
    state = await service.plan(project_id, _noop, _noop)
    task = state["tasks"][0]
    assert task["goal"] == "s3" and task["scenario"].startswith("Masz wolny wieczór") and llm.task_calls == 2
    misses = [{"screen": "s4", "element": "Język"}, {"screen": "s4", "element": "Język"}]
    service.add_session(project_id, "Ola", [{"task": task["id"], "success": False, "seconds": 40, "path": ["s1", "s4"], "misclicks": misses, "quote": "Myślałam, że plan jest w ustawieniach"}])
    service.add_session(project_id, "Jan", [{"task": task["id"], "success": True, "seconds": 30, "path": ["s1", "s2", "s3"], "misclicks": [], "quote": ""}])
    state = service.state(project_id)
    summary = state["tasks"][0]
    assert summary["attempts"] == 2 and summary["successes"] == 1 and summary["seconds"] == 30
    kinds = {i["kind"] for i in state["issues"]}
    assert kinds == {"success", "slow", "detour", "misclick"}
    miss = next(i for i in state["issues"] if i["kind"] == "misclick")
    assert miss == {"kind": "misclick", "task": "Trening", "screen": "Ustawienia", "element": "Język", "count": 1}
    assert summary["misclicks"] == 1.0
    assert next(i for i in state["issues"] if i["kind"] == "detour")["screen"] == "Start"


async def test_report_and_svg(db: Database) -> None:
    llm = ResearchLLM()
    project_id = await _defined(db, llm)
    project = db.get_project(project_id)
    flow = sample_flow()
    markdown = report_markdown(
        {
            "project": project,
            "problem": {"title": "Porzucanie planu", "description": "Ludzie rzucają plan."},
            "persona": db.chosen_persona(project_id),
            "board": {"themes": [{"id": "t1", "name": "Brak czasu", "insight": "Praca wypiera trening."}], "notes": [{"theme": "t1", "source": "note", "text": "nadgodziny"}]},
            "empathy": {**EMPATHY, "says": [{"text": "Brak czasu", "from": None}], "journey": [], "hmw_chosen": "Jak moglibyśmy pomóc?"},
            "features": [{"priority": "must", "title": "Plan", "description": "Elastyczny", "rice": {"score": 4, "reach": 4, "impact": 2, "confidence": 1, "effort": 2}}],
            "flow": flow.model_dump(),
            "tests": {"tasks": [], "participants": 0},
        }
    )
    assert "## Tematy z tablicy" in markdown and "wniosek modelu" in markdown and "RICE 4" in markdown
    page = markdown_html(markdown, "Sport")
    assert "<h2>Mapa empatii</h2>" in page and "<ul>" in page
    svg = prototype_svg(flow, {"primary": "#123456"})
    assert svg.startswith("<svg") and svg.count('rx="32"') == 5 and "#123456" in svg
