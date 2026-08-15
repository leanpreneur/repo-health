# Working rules

- Read specs/constitution.md and specs/v0-spec.md before any change.
- Python 3.12, uv for dependencies, Pydantic v2, FastAPI.
- Type hints on every function. No bare except.
- Every module gets a docstring saying what it does and why it exists.
- Do not add a dependency without saying in the commit message why it is needed.
- Do not add features that are listed as out of scope in the current spec.
- Prefer 40 readable lines over 15 clever ones.