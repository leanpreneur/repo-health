"""
api.py — FastAPI application exposing POST /analyze, GET /health, and GET /.

Validates incoming repo URLs, delegates to analyze_repo in a thread pool with a
timeout, and maps internal errors to HTTP status codes so raw tracebacks never
reach the client. HTTPException raised inside analyze_repo (e.g. 413) propagates
unchanged; all other exceptions become 502.
"""

import concurrent.futures
import logging
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .analyze import analyze_repo
from .schema import Report

logger = logging.getLogger(__name__)

app = FastAPI()

_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/?$"
)
_ANALYSIS_TIMEOUT = 120  # seconds


class AnalyzeRequest(BaseModel):
    """Incoming request body for POST /analyze."""

    repo_url: str


@app.get("/health")
def health() -> dict:
    """Liveness check — returns 200 as long as the process is up."""
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    """Serve the single-page UI from src/static/index.html."""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> Report:
    """Validate a GitHub repo URL, run analysis in a thread, and return the Report.

    Returns 400 for a malformed URL, 413 if the repo data is too large, 504 on
    timeout, and 502 for any other internal failure.
    """
    match = _GITHUB_URL_RE.match(request.repo_url.strip())
    if not match:
        raise HTTPException(
            status_code=400,
            detail=(
                "repo_url must be a public GitHub repository URL, "
                "e.g. https://github.com/owner/repo"
            ),
        )
    owner = match.group("owner")
    repo = match.group("repo")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(analyze_repo, owner, repo)
        try:
            return future.result(timeout=_ANALYSIS_TIMEOUT)
        except concurrent.futures.TimeoutError:
            raise HTTPException(status_code=504, detail="Analysis timed out")
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("analyze_repo failed for %s/%s", owner, repo)
            raise HTTPException(status_code=502, detail=f"Analysis failed: {exc}") from exc
