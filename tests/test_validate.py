"""Tests for the Validate step: plan, interview verdicts and hypothesis statuses."""

from typing import Any

from backend.database import Database
from backend.services.validate import ValidateService, hypothesis_status, quote_in_notes, validated_insights

from .test_define import SchemaLLM, _noop
from .test_develop import _defined

PLAN = {
    "hypotheses": [
        {"kind": "problem", "text": "Ludzie porzucają plan po tygodniu", "signal": "Opowiada o porzuconym planie"},
        {"kind": "workaround", "text": "Używają notatek w telefonie", "signal": "Pokazuje notatki"},
        {"kind": "willingness", "text": "Zapłacą 20 zł miesięcznie", "signal": "Płaci już za podobną aplikację"},
    ],
    "screener": ["Ile razy ćwiczyłeś w ostatnim miesiącu?", "Czy masz plan treningowy?", "Jak go zapisujesz?"],
    "questions": [
        "Opowiedz o ostatnim razie, gdy przestałeś ćwiczyć.",
        "Co wtedy zrobiłeś?",
        "Jak teraz planujesz treningi?",
        "Ile czasu ci to zajmuje?",
        "Za jakie aplikacje płacisz?",
        "Co próbowałeś wcześniej?",
    ],
}

NOTES = "Marek mówi: w marcu rzuciłem plan po tygodniu, bo praca. Treningi zapisuję w notatkach w telefonie. Nie płacę za żadne aplikacje i nie zamierzam."


class ValidateLLM(SchemaLLM):
    def __init__(self, analysis: dict[str, Any]) -> None:
        super().__init__()
        self.analysis = analysis

    async def structured(self, schema: Any, system: str, prompt: str, **kwargs: Any) -> Any:
        if schema.__name__ == "ValidationPlanDraft":
            return schema.model_validate(PLAN)
        if schema.__name__ == "InterviewAnalysis":
            return schema.model_validate(self.analysis)
        return await super().structured(schema, system, prompt, **kwargs)


def test_helpers() -> None:
    assert quote_in_notes("„rzuciłem plan po tygodniu”", NOTES)
    assert not quote_in_notes("zawsze trzymam się planu", NOTES)
    assert hypothesis_status(3, 0) == "confirmed" and hypothesis_status(3, 2) == "open"
    assert hypothesis_status(0, 2) == "rejected" and hypothesis_status(1, 1) == "open"


async def test_interviews_need_verbatim_quotes_and_repetition(db: Database) -> None:
    analysis = {
        "summary": "Plan pada przez pracę.",
        "verdicts": [
            {"hypothesis": 1, "verdict": "supports", "quote": "rzuciłem plan po tygodniu, bo praca"},
            {"hypothesis": 2, "verdict": "supports", "quote": "używam aplikacji Notion do planów"},
            {"hypothesis": 3, "verdict": "contradicts", "quote": "Nie płacę za żadne aplikacje"},
        ],
    }
    llm = ValidateLLM(analysis)
    project_id = await _defined(db, llm)
    service = ValidateService(db, llm)
    state = await service.plan(project_id, _noop, _noop)
    assert len(state["hypotheses"]) == 3 and len(state["questions"]) == 6

    for person in ("Marek", "Ola", "Kuba"):
        state = await service.add_interview(project_id, person, NOTES)
    first, second, third = state["hypotheses"]
    assert first["supports"] == 3 and first["status"] == "confirmed"
    assert second["supports"] == 0 and second["status"] == "open"
    assert third["contradicts"] == 3 and third["status"] == "rejected"
    assert state["progress"] == {"interviews": 3, "confirmed": 1, "rejected": 1}
    assert validated_insights(db, project_id)[0].startswith("CONFIRMED (3 interviews)")

    state = service.remove_interview(project_id, state["interviews"][0]["id"])
    assert state["hypotheses"][0]["status"] == "open"
