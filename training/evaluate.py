"""Evaluate models on the held-out set through the app's real OllamaClient.structured path.

Metrics for Deliver optimisation (SuggestionSet): schema validity, valid-reference rate, audit
issues before and after applying the suggestions, dead-end and Fitts/WCAG fix rates, latency.
Flow design (FlowDraft) is scored on structure rules and the audit of the resulting flow.
A multiple-choice UX quiz checks factual knowledge. Results go to out/eval_<model>.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import statistics
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

os.environ.setdefault("OLLAMA_HOST", "100.89.78.124:11434")

from flows import ROOT, apply_all, audit, draft_metrics, resolve

from backend.models import Flow, FlowDraft, SuggestionSet
from backend.ollama_client import OllamaClient, OllamaError

OUT = ROOT / "out"

QUIZ = [
    ("Jaki minimalny rozmiar celu dotykowego wymaga WCAG 2.2 SC 2.5.8 (poziom AA)?", "24 × 24 px CSS", ["44 × 44 px CSS", "48 × 48 px CSS", "16 × 16 px CSS"]),
    ("Jaki rozmiar celu wymaga WCAG SC 2.5.5 Target Size (Enhanced, AAA)?", "44 × 44 px CSS", ["24 × 24 px CSS", "32 × 32 px CSS", "60 × 60 px CSS"]),
    ("Jaki minimalny cel dotykowy zaleca Material Design?", "48 × 48 dp", ["32 × 32 dp", "40 × 40 dp", "64 × 64 dp"]),
    ("Jaki minimalny obszar dotyku zalecają Apple Human Interface Guidelines?", "44 × 44 pt", ["30 × 30 pt", "50 × 50 pt", "24 × 24 pt"]),
    ("Zgodnie z prawem Fittsa czas wskazania celu rośnie, gdy…", "cel jest mniejszy lub dalej", ["cel jest większy", "cel jest bliżej kciuka", "ekran jest jaśniejszy"]),
    ("Prawo Hicka–Hymana mówi, że czas decyzji rośnie wraz z liczbą opcji…", "logarytmicznie", ["liniowo", "wykładniczo", "nie zależy od liczby opcji"]),
    ("Ile wynosi typowy czas operatora M (przygotowanie mentalne) w modelu KLM?", "około 1,35 s", ["około 0,2 s", "około 3 s", "około 0,05 s"]),
    ("Gdzie na telefonie trzymanym jedną ręką najłatwiej sięgnąć kciukiem?", "w dolnej, środkowej części ekranu", ["w górnym lewym rogu", "w górnym prawym rogu", "na samej górze pośrodku"]),
    ("Którą heurystykę Nielsena łamie ekran bez wyjścia (ślepa uliczka)?", "Kontrola i swoboda użytkownika", ["Estetyka i minimalizm", "Elastyczność i efektywność", "Pomoc i dokumentacja"]),
    ("Ile elementów według Millera (1956) mieści się zwykle w pamięci krótkotrwałej?", "7 ± 2", ["3 ± 1", "12 ± 3", "20 ± 5"]),
    ("Jaki minimalny kontrast tekstu zwykłego wymaga WCAG 1.4.3 (AA)?", "4,5:1", ["3:1", "7:1", "2:1"]),
    ("Jaki minimalny kontrast dużego tekstu wymaga WCAG 1.4.3 (AA)?", "3:1", ["4,5:1", "7:1", "1,5:1"]),
    ("Jaki kontrast wymaga WCAG 1.4.11 dla elementów nietekstowych (np. obramowanie pola)?", "3:1", ["4,5:1", "7:1", "nie ma wymogu"]),
    ("Jaka jest kolejność faz Double Diamond (Design Council)?", "Discover, Define, Develop, Deliver", ["Define, Discover, Deliver, Develop", "Develop, Define, Discover, Deliver", "Discover, Develop, Define, Deliver"]),
    ("Co oznacza litera W w metodzie MoSCoW?", "Won't have (tym razem nie)", ["Wish to have", "Weighted", "Work in progress"]),
    ("Jak najlepiej naprawić ekran, z którego nie da się przejść dalej?", "dodać wyraźne przejście do kolejnego kroku lub celu", ["powiększyć nagłówek", "dodać więcej opcji", "usunąć ekran startowy"]),
    ("Na czym polega stopniowe ujawnianie (progressive disclosure)?", "zaawansowane opcje pokazuje się dopiero na żądanie", ["wszystkie opcje są widoczne od razu", "treść ładuje się wolniej", "użytkownik musi się zalogować"]),
    ("Którego kryterium WCAG dotyczy widoczny wskaźnik fokusu klawiatury?", "2.4.7 Focus Visible", ["1.1.1 Non-text Content", "3.1.1 Language of Page", "2.5.8 Target Size"]),
    ("Ilu ewaluatorów zaleca Nielsen do oceny heurystycznej?", "3–5", ["1", "10–15", "co najmniej 30"]),
    ("Ile pytań ma kwestionariusz SUS (System Usability Scale)?", "10", ["5", "20", "7"]),
    ("Jaki powinien być dobry komunikat błędu według heurystyk Nielsena?", "prosty język, konkretny problem i sposób naprawy", ["kod błędu i numer wersji", "tylko czerwony kolor pola", "ogólne „Coś poszło nie tak”"]),
    ("Co mówi zasada bliskości (Gestalt)?", "elementy blisko siebie postrzegamy jako grupę", ["jasne elementy wydają się bliżej", "symetria zwiększa zaufanie", "ruch przyciąga uwagę"]),
    ("Dlaczego placeholder nie powinien zastępować etykiety pola?", "znika po wpisaniu tekstu i często ma słaby kontrast", ["jest zawsze za duży", "nie działa na telefonach", "WCAG zabrania pól tekstowych"]),
    ("Czego wymaga WCAG 2.2 SC 2.5.7 Dragging Movements?", "alternatywy jednym wskazaniem dla przeciągania", ["animacji podczas przeciągania", "przeciągania dwoma palcami", "zakazu list sortowanych"]),
    ("Czego wymaga WCAG 2.2 SC 3.3.8 Accessible Authentication (Minimum)?", "logowania bez testu funkcji poznawczych, np. z wklejaniem hasła", ["logowania biometrycznego", "haseł dłuższych niż 12 znaków", "CAPTCHA przy każdym logowaniu"]),
    ("Przy jakiej szerokości treść musi się przełamać bez przewijania w poziomie (WCAG 1.4.10 Reflow)?", "320 px CSS", ["1024 px CSS", "480 px CSS", "200 px CSS"]),
]

QUIZ_SYSTEM = "Jesteś ekspertem UX/UI i dostępności. Wybierz jedną poprawną odpowiedź."


class QuizAnswer(BaseModel):
    """Single choice answer."""

    answer: Literal["A", "B", "C", "D"]


def load(name: str) -> list[dict]:
    path = ROOT / "data" / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def findings(report: dict) -> tuple[int, int]:
    """Count dead ends and Fitts/WCAG findings of an audit report."""
    fitts = {(f["screen_id"], f["element_id"]) for f in report["fitts"]}
    wcag = {(t["screen_id"], t["element_id"]) for t in report["targets"]["below_aaa"] if t["primary"]}
    return len(report["dead_ends"]), len(fitts | wcag)


async def run_optimize(client: OllamaClient, item: dict) -> dict:
    system, prompt = item["messages"][0]["content"], item["messages"][1]["content"]
    flow = Flow.model_validate(item["flow"])
    before = audit(flow)
    dead_before, fw_before = findings(before)
    started = time.perf_counter()
    try:
        answer = await client.structured(SuggestionSet, system, prompt, temperature=0.3)
    except OllamaError as exc:
        return {"valid": False, "latency": time.perf_counter() - started, "error": str(exc)[:200],
                "issues_before": before["issues"], "issues_after": before["issues"],
                "dead_before": dead_before, "dead_after": dead_before, "fw_before": fw_before, "fw_after": fw_before, "raw": 0, "resolved": 0}
    latency = time.perf_counter() - started
    resolved = resolve(flow, answer)
    after = audit(apply_all(flow, resolved))
    dead_after, fw_after = findings(after)
    return {
        "valid": True, "latency": latency, "raw": len(answer.suggestions), "resolved": len(resolved),
        "issues_before": before["issues"], "issues_after": after["issues"],
        "dead_before": dead_before, "dead_after": dead_after, "fw_before": fw_before, "fw_after": fw_after,
        "answer": answer.model_dump(),
    }


async def run_flow(client: OllamaClient, item: dict) -> dict:
    system, prompt = item["messages"][0]["content"], item["messages"][1]["content"]
    started = time.perf_counter()
    try:
        draft = await client.structured(FlowDraft, system, prompt, temperature=0.4)
    except OllamaError as exc:
        return {"valid": False, "latency": time.perf_counter() - started, "error": str(exc)[:200]}
    return {"valid": True, "latency": time.perf_counter() - started, **draft_metrics(draft, item["features"]), "answer": draft.model_dump()}


async def run_quiz(client: OllamaClient) -> list[dict]:
    rng = random.Random(3)
    rows = []
    for question, correct, wrong in QUIZ:
        options = [correct, *wrong]
        rng.shuffle(options)
        letter = "ABCD"[options.index(correct)]
        text = question + "\n" + "\n".join(f"{'ABCD'[i]}. {o}" for i, o in enumerate(options))
        try:
            answer = await client.structured(QuizAnswer, QUIZ_SYSTEM, text, temperature=0.0)
            rows.append({"question": question, "correct": answer.answer == letter})
        except OllamaError:
            rows.append({"question": question, "correct": False})
    return rows


def rate(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def summary(optimize: list[dict], flows: list[dict], quiz: list[dict], gold: list[dict]) -> dict:
    """Aggregate per-example results."""
    valid = [r for r in optimize if r["valid"]]
    before = sum(r["issues_before"] for r in optimize)
    after = sum(r["issues_after"] for r in optimize)
    fvalid = [r for r in flows if r["valid"]]
    return {
        "optimize": {
            "n": len(optimize),
            "schema_valid": rate(len(valid), len(optimize)),
            "valid_reference": rate(sum(r["resolved"] for r in valid), sum(r["raw"] for r in valid)),
            "suggestions_per_answer": round(statistics.mean(r["raw"] for r in valid), 2) if valid else None,
            "issues_before": round(before / len(optimize), 2),
            "issues_after": round(after / len(optimize), 2),
            "issue_reduction": rate(before - after, before),
            "gold_issue_reduction": rate(sum(g["issues_before"] - g["issues_gold"] for g in gold), sum(g["issues_before"] for g in gold)),
            "improved_share": rate(sum(1 for r in optimize if r["issues_after"] < r["issues_before"]), len(optimize)),
            "dead_end_fix": rate(sum(r["dead_before"] - r["dead_after"] for r in optimize), sum(r["dead_before"] for r in optimize)),
            "fitts_wcag_fix": rate(sum(r["fw_before"] - r["fw_after"] for r in optimize), sum(r["fw_before"] for r in optimize)),
            "latency_s": round(statistics.mean(r["latency"] for r in optimize), 2),
        },
        "flow": {
            "n": len(flows),
            "schema_valid": rate(len(fvalid), len(flows)),
            "structure_ok": rate(sum(1 for r in fvalid if r["screens_ok"] and r["one_start_goal"] and r["targets_valid"]), len(flows)),
            "goal_reachable": rate(sum(1 for r in fvalid if r["goal_reachable"]), len(flows)),
            "must_coverage": round(statistics.mean(r["must_coverage"] for r in fvalid), 3) if fvalid else None,
            "issues": round(statistics.mean(r["issues"] for r in fvalid), 2) if fvalid else None,
            "dead_ends": round(statistics.mean(r["dead_ends"] for r in fvalid), 2) if fvalid else None,
            "latency_s": round(statistics.mean(r["latency"] for r in flows), 2),
        },
        "quiz": {"n": len(quiz), "accuracy": rate(sum(1 for r in quiz if r["correct"]), len(quiz))},
    }


async def main(model: str, limit: int | None) -> None:
    test = load("test.jsonl")
    optimize_items = [t for t in test if t["task"] == "optimize"][:limit]
    flow_items = [t for t in test if t["task"] == "flow"][:limit]
    client = OllamaClient(model=model)
    await client.resolve_model()
    optimize, flows = [], []
    for index, item in enumerate(optimize_items, 1):
        optimize.append(await run_optimize(client, item))
        print(f"optimize {index}/{len(optimize_items)} issues {optimize[-1]['issues_before']}->{optimize[-1]['issues_after']}", flush=True)
    for index, item in enumerate(flow_items, 1):
        flows.append(await run_flow(client, item))
        print(f"flow {index}/{len(flow_items)} valid {flows[-1]['valid']}", flush=True)
    quiz = await run_quiz(client)
    result = {"model": model, "summary": summary(optimize, flows, quiz, optimize_items), "optimize": optimize, "flow": flows, "quiz": quiz}
    OUT.mkdir(exist_ok=True)
    path = OUT / f"eval_{model.replace('/', '_').replace(':', '_')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result["summary"], indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    asyncio.run(main(args.model, args.limit))
