"""Distil multiple-choice UX/UI items from training documents of the open corpus.

Only documents outside the held-out knowledge split are used. Items whose question is close to
one of the evaluation quiz questions (word Jaccard >= 0.2), together with their open-answer twin, are dropped so the quiz stays unseen.
Each item becomes two chat examples: the quiz-style JSON answer and an open answer with the reason.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from backend.ollama_client import OllamaClient, OllamaError
from distill_knowledge import CORPUS, DATA, KNOWLEDGE_SYSTEM, chunks, copies
from evaluate import QUIZ, QUIZ_SYSTEM

TEACHER_SYSTEM = """You write multiple-choice exam items for Polish product designers learning UX/UI and accessibility.
From the passage, write 2 or 3 items that test a concrete, checkable fact or rule: a number, a threshold,
a level, a law, a recommended practice or the reason behind it.
Rules:
- Everything in Polish; keep established English names of criteria and laws.
- One unambiguous correct option and three plausible but clearly wrong distractors of similar length.
- explanation: 1-2 sentences in your own words saying why the correct option is right.
- Never copy sentences from the passage; do not quote more than 3 words.
- Skip navigation, legal text, changelogs and code. If the passage has no checkable design knowledge, return an empty list."""


class Item(BaseModel):
    """One multiple-choice item."""

    question: str
    correct: str
    distractors: list[str] = Field(json_schema_extra={"minItems": 3, "maxItems": 3})
    explanation: str


class ItemSet(BaseModel):
    """Teacher output for one passage."""

    items: list[Item] = Field(json_schema_extra={"maxItems": 3})


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.casefold()) if len(w) > 2}


def near_quiz(question: str, threshold: float = 0.2) -> bool:
    """Return whether the question overlaps an evaluation quiz question."""
    mine = tokens(question)
    for quiz_question, _, _ in QUIZ:
        other = tokens(quiz_question)
        if mine and other and len(mine & other) / len(mine | other) >= threshold:
            return True
    return False


async def main(model: str, limit: int, concurrency: int) -> None:
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    held = {json.loads(line)["url"] for line in (DATA / "knowledge_test.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()}
    rng = random.Random(11)
    jobs = []
    for doc in manifest:
        if doc["url"] in held:
            continue
        text = (CORPUS / "raw" / doc["file"]).read_text(encoding="utf-8").split("\n", 3)[-1]
        jobs += [(doc, part) for part in chunks(text)[:3]]
    rng.shuffle(jobs)
    jobs = jobs[:limit]
    client = OllamaClient(model=model)
    semaphore = asyncio.Semaphore(concurrency)
    out: list[dict] = []
    dropped = {"quiz_overlap": 0, "copied": 0, "error": 0, "invalid": 0}

    async def run(doc: dict, passage: str) -> None:
        async with semaphore:
            try:
                answer = await client.structured(ItemSet, TEACHER_SYSTEM, f"Source: {doc['title']}\n\nPassage:\n{passage}", temperature=0.5)
            except OllamaError:
                dropped["error"] += 1
                return
        for item in answer.items:
            options = [item.correct.strip(), *[d.strip() for d in item.distractors]]
            if len({o.casefold() for o in options}) != 4 or not all(options) or len(item.question) < 10:
                dropped["invalid"] += 1
                continue
            if near_quiz(item.question):
                dropped["quiz_overlap"] += 1
                continue
            if copies(item.explanation, passage):
                dropped["copied"] += 1
                continue
            rng.shuffle(options)
            letter = "ABCD"[options.index(item.correct.strip())]
            text = item.question.strip() + "\n" + "\n".join(f"{'ABCD'[i]}. {o}" for i, o in enumerate(options))
            meta = {"source": doc["source"], "url": doc["url"], "license": doc["license"]}
            out.append({"task": "knowledge_mc", **meta, "messages": [
                {"role": "system", "content": QUIZ_SYSTEM},
                {"role": "user", "content": text},
                {"role": "assistant", "content": json.dumps({"answer": letter})},
            ]})
            out.append({"task": "knowledge", **meta, "messages": [
                {"role": "system", "content": KNOWLEDGE_SYSTEM},
                {"role": "user", "content": item.question.strip()},
                {"role": "assistant", "content": f"{item.correct.strip()}. {item.explanation.strip()}"},
            ]})
        if len(out) % 100 < 6:
            print(f"{len(out)} examples", flush=True)

    await asyncio.gather(*(run(doc, passage) for doc, passage in jobs))
    with (DATA / "knowledge_mc_train.jsonl").open("w", encoding="utf-8") as handle:
        for item in out:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    letters = [json.loads(i["messages"][2]["content"])["answer"] for i in out if i["task"] == "knowledge_mc"]
    print(f"{len(jobs)} passages, {len(out)} examples, letters {{{', '.join(f'{l}: {letters.count(l)}' for l in 'ABCD')}}}, dropped {dropped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="local/gemma3-12b")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()
    asyncio.run(main(args.model, args.limit, args.concurrency))
