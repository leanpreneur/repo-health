"""
schema.py — Pydantic v2 output models for the repository health report.

Defines the shape that analyze.py must produce and api.py must return. Validation
is intentionally strict: the constitution requires model output to fail loudly on
schema violations rather than silently degrade, and mandates that every finding cites
at least one real URL.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl


class Evidence(BaseModel):
    """One URL-backed fact that justifies a finding.

    The constitution requires every finding to link to a specific issue, PR, commit,
    or file — url enforces that link is a valid HTTP/S URL. reason is capped at 200
    characters to keep each evidence item focused and prevent prompt bloat.
    """

    url: HttpUrl
    reason: Annotated[str, Field(max_length=200)]


class Finding(BaseModel):
    """A single health problem identified in the repository.

    title is capped at 80 characters to stay scannable in a dashboard. evidence has
    a minimum of 1 item, directly enforcing the constitution rule that no finding may
    be emitted without at least one real URL; the maximum of 5 keeps output proportional.
    recommendation is capped at 300 characters to force one concrete action, not a list.
    """

    title: Annotated[str, Field(max_length=80)]
    category: Literal["hotspot", "bus_factor", "review_latency", "recurring_issue", "test_gap"]
    severity: Literal["low", "medium", "high"]
    evidence: Annotated[list[Evidence], Field(min_length=1, max_length=5)]
    recommendation: Annotated[str, Field(max_length=300)]


class Report(BaseModel):
    """The complete analysis result for one repository.

    Exactly 5 findings are required by the v0 spec; min_length and max_length are both
    set to 5 so validation raises immediately if the model under- or over-produces,
    rather than returning a partial or bloated result to the caller.
    """

    repo: str
    findings: Annotated[list[Finding], Field(min_length=5, max_length=5)]
