"""Evaluate case study narratives through the app's real OllamaClient.structured path.

For every held-out fact sheet (synthetic projects from held-out niches plus real project 5) the model writes a
CaseStudyDraft with the app's system prompt and temperature. Metrics: schema validity, sentences the app's
number filter removes, qualitative claims flagged by claims.py on the text that survives the filter, sections
left empty although the sheet has facts for them, length and latency. Project 5 is also run several times and
its texts are kept for manual review. Results go to results/case_study/eval_<model>.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from pathlib import Path

os.environ.setdefault("OLLAMA_HOST", "127.0.0.1:11434")

from build_case_study import ROOT

from backend.models import CaseStudyDraft
from backend.ollama_client import OllamaClient, OllamaError
from backend.services.case_study import grounded

from claims import unsupported_claims

OUT = ROOT / "results" / "case_study"
FIELDS = ("summary", "context", "research", "synthesis", "ideation", "design", "testing", "reflection")
SECTION_OF = {"summary": "summary", "context": "context", "research": "research", "synthesis": "synthesis", "ideation": "ideation", "design": "design", "testing": "testing", "reflection": "reflection"}


def has_facts(sheet: str, key: str) -> bool:
    """Whether the sheet lists facts (not only the purpose line and gaps) for a section."""
    block = sheet.split(f"\n[{key}]", 1)[1].split("\n[", 1)[0].splitlines()[1:]
    return any(line.strip() and not line.startswith("Missing (do not mention)") for line in block)


def score(fields: dict[str, str], sheet: str, context: dict) -> dict:
    """Apply the app's number filter, then the claim check on what remains."""
    kept, removed = {}, []
    for key, text in fields.items():
        text, dropped = grounded(text, sheet)
        kept[key] = text
        removed += dropped
    flags = unsupported_claims(kept, context)
    empty = [k for k in FIELDS if has_facts(sheet, k) and not kept.get(k)]
    return {"kept": kept, "removed": removed, "flags": flags, "empty_with_facts": empty, "chars": sum(len(v) for v in kept.values())}


async def run(model: str, repeats: int) -> dict:
    items = [json.loads(line) for line in (ROOT / "data" / "case_test.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    client = OllamaClient(model=model)
    await client.resolve_model()
    results = []
    for index, item in enumerate(items, 1):
        system, sheet = item["messages"][0]["content"], item["messages"][1]["content"]
        runs = repeats if item["source"] == "real:5" else 1
        for attempt in range(runs):
            started = time.time()
            try:
                draft = await client.structured(CaseStudyDraft, system, sheet, temperature=0.3)
                fields = CaseStudyDraft.model_validate(draft.model_dump()).model_dump()
                valid = True
            except (OllamaError, ValueError) as exc:
                fields, valid = {k: "" for k in ("headline", *FIELDS)}, False
                print("invalid", item["niche"], exc)
            seconds = round(time.time() - started, 2)
            result = score(fields, sheet, item["context"])
            results.append({"index": index, "source": item["source"], "niche": item["niche"], "lang": item["lang"], "attempt": attempt, "valid": valid, "seconds": seconds, "raw": fields, **result})
            print(f"{model} {index}/{len(items)} {item['source']} removed {len(result['removed'])} flags {len(result['flags'])} {seconds}s", flush=True)
    return {"model": model, "results": results, "summary": summarise(results)}


def summarise(results: list[dict]) -> dict:
    def block(rows: list[dict]) -> dict:
        if not rows:
            return {}
        return {
            "n": len(rows),
            "valid": round(sum(r["valid"] for r in rows) / len(rows), 3),
            "removed_total": sum(len(r["removed"]) for r in rows),
            "removed_mean": round(statistics.mean(len(r["removed"]) for r in rows), 2),
            "flags_total": sum(len(r["flags"]) for r in rows),
            "flags_mean": round(statistics.mean(len(r["flags"]) for r in rows), 2),
            "clean_share": round(sum(1 for r in rows if not r["removed"] and not r["flags"]) / len(rows), 3),
            "empty_with_facts_mean": round(statistics.mean(len(r["empty_with_facts"]) for r in rows), 2),
            "chars_mean": round(statistics.mean(r["chars"] for r in rows)),
            "seconds_mean": round(statistics.mean(r["seconds"] for r in rows), 2),
            "flag_rules": {rule: sum(1 for r in rows for f in r["flags"] if f[1] == rule) for rule in sorted({f[1] for r in rows for f in r["flags"]})},
        }

    return {"synthetic": block([r for r in results if r["source"] == "synthetic"]), "project_5": block([r for r in results if r["source"] == "real:5"])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--repeats", type=int, default=5, help="runs on project 5")
    args = parser.parse_args()
    report = asyncio.run(run(args.model, args.repeats))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"eval_{args.model.replace('/', '_').replace(':', '_')}.json"
    path.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["summary"], indent=1))


if __name__ == "__main__":
    main()
