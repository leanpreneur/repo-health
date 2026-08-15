# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working rules

- Read `specs/constitution.md` and `specs/v0-spec.md` before any change.
- Python 3.12, uv for dependencies, Pydantic v2, FastAPI.
- Type hints on every function. No bare except.
- Every module gets a docstring saying what it does and why it exists.
- Do not add a dependency without saying in the commit message why it is needed.
- Do not add features that are listed as out of scope in the current spec.
- Prefer 40 readable lines over 15 clever ones.

## Development commands

```bash
uv sync                        # install dependencies
uv run fastapi dev src/api.py  # run dev server
uv run pytest                  # run all tests
uv run pytest tests/test_foo.py::test_bar  # run a single test
uv run ruff check .            # lint
uv run ruff format .           # format
```

## Environment

Copy `.env.example` to `.env` and fill in:
- `GITHUB_TOKEN` — GitHub personal access token (read:public only; anonymous works but hits rate limits faster)
- `GOOGLE_API_KEY` — Gemini API key used for the analysis step

## Architecture

Three modules in `src/`, called in sequence:

```
collect.py  →  analyze.py  →  api.py (FastAPI, serves static/index.html)
```

**`src/collect.py`** — fetches raw GitHub data for a repo URL: metadata, last 100 closed issues, last 100 merged PRs (with changed file paths), and last 300 commits. All GitHub responses must be treated as untrusted input. Logs tokens consumed and wall-clock time.

**`src/analyze.py`** — sends collected data to Gemini and parses the response into exactly 5 `Finding` objects via a Pydantic schema. Must fail loudly (raise) on schema validation errors rather than degrade silently. Must cap spend per run and refuse to exceed it.

**`src/api.py`** — FastAPI app exposing a single `POST /analyze` endpoint. Accepts a repo URL, calls collect then analyze, returns findings. Serves `src/static/index.html` for the minimal UI.

**Key output schema** (Pydantic, lives in `analyze.py` or a `models.py`):
```python
category: Literal["hotspot", "bus_factor", "review_latency", "recurring_issue", "test_gap"]
severity: Literal["low", "medium", "high"]
evidence: list[EvidenceItem]  # 1–5 items, each with url + one-line reason
```

Every finding must include at least one URL pointing to a real GitHub issue, PR, commit, or file. Generic findings ("add more tests") are invalid.

**Local dev cache** lives in `.cache/` (gitignored) — safe to use for GitHub API responses during development to avoid rate limits, but the spec marks caching layers as out of scope for production v0.
