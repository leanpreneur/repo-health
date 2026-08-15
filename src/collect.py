"""
collect.py — fetches raw GitHub data for a public repository.

Provides collect_repo_data(owner, repo) -> dict with metadata, closed issues,
merged pull requests, and recent commits. Every API response is cached in .cache/
with a one-hour TTL so reruns do not consume rate-limit quota on unchanged data.

All text returned from GitHub is untrusted; callers must not eval or interpolate it.
"""

import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

_API = "https://api.github.com"
_CACHE_DIR = Path(".cache")
_CACHE_TTL = 3600  # seconds
_CONCURRENCY = 8   # max simultaneous GitHub requests


# ── cache ──────────────────────────────────────────────────────────────────────


def _cache_path(url: str) -> Path:
    return _CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest() + ".json")


def _cache_read(url: str) -> dict | None:
    path = _cache_path(url)
    if not path.exists() or time.time() - path.stat().st_mtime > _CACHE_TTL:
        return None
    return json.loads(path.read_text())


def _cache_write(url: str, payload: dict) -> None:
    _CACHE_DIR.mkdir(exist_ok=True)
    _cache_path(url).write_text(json.dumps(payload))


def _next_link(header: str) -> str | None:
    """Parse the 'next' URL out of a GitHub Link response header."""
    for part in header.split(","):
        segments = part.strip().split(";")
        if any(s.strip() == 'rel="next"' for s in segments[1:]):
            return segments[0].strip().strip("<>")
    return None


# ── HTTP layer ─────────────────────────────────────────────────────────────────


async def _get(
    client: httpx.AsyncClient,
    url: str,
    sem: asyncio.Semaphore,
    params: dict[str, str | int] | None = None,
) -> tuple[list | dict, str | None]:
    """GET one URL; return (body, next_link). Reads/writes .cache/. Prints rate-limit on live requests."""
    if params:
        cache_url = str(httpx.URL(url, params=sorted((k, str(v)) for k, v in params.items())))
    else:
        cache_url = url

    entry = _cache_read(cache_url)
    if entry is not None:
        return entry["data"], entry.get("next_link")

    async with sem:
        resp = await client.get(url, params=params)
    resp.raise_for_status()

    data = resp.json()
    next_page = _next_link(resp.headers.get("link", ""))
    print(f"rate-limit remaining={resp.headers.get('X-RateLimit-Remaining', '?')}  {cache_url}", file=sys.stderr)
    _cache_write(cache_url, {"data": data, "next_link": next_page})
    return data, next_page


async def _paginate(
    client: httpx.AsyncClient,
    url: str,
    sem: asyncio.Semaphore,
    params: dict[str, str | int],
    limit: int,
) -> list:
    """Collect up to `limit` items by following GitHub Link-header pagination."""
    results: list = []
    next_url: str | None = url
    next_params: dict[str, str | int] | None = params

    while next_url and len(results) < limit:
        page, next_url = await _get(client, next_url, sem, next_params)
        next_params = None  # subsequent page URLs already embed all query params
        results.extend(page)  # type: ignore[arg-type]

    return results[:limit]


# ── per-resource collectors ────────────────────────────────────────────────────


async def _collect_metadata(
    client: httpx.AsyncClient, owner: str, repo: str, sem: asyncio.Semaphore
) -> dict:
    data, _ = await _get(client, f"{_API}/repos/{owner}/{repo}", sem)
    return {
        "stars": data["stargazers_count"],
        "language": data["language"],
        "created_at": data["created_at"],
        "open_issues_count": data["open_issues_count"],
    }


async def _collect_issues(
    client: httpx.AsyncClient, owner: str, repo: str, sem: asyncio.Semaphore
) -> list[dict]:
    # The /issues endpoint returns PRs too; over-fetch so we end up with 100 real issues.
    raw = await _paginate(
        client, f"{_API}/repos/{owner}/{repo}/issues", sem,
        params={"state": "closed", "per_page": 100},
        limit=500,
    )
    true_issues = [i for i in raw if "pull_request" not in i][:100]
    return [
        {
            "title": i["title"],
            "labels": [la["name"] for la in i["labels"]],
            "created_at": i["created_at"],
            "closed_at": i["closed_at"],
            "html_url": i["html_url"],
        }
        for i in true_issues
    ]


async def _collect_pull_requests(
    client: httpx.AsyncClient, owner: str, repo: str, sem: asyncio.Semaphore
) -> list[dict]:
    raw = await _paginate(
        client, f"{_API}/repos/{owner}/{repo}/pulls", sem,
        params={"state": "closed", "per_page": 100, "sort": "updated", "direction": "desc"},
        limit=300,
    )
    merged = [pr for pr in raw if pr.get("merged_at")][:100]

    async def _with_files(pr: dict) -> dict:
        # Fetch files and full PR detail concurrently; the list endpoint omits review_comments count.
        files_coro = _get(client, f"{_API}/repos/{owner}/{repo}/pulls/{pr['number']}/files", sem, params={"per_page": 100})
        detail_coro = _get(client, f"{_API}/repos/{owner}/{repo}/pulls/{pr['number']}", sem)
        (files, _), (detail, _) = await asyncio.gather(files_coro, detail_coro)
        return {
            "title": pr["title"],
            "author": pr["user"]["login"],
            "created_at": pr["created_at"],
            "merged_at": pr["merged_at"],
            "html_url": pr["html_url"],
            "review_comment_count": detail["review_comments"],
            "changed_files": [f["filename"] for f in files],  # type: ignore[index]
        }

    return list(await asyncio.gather(*[_with_files(pr) for pr in merged]))


async def _collect_commits(
    client: httpx.AsyncClient, owner: str, repo: str, sem: asyncio.Semaphore
) -> list[dict]:
    raw = await _paginate(
        client, f"{_API}/repos/{owner}/{repo}/commits", sem,
        params={"per_page": 100},
        limit=300,
    )

    async def _with_files(c: dict) -> dict:
        detail, _ = await _get(client, f"{_API}/repos/{owner}/{repo}/commits/{c['sha']}", sem)
        return {
            "author": detail["commit"]["author"]["name"],
            "timestamp": detail["commit"]["author"]["date"],
            "html_url": detail["html_url"],
            "changed_files": [f["filename"] for f in detail.get("files", [])],
        }

    return list(await asyncio.gather(*[_with_files(c) for c in raw]))


# ── public interface ───────────────────────────────────────────────────────────


async def _run(owner: str, repo: str) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    sem = asyncio.Semaphore(_CONCURRENCY)
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        meta, issues, prs, commits = await asyncio.gather(
            _collect_metadata(client, owner, repo, sem),
            _collect_issues(client, owner, repo, sem),
            _collect_pull_requests(client, owner, repo, sem),
            _collect_commits(client, owner, repo, sem),
        )

    return {"metadata": meta, "issues": issues, "pull_requests": prs, "commits": commits}


def collect_repo_data(owner: str, repo: str) -> dict:
    """Fetch metadata, issues, pull requests, and commits for a public GitHub repository."""
    return asyncio.run(_run(owner, repo))


if __name__ == "__main__":
    if len(sys.argv) != 2 or "/" not in sys.argv[1]:
        print("Usage: python src/collect.py owner/repo", file=sys.stderr)
        sys.exit(1)
    _owner, _repo = sys.argv[1].split("/", 1)
    print(json.dumps(collect_repo_data(_owner, _repo), indent=2, default=str))
