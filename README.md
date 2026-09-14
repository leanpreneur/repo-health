# repo-health

Point it at a GitHub repo URL, get back 5 evidence-backed findings on the codebase's health.

## Live demo

https://repo-health-kxqu.onrender.com/

The free tier sleeps when idle, so the first request after a while may take up to a minute to wake the instance. Subsequent requests are fast.

## The problem

Engineering leaders inherit or oversee codebases faster than they can read them, and by the time bus-factor risk or a review-latency problem shows up as an incident, it's already expensive. A fast, evidence-linked read on repo health lets them ask the right follow-up questions before that happens, instead of after.

## How it works

1. Collect: fetch repo metadata, the last 100 closed issues, the last 100 merged PRs (with changed file paths), and the last 300 commits from the GitHub REST API. Responses are cached locally in dev to avoid rate limits.
2. Assemble: build a prompt from the collected data plus few-shot examples of good vs. generic findings.
3. Analyze: send the prompt to Gemini 2.5 Flash with a structured output call constrained to a Pydantic schema.
4. Validate: parse the response against the schema and retry on either malformed output or a transient Gemini server error. Validation failures after retry raise rather than degrade silently.
5. Serve: a FastAPI endpoint (`POST /analyze`) runs collect → analyze and returns the 5 findings; a single static page provides the UI.
6. Deploy: packaged in a Docker image, running on Render.

## Baseline numbers

Measured on `pallets/flask`.

| Metric | Value |
|---|---|
| Tokens per run (input) | 65,784 |
| Tokens per run (output) | 1,030 |
| Latency | 15.2s |
| Estimated cost per run | ~$0.022 (at Gemini list pricing: $0.30 / $2.50 per million input/output tokens) |

## What v0 deliberately does not do

No agents, no retrieval, no evals yet. This is the baseline every later version gets measured against.

## Roadmap

- v1: eval set
- v2: retrieval
- v3: agent graph
- v4: guardrails and tracing
- v5: CI eval gates and governance

## Running it yourself

```bash
git clone <this-repo-url>
cd repo-health
uv sync
cp .env.example .env  # fill in GITHUB_TOKEN and GOOGLE_API_KEY
uv run uvicorn src.api:app --reload
```

Then visit http://localhost:8000.

## Notes

The model in use, Gemini 2.5 Flash, is scheduled for deprecation by Google in October 2026 and will need to be swapped for a current one before then.
