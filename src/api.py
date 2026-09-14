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

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .analyze import analyze_repo
from .schema import Report

logger = logging.getLogger(__name__)

app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/?$"
)
_ANALYSIS_TIMEOUT = 120  # seconds
_ANALYZE_RATE_LIMIT = "10/hour"


@app.exception_handler(RateLimitExceeded)
def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Return a clear 429 when a client exceeds the /analyze rate limit."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": (
                f"Rate limit exceeded ({_ANALYZE_RATE_LIMIT} per IP). "
                "Please wait before submitting another analysis request."
            )
        },
    )


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
@limiter.limit(_ANALYZE_RATE_LIMIT)
def analyze(request: Request, body: AnalyzeRequest) -> Report:
    """Validate a GitHub repo URL, run analysis in a thread, and return the Report.

    Returns 400 for a malformed URL, 413 if the repo data is too large, 429 if
    the caller has exceeded the per-IP rate limit, 504 on timeout, and 502 for
    any other internal failure.
    """
    # TEMPORARY: verify Render's proxy headers resolve to the real visitor IP.
    print(
        f"resolved client ip: {request.client.host}, "
        f"x-forwarded-for: {request.headers.get('x-forwarded-for')}"
    )
    match = _GITHUB_URL_RE.match(body.repo_url.strip())
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
