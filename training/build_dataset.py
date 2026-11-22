"""Build the chat-format JSONL dataset for the Deliver tasks, with held-out niches for testing.

Every example uses the exact prompts of DeliverService (captured through a stub model), and every
target is validated against the app's Pydantic schema and checked with the deterministic audit.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from flows import (
    apply_all,
    audit,
    draft_metrics,
    flow_prompt,
    gold_flow,
    gold_suggestions,
    niche_features,
    optimize_prompt,
    random_flow,
    resolve,
)
from niches import NICHES, TEST_SEEDS

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OPTIMIZE_PER_NICHE = 10
FLOWS_PER_NICHE = 3
SEED = 20261122


def answer(model) -> str:
    """Serialise a target the way the model should emit it."""
    return json.dumps(model.model_dump(), ensure_ascii=False)


def optimize_examples(niche: dict, rng: random.Random) -> list[dict]:
    """SuggestionSet examples for random flows of the niche."""
    examples, seen = [], set()
    attempts = 0
    while len(examples) < OPTIMIZE_PER_NICHE and attempts < 200:
        attempts += 1
        flow = random_flow(niche, rng)
        before = audit(flow)["issues"]
        if before == 0:
            continue
        system, prompt = optimize_prompt(niche, flow)
        if prompt in seen:
            continue
        gold = gold_suggestions(niche, flow, rng)
        if gold is None:
            continue
        resolved = resolve(flow, gold)
        if len(resolved) != len(gold.suggestions):
            continue
        after = audit(apply_all(flow, resolved))["issues"]
        if after >= before:
            continue
        seen.add(prompt)
        examples.append({
            "task": "optimize",
            "niche": niche["seed"],
            "lang": niche["lang"],
            "flow": flow.model_dump(),
            "issues_before": before,
            "issues_gold": after,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": answer(gold)},
            ],
        })
    return examples


def flow_examples(niche: dict, rng: random.Random) -> list[dict]:
    """FlowDraft examples with different backlog subsets of the niche."""
    examples, seen = [], set()
    attempts = 0
    while len(examples) < FLOWS_PER_NICHE and attempts < 50:
        attempts += 1
        features, chosen = niche_features(niche, rng)
        system, prompt = flow_prompt(niche, features)
        if prompt in seen:
            continue
        draft = gold_flow(niche, chosen, features, rng)
        metrics = draft_metrics(draft, features)
        if metrics["issues"] or not metrics["goal_reachable"] or metrics["must_coverage"] < 1:
            continue
        seen.add(prompt)
        examples.append({
            "task": "flow",
            "niche": niche["seed"],
            "lang": niche["lang"],
            "features": features,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": answer(draft)},
            ],
        })
    return examples


def main() -> None:
    """Generate, split by niche and write train.jsonl and test.jsonl."""
    rng = random.Random(SEED)
    DATA.mkdir(exist_ok=True)
    train, test = [], []
    for niche in NICHES:
        items = optimize_examples(niche, rng) + flow_examples(niche, rng)
        (test if niche["seed"] in TEST_SEEDS else train).extend(items)
    rng.shuffle(train)
    for name, items in (("train", train), ("test", test)):
        with (DATA / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    total = len(train) + len(test)
    for name, items in (("train", train), ("test", test)):
        tasks = {t: sum(1 for i in items if i["task"] == t) for t in ("optimize", "flow")}
        langs = {l: sum(1 for i in items if i["lang"] == l) for l in ("pl", "en")}
        print(f"{name}: {len(items)} ({len(items) / total:.0%}) tasks={tasks} langs={langs}")


if __name__ == "__main__":
    main()
