# Contributing to PrismaFlow

Thanks for helping. PrismaFlow is licensed under AGPL-3.0; by submitting a contribution you agree
that it is released under the same license.

## Getting started

```bash
uv venv .venv --python /usr/bin/python3 --system-site-packages
uv pip install -r requirements-dev.txt
cd frontend && npm install && cd ..
.venv/bin/python main.py --server-only --port 8765
cd frontend && npm run dev
```

Run the checks before opening a pull request:

```bash
.venv/bin/python -m pytest
cd frontend && npm run build
```

## Architecture

```
frontend (React + React Flow)  <-- HTTP -->  backend/api.py (FastAPI)
                                                   |
                      backend/services/  (Discover, Define, Develop, Deliver)
                         |            |                    |
          backend/collectors/   backend/ollama_client.py   backend/database.py
          (Autocomplete, Trends,  (local LLM, Pydantic     (SQLite + FTS5)
           Stack Exchange, Lemmy,  validated output)
           Reddit)
```

## Guidelines

- Open an issue before large changes so the direction can be agreed first.
- Keep pull requests focused: one change, with tests for new backend behaviour.
- Collectors must use documented public APIs, respect rate limits and cache results. Do not add scraping
  of sites that forbid it.
- Write commit messages in English, in the imperative mood.
- Python docstrings are English. Keep code free of explanatory comments; name things clearly instead.
- UI strings live in the frontend. New user-facing text should be easy to translate.

## Reporting bugs

Use the issue templates. Include your OS, Python and Ollama versions, the model in use and the relevant log output.
