# Fine-tuning report: `local/gemma3-4b-ux`

A LoRA fine-tune of Gemma 3 4B instruct for the PrismaFlow Deliver phase: audit-driven flow fixes (`SuggestionSet`) and first flow drafts (`FlowDraft`), plus UX/UI knowledge distilled from openly licensed sources.

## Setup

| | |
|---|---|
| Base weights | `unsloth/gemma-3-4b-it` (ungated mirror of `google/gemma-3-4b-it`), downloaded to `training/weights/`. The GGUF originals in `~/models` were not touched. |
| Method | LoRA r = 16, α = 32, dropout 0.05, on all attention and MLP projections of the language model. bf16, gradient checkpointing. Loss on the answer tokens only. |
| Schedule | 2 epochs, 140 optimiser steps (batch 1 × 8 accumulation), AdamW at lr 2e-4 with cosine decay. 12.8 min on the RTX 5060 Ti, 12.5 GiB peak. Ollama was unloaded during training. |
| Training data | 364 Deliver examples (280 `SuggestionSet`, 84 `FlowDraft`; 299 PL, 65 EN) plus 195 sampled UX knowledge Q&A pairs |
| Held-out data | 78 Deliver examples from 6 niches never seen in training (60 optimise, 18 flow) plus 129 knowledge Q&A pairs from held-out documents |
| Export | merged bf16 → GGUF (`llama.cpp convert_hf_to_gguf.py`) → `llama-quantize Q4_K_M` (2.5 GB) → `ollama create local/gemma3-4b-ux -f training/Modelfile` (same chat template as `local/gemma3-4b`) |

### Where the data comes from

- **Deliver tasks** (`build_dataset.py`): random flows over 34 niches with injected defects: dead ends, unreachable screens, small or far targets, and crowded screens. The prompts are the exact strings `DeliverService.optimize` / `generate` send; they are captured through a stub model. Gold answers come from the deterministic audit. A candidate fix is kept only if, applied with `apply_suggestion`, it lowers the `audit()` issue count. Every target validates against the Pydantic schema and resolves through the app's `_resolve`.
- **UX knowledge** (`scrape_corpus.py` → `distill_knowledge.py`): 346 documents (3.2 M characters) scraped from WCAG 2.2 Understanding (W3C licence), the GOV.UK Design System (OGL v3), MDN accessibility guides (CC BY-SA 2.5) and Wikipedia EN/PL (CC BY-SA 4.0), honouring robots.txt. `local/gemma3-12b` paraphrased 320 passages into 945 Polish Q&A pairs. 4 pairs were dropped because they shared 8 or more consecutive words with their source. `corpus/manifest.json` records the URL and licence of every document.
- **Bibliography**: [docs/bibliography.md](../docs/bibliography.md) is the curated core with the rules used. [docs/bibliography-extended.md](../docs/bibliography-extended.md) lists 505 works from OpenAlex.

## Results

All models were called through the app's real `OllamaClient.structured` path, with the app's temperatures: 0.3 for optimise, 0.4 for flow and 0.0 for the quiz. Each model was run once, sequentially. Raw per-example results are in `results/eval_*.json`.

### Deliver: audit suggestions (`SuggestionSet`, 60 held-out flows, 6.98 issues each on average)

| Metric | gemma3-4b (base) | **gemma3-4b-ux** | gemma3-12b (reference) |
|---|---|---|---|
| JSON / schema valid | 100% | 100% | 100% |
| Valid references (screen and element exist, op valid, not a no-op) | 79.1% | **98.2%** | 94.6% |
| Issues after applying the suggestions (mean) | 4.58 | **2.23** | 4.08 |
| Audit issue reduction (gold answers: 71.4%) | 34.4% | **68.0%** | 41.5% |
| Flows improved | 83.3% | **100%** | 93.3% |
| Dead-end fix rate | 27.8% | **100%** | 88.9% |
| Fitts / WCAG target fix rate | 36.3% | **70.2%** | 28.2% |
| Mean latency | 2.93 s | **2.11 s** | 5.96 s |

### Deliver: flow design (`FlowDraft`, 18 held-out backlogs)

| Metric | gemma3-4b (base) | **gemma3-4b-ux** | gemma3-12b (reference) |
|---|---|---|---|
| JSON / schema valid | 100% | 100% | 100% |
| Structure rules (3–5 screens, one start and one goal, valid targets) | 22.2% | **100%** | 38.9% |
| Goal reachable from start | 94.4% | 94.4% | 94.4% |
| Must-have features placed | 52.3% | **97.2%** | 59.7% |
| Audit issues of the drafted flow (mean) | 4.61 | **0.17** | 5.72 |
| Dead ends per flow | 0.06 | 0.06 | 0.06 |
| Mean latency | 5.78 s | **3.72 s** | 12.66 s |

### UX knowledge

| Metric | gemma3-4b (base) | gemma3-4b-ux | gemma3-12b (reference) |
|---|---|---|---|
| Held-out answer loss, knowledge Q&A (129 pairs, nats/token) | 2.42 | **1.38** | — |
| 26-question UX/accessibility quiz (WCAG, Fitts, Hick, KLM, Nielsen, Material/HIG) | 57.7% | 57.7% | **76.9%** |

Held-out answer loss on the Deliver tasks fell from 1.58 to 0.022 (optimise) and from 0.90 to 0.106 (flow).

## Honest reading

- **Clear win on what the app asks the model to do.** On unseen niches the fine-tune reaches 95% of the gold issue reduction (68.0% vs 71.4%). It almost doubles the base 4B, beats the 12B, and runs about 3× faster than the 12B. It always fixes dead ends, and it nearly stops referencing screens or elements that do not exist.
- **The test set comes from the same generator as the training set.** The niches, labels and flows are new, but defect types, prompt shape and answer style match training. Part of the gain is learning the house style of the gold answers (for example `move_zone → bottom` for every Fitts finding). Real user flows drawn by hand in the studio may be less regular, so expect a smaller margin there.
- **No gain on factual UX knowledge.** The distilled Q&A lowered held-out answer loss, so the model learned the style and content of those answers. But quiz accuracy did not change (15/26 for both 4B models), and the 12B stays well ahead (20/26). The knowledge set was a minority of training (195 of 559 examples) and is phrased as open answers, not as multiple choice. Do not use the fine-tune as a UX reference assistant.
- **Weak spots that remain.** In 1 of 18 drafts the goal is unreachable; the base 4B and the 12B fail the same case. The fine-tune proposes slightly fewer suggestions per answer (3.62 vs 3.9–4). Its Fitts/WCAG fix rate (70%) is below what the gold answers allow, because some answers spend a slot on a lower-priority fix.
- **Not measured:** the Discover, Define and Develop tasks. The app therefore uses the fine-tune only for Deliver (see below), and the 12B stays the default everywhere else.
- **Single run per model** with sampling temperatures > 0, so differences of a few points are within noise. The large gaps above are not.

## How the app uses it

`backend/config.py` defines `TASK_MODELS = {"deliver": ("local/gemma3-4b-ux",)}`. `OllamaClient.structured(..., task="deliver")` picks `local/gemma3-4b-ux` when it is installed, and otherwise falls back to the usual `PREFERRED_MODELS` order. `PRISMAFLOW_MODEL` still overrides everything. Every other phase keeps using `local/gemma3-12b`.

## Round 2: `local/gemma3-4b-ux2` with multiple-choice knowledge

Goal: close the knowledge-quiz gap without losing the Deliver gains. A 12B QLoRA was started and then dropped by decision; only the 4B was retrained.

### What changed

- `distill_mc.py`: `gemma3-12b` wrote 1100 multiple-choice items, in the quiz's format, from 400 passages of **training** documents only. Each item also becomes an open answer with its reason.
- **Quiz contamination guard:** items whose question has word Jaccard ≥ 0.2 with any of the 26 quiz questions were removed, together with their open-answer twins. That removed 27 items, and the removed ones were real near-duplicates (Miller 7±2, Hick's logarithm, the 4.5:1 contrast, MoSCoW "Won't", Fitts target width, SUS). 2 of the 816 round-1 open Q&A matched the same guard and were excluded from ux2. 1076 MC items remained, with answer letters balanced (A/B/C/D 268/254/272/306 before filtering).
- **Training mix:** 364 Deliver examples, 338 MC items and 338 open answers, so knowledge is 65% of 1040 examples instead of 35% of 559. Same LoRA settings, 2 epochs, 260 steps, 18.2 min, 12.5 GiB peak.

### Results (all four models re-run back to back on the same held-out set)

| Metric | gemma3-4b | gemma3-4b-ux | **gemma3-4b-ux2** | gemma3-12b |
|---|---|---|---|---|
| Optimise: schema valid | 100% | 100% | 100% | 98.3% |
| Optimise: valid references | 81.8% | 99.1% | 99.1% | 93.2% |
| Optimise: audit issue reduction (gold 71.4%) | 39.6% | **68.7%** | 68.5% | 41.5% |
| Optimise: dead-end fix | 33.3% | **100%** | 97.2% | 88.9% |
| Optimise: Fitts/WCAG fix | 41.1% | 71.0% | **71.8%** | 27.8% |
| Optimise: latency | 3.26 s | 3.08 s | 2.33 s | 17.45 s |
| Flow: structure rules | 16.7% | **100%** | **100%** | 55.6% |
| Flow: goal reachable | 83.3% | **100%** | 94.4% | **100%** |
| Flow: Must-have coverage | 57.4% | **95.4%** | 94.0% | 76.4% |
| Flow: audit issues | 5.11 | **0.06** | **0.06** | 5.94 |
| UX quiz (26 items) | 57.7% | 57.7% | **65.4%** | **76.9%** |
| Held-out loss: optimise / flow / knowledge | 1.58 / 0.90 / 2.42 | 0.022 / 0.106 / 1.38 | 0.020 / 0.107 / 1.39 | — |

### Honest reading

- **The quiz improved a little, not decisively.** ux2 answers 17 of 26 correctly, against 15 for ux and the base 4B and 20 for the 12B. Two questions on 26 is within what a different phrasing could swing. ux2 gained Miller, the 4.5:1 contrast, Material's 48 dp, the dead-end heuristic and SC 3.3.8. It lost the 24 px of SC 2.5.8 and Hick's logarithm, exactly the topics whose near-duplicate items were filtered out. Multiple-choice practice helped with facts it saw in training; it did not make the model reliable on UX facts in general. The 12B is still the better source of UX facts.
- **Deliver held.** On every metric ux2 is within one example of ux. Dead ends: 35 of 36 fixed vs 36 of 36. Goal reachable: 17 of 18 vs 18 of 18. Fitts/WCAG fixes are slightly better. The held-out losses are practically identical.
- **Run-to-run noise is visible.** The base 4B went from 34.4% to 39.6% issue reduction between round 1 and round 2 with no change at all, so differences of a few points are noise. The 12B's latency (17 s here, 6 s in round 1) depended on what else was running on the GPU; latencies are only comparable within one round.
- **Decision:** the rule was to switch only if ux2 is at least as good on Deliver. It ties within noise but is one example worse on two metrics, so `TASK_MODELS` stays on `local/gemma3-4b-ux`. ux2 stays installed in Ollama for anyone who wants the slightly better quiz score. To use it, set `PRISMAFLOW_MODEL=local/gemma3-4b-ux2`; note that this then applies to every phase.

Raw results: `results/round2/`. Reproduce ux2:

```bash
OLLAMA_HOST=127.0.0.1:11434 .venv/bin/python distill_mc.py --limit 400
.venv/bin/python train.py --name ux2 --knowledge-share 0.65 --mc-share 0.5
./export.sh gemma3-4b-ux2 out/ux2
.venv/bin/python evaluate.py local/gemma3-4b-ux2
```

## Round 3: `local/gemma3-4b-case` for the case study narrative

Goal: the Deliver case study (`backend/services/case_study.py`) asks a local model to write short narrative per section from a fact sheet. The app already drops sentences with numbers that are not in the sheet, but `gemma3-12b` still made qualitative claims the data does not support. This round trains a 4B to write only what the facts carry.

### Data

- **Style corpus (local only):** 39 real case studies listed in `~/.local/share/PrismaFlow-training/case-studies/corpus.json`. 27 come from designers' own portfolios (all rights reserved) and 12 from public-sector teams (OGL v3 / US public domain). `case_corpus.py` extracts sections and measures style. Everything it derives (text, `style.json`, phrasebook) stays next to the corpus, outside the repository; no corpus sentence is copied into targets or code. Measured: median sentence 16 words in portfolios and 18 in public-sector posts; portfolios speak as "I" (24% of sentences), public-sector posts as "we" (50%); only 9–15% of sentences carry a number. The targets keep the app's first person plural and follow the recurring moves: purpose before method in research, the persona as the reference for later decisions, findings stated as what people did, numbers with their denominator, lessons and concrete next tests at the end.
- **Pairs (`build_case_study.py`):** input = the exact `SYSTEM` prompt and `fact_sheet()` output; output = `CaseStudyDraft` JSON. Facts come from synthetic projects over the 28 training niches, run through the app's own `audit()`, `usability.summarize()` and `case_study_facts()`, with each phase randomly missing (negative examples: no claims about missing data). Projects 2, 4, 7, 8 and 9 come from a backup copy of the user's database. Every target passes the app's number filter with nothing removed and `claims.py` with no flags. 402 training pairs (332 PL, 70 EN); 31 held out (30 from the 6 held-out niches + real project 5). The jsonl files contain local project data and are git-ignored.
- **Claim check (`claims.py`):** flags "all touch targets meet 44 px" when they do not, smooth/successful/intuitive tasks when tests show failures, confirmed/validated without confirmed interview hypotheses, measured outcomes or iterations, "well received", team/timeline, statements about missing interviews or tests, and quoting the model-written persona quote. It runs on the text left after the number filter.

### Training

LoRA r = 16 on `gemma-3-4b-it` as in round 1, bf16, 2 epochs, 101 steps, 29.8 min, 10.7 GiB peak (logits computed only at answer positions). Held-out answer loss 2.60 → 0.035. `train.py` gained `--train-file`, `--test-files` and an optional `--qlora` (4-bit base, merged into bf16 on the CPU) for when the GPU is shared; the reported model was trained in bf16 after `gemma3-12b` was unloaded.

### Results (`evaluate_case_study.py`, app path `OllamaClient.structured`, temperature 0.3; project 5 run 5×)

| Metric | gemma3-4b (base) | **gemma3-4b-case** | gemma3-12b |
|---|---|---|---|
| Synthetic held-out (30): schema valid | 36.7% | 96.7% | 100% |
| Sentences removed by the number filter | 1 | 2 | 0 |
| Unsupported-claim flags (total) | 36 (on 11 valid texts) | **2** | 104 |
| Texts with nothing removed and no flags | 1 of 11 valid | **86.7%** | 3.3% |
| Sections left empty although the sheet has facts (mean) | 0.55 | 0.27 | 0 |
| Narrative length (chars, mean) | 2392 | 1372 | 3102 |
| Project 5 (5 runs): schema valid | 0% | 100% | 100% |
| Project 5: sentences removed | — | 0 | 0 |
| Project 5: claim flags | — | **0** | 17 |
| Project 5: mean latency | — | **4.9 s** | 26.0 s |

The base 4B often failed: 19 of 30 synthetic requests and all 5 project 5 runs ended in Ollama 500 errors (GPU shared with a training job at the time) or JSON cut off mid-string; a rerun on a free GPU stalled on the same unterminated output, so its row covers the valid answers only. 12B flags by rule (synthetic): smooth/intuitive 55, missing tests mentioned 27, validated/confirmed 14, outcomes 2, all targets 44 px 2, other 4. Latency on the synthetic set is not comparable: the 4B-case run shared the GPU with a training job (58 s mean), the 12B did not.

**Manual check on project 5** (data: touch targets 4 of 10 at 44 px, task “Wynik” 1 of 2, 4 themes with one note each, persona quote written by the model):

- `gemma3-12b`: in 4 of 5 runs it says it ensured touch targets of at least 44 px (once followed by "not all elements met it"). Every run calls the solution "intuitive" (2–5 times), although only 1 of 2 people finished the task. Other unsupported claims: "the 85 web signals confirmed the concerns", "all these features were deemed essential" (the backlog has Must 3, Should 2, Could 2), "financial losses", and listing RICE scores the facts already print. The flag counter is a lower bound; the manual reading matches it.
- `gemma3-4b-case`: the number filter removed nothing in any run. It states "only 4 of 10 touch targets reach 44 px; the smaller ones need enlarging", "1 of 2", the dead taps on “Regulamin” and “Notatki”, and that part of the empathy map is assumption. One unsupported claim that the checker missed: in 4 of 5 runs it says the theme “Ograniczenia finansowe…” has the most notes, while every theme has one; the fifth run got it right ("each theme rests on a single note"). Two runs copy the truncated persona role ("uprawia warzywa z…").

### Honest reading

- **Much more grounded, much less prose.** The fine-tune states what the data says, including what is weak, and stays quiet about missing phases. The 12B writes 2.3× more text and fills it with overclaims. The 4B's narrative is plain and close to the house style of the targets; it reads as a careful research summary, not as a portfolio story.
- **Targets are templated.** Gold narratives are composed by rules from the facts, so the model learns those phrasings. Real designer case studies informed the moves and tone, not the wording. Unusual projects may get generic sentences.
- **The claim checker is rule-based** and misses comparative claims such as "the theme with the most notes" when there is a tie; manual reading remains necessary.
- **Single run per model** except project 5; small differences are noise.

**Decision:** `TASK_MODELS["case_study"] = ("local/gemma3-4b-case",)`; `CaseStudyService.generate` passes `task="case_study"`, falling back to the general model when the fine-tune is not installed.

Reproduce (the corpus and the database copy stay outside the repo):

```bash
.venv/bin/python case_corpus.py
.venv/bin/python build_case_study.py --db <backup copy of workspace.db>
.venv/bin/python train.py --name case --train-file case_train.jsonl --test-files case_test.jsonl --knowledge-share 0 --max-len 3072
./export.sh gemma3-4b-case out/case
.venv/bin/python evaluate_case_study.py local/gemma3-4b-case
```

## Reproduce (round 1)

```bash
cd training
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python torch --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv/bin/python transformers peft datasets accelerate sentencepiece protobuf huggingface_hub hf_transfer safetensors gguf numpy pydantic networkx httpx beautifulsoup4 lxml
.venv/bin/hf download unsloth/gemma-3-4b-it --local-dir weights/gemma-3-4b-it --exclude "*.gguf"
git clone --depth 1 https://github.com/ggml-org/llama.cpp vendor/llama.cpp
cmake -S vendor/llama.cpp -B vendor/llama.cpp/build -DGGML_CUDA=OFF && cmake --build vendor/llama.cpp/build --target llama-quantize -j
.venv/bin/python scrape_bibliography.py
.venv/bin/python scrape_corpus.py
OLLAMA_HOST=127.0.0.1:11434 .venv/bin/python distill_knowledge.py --limit 320
.venv/bin/python build_dataset.py
curl -s http://127.0.0.1:11434/api/generate -d '{"model":"local/gemma3-12b","keep_alive":0}'
.venv/bin/python train.py
./export.sh
.venv/bin/python evaluate.py local/gemma3-4b-ux
```

## Publishing on Hugging Face

`hf/` holds the release of `gemma3-4b-ux`: the model card (`README.md`), the `Modelfile`, the Gemma `NOTICE` and `upload.sh`. Nothing is uploaded automatically. Log in first, then pass the repo id:

```bash
.venv/bin/hf auth login
hf/upload.sh <hf-user>/<repo-name>
```

The script fills the repo id into the card, creates the repo (public by default) and uploads the card, the Modelfile, the notice and `out/gemma3-4b-ux-Q4_K_M.gguf`. After that the model runs with `ollama run hf.co/<hf-user>/<repo-name>`.
