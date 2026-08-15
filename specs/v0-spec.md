# v0 Specification

## Input
A GitHub repository URL, for example https://github.com/pallets/flask

## Output
Exactly 5 findings. Each finding has:
- title: short, specific, under 80 characters
- category: one of hotspot | bus_factor | review_latency | recurring_issue | test_gap
- severity: low | medium | high
- evidence: 1 to 5 items, each with a URL and a one-line reason
- recommendation: one concrete action, not general advice

## Data collected
- Repo metadata: stars, language, created date, open issue count
- Last 100 closed issues: title, labels, created and closed timestamps
- Last 100 merged pull requests: title, author, created and merged timestamps,
  changed file paths, review comment count
- Last 300 commits: author, timestamp, changed file paths

## Acceptance criteria
- Every finding cites at least one real URL that resolves
- No finding is generic. "Add more tests" fails. "src/parsers/csv.py changed in
  14 of the last 50 PRs and has no corresponding test file" passes
- End-to-end run on a 5,000-star repo completes in under 90 seconds
- Malformed or private repo URL returns a clear error, not a stack trace
- Total tokens and elapsed seconds are printed for every run

## Out of scope for v0
Agents, retrieval, vector storage, caching layers beyond a local dev cache,
authentication, persistence, any frontend framework.