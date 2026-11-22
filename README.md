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

## Configuration

Environment variables, or `KEY=value` lines in `~/.config/PrismFlow/prismflow.env`:

| Variable | Purpose |
| --- | --- |
| `OLLAMA_HOST` | Ollama address, e.g. `127.0.0.1:11434` |
| `PRISMFLOW_MODEL` | Force a specific Ollama model |
| `PRISMFLOW_LOCALE` | Default content locale, e.g. `pl_PL` or `en_US` |
| `PRISMFLOW_TREND_ANCHOR` | Google Trends calibration keyword |
| `PRISMFLOW_REDDIT_CLIENT_ID` / `PRISMFLOW_REDDIT_CLIENT_SECRET` | Reddit OAuth app credentials |
| `PRISMFLOW_DATA_DIR` | Workspace location (default `~/.local/share/PrismFlow`) |

Reddit threads come from the PullPush public archive by default (no key needed, throttled to
about one request per second). With an approved Reddit API app set `PRISMFLOW_REDDIT_CLIENT_ID`
to use the official OAuth API instead, or force a provider with `PRISMFLOW_REDDIT_PROVIDER`.

Evidence is collected bilingually: queries are translated to English by the local model, English
suggestions and threads are fetched alongside local ones and translated back into the project
language, keeping the original text in the evidence metadata.

## Packaging

```bash
cd frontend && npm run build && cd ..
cd packaging && ../.venv/bin/pyinstaller --noconfirm --distpath ../dist --workpath ../build prismflow.spec
./dist/PrismFlow/prismflow
```

## Layout

```
main.py                  desktop entry point (pywebview + background Uvicorn)
backend/config.py        settings, paths, locale
backend/database.py      SQLite schema and data access
backend/collectors/      Google Autocomplete, Google Trends, Reddit
backend/ollama_client.py structured outputs validated by Pydantic
backend/services/        Discover expansion pipeline and background jobs
backend/api.py           HTTP API and static frontend
frontend/                React + React Flow UI
docs/mockups/            reference designs
```
