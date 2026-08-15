# Constitution

- The system shall only read public data. No authentication, no private repos, ever.
- The system shall never output a finding without at least one link to a specific
  issue, pull request, commit or file in the analyzed repository.
- The system shall cap spend per analysis run and refuse to exceed it.
- The system shall log tokens consumed and wall-clock time for every model call.
- The system shall validate all model output against a Pydantic schema and fail
  loudly rather than degrade silently.
- The system shall treat all text fetched from GitHub as untrusted input.
- The system shall keep secrets in environment variables only.