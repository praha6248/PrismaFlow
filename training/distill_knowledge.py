"""Distil the scraped open corpus into paraphrased UX/UI question-answer pairs with the local 12B teacher.

The teacher writes short Polish answers in its own words; any answer sharing 8 or more consecutive
words with its source passage is dropped so no source text is copied. Documents are split into
train and test by document, never by passage.
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

CORPUS = ROOT / "corpus"
DATA = ROOT / "data"
CHUNK = 2400
PER_DOC = {"wcag22": 2, "govuk": 1, "mdn": 2, "wikipedia-en": 2, "wikipedia-pl": 2}
KNOWLEDGE_SYSTEM = (
    "Jesteś doświadczonym projektantem UX/UI. Odpowiadasz po polsku, zwięźle i konkretnie, "
    "opierając się na sprawdzonych zasadach: WCAG 2.2, heurystyki Nielsena, prawa Fittsa i Hicka, "
    "model KLM, wytyczne platform mobilnych i dobre praktyki systemów projektowych."
)
TEACHER_SYSTEM = """You write training data for a Polish UX/UI assistant.
From the passage, write 2 or 3 question-answer pairs that a product designer would really ask.
Rules:
- Questions and answers in Polish.
- Each answer has 2-4 sentences, gives a concrete rule, number or reason, and is written entirely in your own words.
- Never copy sentences from the passage; do not quote more than 3 words.
- Skip navigation, legal text, changelogs and code. If the passage has no design knowledge, return an empty list.
- Do not mention "the passage" or "the text"."""


class QA(BaseModel):
    """One paraphrased question and answer."""

    question: str = Field(description="Question in Polish")
    answer: str = Field(description="Answer in Polish, 2-4 sentences, own words")


class QASet(BaseModel):
    """Teacher output for one passage."""

    pairs: list[QA] = Field(json_schema_extra={"maxItems": 3})


def chunks(text: str) -> list[str]:
    """Split a document into paragraph-aligned passages of about CHUNK characters."""
    paragraphs = [p for p in text.split("\n") if len(p) > 40]
    out, current = [], ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) > CHUNK and current:
            out.append(current)
            current = ""
        current += paragraph + "\n"
    if len(current) > 400:
        out.append(current)
    return out


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


def copies(answer: str, source: str, n: int = 8) -> bool:
    """Return whether the answer shares an n-word sequence with the source."""
    src = words(source)
    grams = {tuple(src[i:i + n]) for i in range(len(src) - n + 1)}
    ans = words(answer)
    return any(tuple(ans[i:i + n]) in grams for i in range(len(ans) - n + 1))


async def main(model: str, limit: int, concurrency: int) -> None:
    """Run the teacher over sampled passages and write knowledge_train/test.jsonl."""
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    rng = random.Random(7)
    jobs = []
    for doc in manifest:
        text = (CORPUS / "raw" / doc["file"]).read_text(encoding="utf-8").split("\n", 3)[-1]
        parts = chunks(text)[: PER_DOC.get(doc["source"], 1)]
        jobs += [(doc, part) for part in parts]
    rng.shuffle(jobs)
    jobs = jobs[:limit]
    docs = sorted({d["url"] for d, _ in jobs})
    rng.shuffle(docs)
    held = set(docs[: max(1, len(docs) * 15 // 100)])
    client = OllamaClient(model=model)
    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict] = []
    dropped = {"copied": 0, "error": 0, "short": 0}

    async def run(doc: dict, passage: str) -> None:
        async with semaphore:
            try:
                answer = await client.structured(QASet, TEACHER_SYSTEM, f"Source: {doc['title']}\n\nPassage:\n{passage}", temperature=0.5)
            except OllamaError:
                dropped["error"] += 1
                return
        for pair in answer.pairs:
            if len(pair.answer) < 60 or len(pair.question) < 10:
                dropped["short"] += 1
                continue
            if copies(pair.answer, passage):
                dropped["copied"] += 1
                continue
            results.append({
                "task": "knowledge",
                "source": doc["source"],
                "url": doc["url"],
                "license": doc["license"],
                "split": "test" if doc["url"] in held else "train",
                "messages": [
                    {"role": "system", "content": KNOWLEDGE_SYSTEM},
                    {"role": "user", "content": pair.question.strip()},
                    {"role": "assistant", "content": pair.answer.strip()},
                ],
            })
        if len(results) % 50 < 3:
            print(f"{len(results)} pairs", flush=True)

    await asyncio.gather(*(run(doc, passage) for doc, passage in jobs))
    DATA.mkdir(exist_ok=True)
    for split in ("train", "test"):
        with (DATA / f"knowledge_{split}.jsonl").open("w", encoding="utf-8") as handle:
            for item in results:
                if item["split"] == split:
                    handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"{len(jobs)} passages, {len(results)} pairs kept, dropped {dropped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="local/gemma3-12b")
    parser.add_argument("--limit", type=int, default=260)
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()
    asyncio.run(main(args.model, args.limit, args.concurrency))
