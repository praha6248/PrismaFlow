# PrismFlow

Local-first desktop studio for discovering product niches with the Double Diamond method
(Discover → Define → Develop → Deliver). Everything runs on your machine: a FastAPI backend,
a SQLite workspace with FTS5, market-data collectors and a local LLM served by Ollama,
displayed in a GTK WebKit window through pywebview.

## Requirements

- Linux with WebKit2GTK 4.1 and PyGObject (`gir1.2-webkit2-4.1`, `python3-gi`)
- Python 3.11+
- Node.js 20+ (only to build the frontend)
- Ollama with an instruction model; `gemma3:12b` works best, smaller models are picked automatically

## Setup

```bash
uv venv .venv --python /usr/bin/python3 --system-site-packages
uv pip install -r requirements-dev.txt
cd frontend && npm install && npm run build && cd ..
.venv/bin/python main.py
```

`--system-site-packages` lets the virtualenv reuse the distribution's PyGObject.

### Development

```bash
.venv/bin/python main.py --server-only --port 8765
cd frontend && npm run dev
.venv/bin/python main.py --dev http://localhost:5173
.venv/bin/python -m pytest
```

### UX fine-tune for Deliver

`training/` holds a LoRA fine-tune of Gemma 3 4B for the Deliver phase. It is trained on audit-driven
flow fixes and flow drafts generated from the app's own prompts and audit, plus UX/UI knowledge distilled
from WCAG 2.2, the GOV.UK Design System, MDN and Wikipedia. When `local/gemma3-4b-ux` is installed in
Ollama, the flow generation and audit suggestions use it (`TASK_MODELS` in `backend/config.py`). The
other phases keep the general model, and `PRISMFLOW_MODEL` overrides both. On held-out niches it cuts
audit issues by 68%, against 34% for the base 4B and 42% for `gemma3:12b`, at about a third of the 12B's
latency. Results, caveats and reproduction steps are in [training/REPORT.md](training/REPORT.md); the
sources are in [docs/bibliography.md](docs/bibliography.md).

## Configuration

Environment variables, or `KEY=value` lines in `~/.config/PrismFlow/prismflow.env`:

| Variable | Purpose |
| --- | --- |
| `OLLAMA_HOST` | Ollama address, e.g. `127.0.0.1:11434` |
| `PRISMFLOW_MODEL` | Force a specific Ollama model |
| `PRISMFLOW_LOCALE` | Default content locale, e.g. `pl_PL` or `en_US` |
| `PRISMFLOW_TREND_ANCHOR` | Google Trends calibration keyword |
| `PRISMFLOW_REDDIT_CLIENT_ID` / `PRISMFLOW_REDDIT_CLIENT_SECRET` | Optional Reddit OAuth app credentials |
| `PRISMFLOW_DATA_DIR` | Workspace location (default `~/.local/share/PrismFlow`) |

Community evidence comes from two documented, keyless public APIs: Stack Exchange questions
(sites such as fitness, parenting or cooking are picked from the query's topic; about 300 requests
per day per IP, cached for three days) and Lemmy, a federated Reddit-like forum, searched through
lemmy.world. With an approved Reddit API app set `PRISMFLOW_REDDIT_CLIENT_ID` to add Reddit threads
from the official OAuth API.

## Phases

- **Discover** — mind map grown by the local model from Google Autocomplete, with Google Trends and community
  evidence attached to every node.
- **Define** — three problem statements grounded in the starred topics, compared on one Google Trends scale,
  and proto-personas for the chosen problem.
- **Develop** — a MoSCoW backlog for the chosen persona; demand is the share of collected evidence
  (Google suggestions, Stack Exchange and Lemmy discussions) that supports a feature.
- **Deliver** — user flow studio with a live UX audit computed with NetworkX:
  steps to goal (shortest path), KLM time to goal (M = 1.35 s plus Hick and Fitts per step),
  Hick decision time `RT = a + b·log2(n+1)` (a = 0.25 s, b = 0.15 s), Fitts difficulty `ID = log2(2D/W)`
  from target size and thumb zone, WCAG 2.2 touch target sizes (24 px AA, 44 px AAA), dead ends and
  unreachable screens. The local model proposes fixes that can be accepted in one click, and
  "Generuj Handoff" writes `figma-prompt.md` and `CLAUDE.md` to `~/Documents/PrismFlow/<project>/`.

Evidence is collected bilingually: queries are translated to English by the local model, English
suggestions and threads are fetched alongside local ones and translated back into the project
language, keeping the original text in the evidence metadata.

## Packaging

```bash
cd frontend && npm run build && cd ..
cd packaging && ../.venv/bin/pyinstaller --noconfirm --distpath ../dist --workpath ../build prismflow.spec
./dist/PrismFlow/prismflow
```

## CI/CD

- `.github/workflows/ci.yml` runs on every push to `main` and on pull requests: backend tests (`pytest`) and the frontend type check and build.
- `.github/workflows/release.yml` runs on a `v*` tag (or by hand): it builds the frontend, runs the tests, packages the app with PyInstaller on Ubuntu 24.04 and attaches `PrismFlow-linux-x86_64.tar.gz` to a GitHub release.

```bash
git tag v0.1.0 && git push origin v0.1.0
```

## Layout

```
main.py                  desktop entry point (pywebview + background Uvicorn)
backend/config.py        settings, paths, locale
backend/database.py      SQLite schema and data access
backend/collectors/      Google Autocomplete, Google Trends, Stack Exchange + Lemmy, optional Reddit
backend/ollama_client.py structured outputs validated by Pydantic
backend/services/        Discover, Define, Develop and Deliver services, translation, background jobs
backend/api.py           HTTP API and static frontend
frontend/                React + React Flow UI
docs/mockups/            reference designs
```
