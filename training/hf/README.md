---
license: gemma
license_link: https://ai.google.dev/gemma/terms
base_model: google/gemma-3-4b-it
base_model_relation: finetune
language:
  - pl
  - en
pipeline_tag: text-generation
library_name: gguf
tags:
  - gguf
  - ollama
  - gemma3
  - lora
  - ux
  - ui
  - accessibility
  - structured-output
---

# gemma3-4b-ux (PrismaFlow Deliver)

A LoRA fine-tune of [Gemma 3 4B instruct](https://huggingface.co/google/gemma-3-4b-it), merged into the base weights and quantised to **GGUF Q4_K_M** (2.5 GB). It is built for one job: the **Deliver** phase of PrismaFlow, a local-first desktop app for product discovery with the Double Diamond. In that phase it returns JSON constrained by a schema:

- **`SuggestionSet`**: up to 4 small fixes for findings of a mobile user-flow audit. Allowed operations are `resize`, `move_zone`, `group_options`, `add_transition` and `remove_element`. The audit checks dead ends, unreachable screens, Fitts index > 4.5, touch targets below 44 px (WCAG 2.5.5) and Hick overload (> 7 options).
- **`FlowDraft`**: a first 3–5 screen user flow built from a persona and a MoSCoW backlog. Primary actions are large buttons in the thumb zone, there are no dead ends, and every Must-have feature is placed.

Screen names, labels and suggestion texts are mostly in Polish; English works too.

> Gemma is provided under and subject to the Gemma Terms of Use found at [ai.google.dev/gemma/terms](https://ai.google.dev/gemma/terms). Use of this model must also follow the [Gemma Prohibited Use Policy](https://ai.google.dev/gemma/prohibited_use_policy).

## Run it

```bash
ollama run hf.co/<REPO>
```

Or with the included Modelfile, after downloading the files:

```bash
ollama create local/gemma3-4b-ux -f Modelfile
```

PrismaFlow picks `local/gemma3-4b-ux` automatically for Deliver when that model is installed. The model was trained on the app's exact system prompts (`FLOW_SYSTEM`, `OPTIMIZE_SYSTEM`) and expects to be called with Ollama's `format` set to the JSON schema of the answer. Other prompts work as ordinary Gemma 3 chat, but they were not evaluated.

## Training

| | |
|---|---|
| Method | LoRA r = 16, α = 32, dropout 0.05, on all attention and MLP projections of the language model. bf16, 2 epochs, 140 steps, lr 2e-4 with cosine decay. Loss on answer tokens only. |
| Hardware | one RTX 5060 Ti 16 GB, 12.8 min |
| Deliver data | 364 synthetic examples over 28 product niches (299 Polish, 65 English). The inputs are random flows with injected UX defects. The prompts are the app's real prompts. Gold answers come from the app's deterministic audit, and a fix is kept only if applying it lowers the audit issue count. |
| Knowledge data | 195 Polish Q&A pairs. They were paraphrased by Gemma 3 12B from openly licensed sources: W3C WCAG 2.2 Understanding (W3C Software and Document License), GOV.UK Design System (Open Government Licence v3.0), MDN accessibility guides (CC BY-SA 2.5) and Wikipedia EN/PL (CC BY-SA 4.0). Answers sharing 8 or more consecutive words with their source were dropped. |
| Rules behind the gold answers | Fitts (1954), MacKenzie (1992), Bi, Li & Zhai's FFitts law (2013), Hick (1952), Hyman (1953), Card, Moran & Newell's KLM (1980), Wobbrock et al. (2008), Hoober (2013), WCAG 2.2 SC 2.5.5 and 2.5.8, Material Design and Apple HIG touch targets, Nielsen's heuristics, Miller (1956), Sweller (1988), MoSCoW (DSDM), Double Diamond (Design Council). |

## Evaluation

The held-out set has 60 audit flows and 18 backlogs from 6 product niches that never appear in training. All models were called through PrismaFlow's real structured-output path. Round 2 ran all models back to back.

**Audit suggestions (`SuggestionSet`)**

| Metric | gemma3-4b (base) | **gemma3-4b-ux** | gemma3-12b |
|---|---|---|---|
| Schema-valid JSON | 100% | 100% | 98.3% |
| Valid references (screens and elements exist, op is not a no-op) | 81.8% | **99.1%** | 93.2% |
| Audit issues removed (gold answers: 71.4%) | 39.6% | **68.7%** | 41.5% |
| Dead ends fixed | 33.3% | **100%** | 88.9% |
| Fitts/WCAG target problems fixed | 41.1% | **71.0%** | 27.8% |
| Mean latency | 3.26 s | **3.08 s** | 17.45 s |

**Flow drafts (`FlowDraft`)**

| Metric | gemma3-4b (base) | **gemma3-4b-ux** | gemma3-12b |
|---|---|---|---|
| Structure rules (3–5 screens, one start and one goal, valid targets) | 16.7% | **100%** | 55.6% |
| Goal reachable | 83.3% | **100%** | **100%** |
| Must-have features placed | 57.4% | **95.4%** | 76.4% |
| Audit issues in the draft | 5.11 | **0.06** | 5.94 |

**UX knowledge**: 26-question multiple-choice quiz on WCAG, Fitts, Hick, KLM, Nielsen and Material/HIG

| gemma3-4b (base) | gemma3-4b-ux | gemma3-12b |
|---|---|---|
| 57.7% | 57.7% | **76.9%** |

## Limitations

- **The test set comes from the same generator as the training set.** The niches, labels and flows are new, but defect types, prompt shape and answer style match training. Part of the gain is learning the gold answers' house style, for example always moving a hard Fitts target to the bottom zone. Expect a smaller margin on hand-drawn flows.
- **No gain in UX knowledge.** The quiz score is the same as the base model's. Do not use this model as a UX or accessibility reference; a larger general model is more reliable there. A variant trained with extra multiple-choice items reached 65.4% while matching this model on the Deliver tasks. That gain is small (2 of 26 questions), so it was not published.
- Only the Deliver tasks were evaluated. Behaviour on other prompts is that of Gemma 3 4B, possibly shifted by the fine-tune.
- Each model was evaluated once with sampling temperature > 0. Run-to-run noise is several percentage points: the base 4B scored 34.4% and 39.6% issue reduction in two identical runs. Treat only large gaps as real.
- Synthetic flows are a simplified model of mobile UI: sizes S/M/L = 24/40/56 px, and zones bottom/center/top at 120/320/560 px thumb distance. The audit's thresholds are design heuristics, not user-test results.

## Files

- `gemma3-4b-ux-Q4_K_M.gguf`: the model
- `Modelfile`: the Ollama Modelfile with the Gemma 3 chat template
- `NOTICE`: the Gemma Terms of Use notice

The training, data generation and evaluation code, together with the full report, lives in the PrismaFlow repository under `training/`.
