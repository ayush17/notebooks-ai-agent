"""GitHub REST helpers: duplicate PR detection and repo URL parsing."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx

_GITHUB_REPO_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


def parse_github_owner_repo(github_url: str) -> tuple[str, str] | None:
    """Return ``(owner, repo)`` for a typical GitHub HTTPS URL."""
    u = (github_url or "").strip()
    m = _GITHUB_REPO_RE.match(u)
    if not m:
        return None
    return m.group("owner"), m.group("repo")


def search_pull_requests_with_text(
    token: str,
    *,
    owner: str,
    repo: str,
    text: str,
    per_page: int = 20,
) -> list[dict[str, Any]]:
    """Return GitHub search hits for open/closed PRs whose body/title matches ``text`` (e.g. CVE id)."""
    q = f'repo:{owner}/{repo} is:pr "{text}"'
    url = "https://api.github.com/search/issues"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    items: list[dict[str, Any]] = []
    with httpx.Client(timeout=60.0) as client:
        r = client.get(url, headers=headers, params={"q": q, "per_page": per_page})
        r.raise_for_status()
        data = r.json()
        raw = data.get("items")
        if isinstance(raw, list):
            items = [x for x in raw if isinstance(x, dict)]
    return items


def any_pull_requests_for_cve(
    token: str,
    *,
    owner: str,
    repo: str,
    cve_id: str,
) -> bool:
    """True if the GitHub search finds at least one PR mentioning the CVE."""
    return len(search_pull_requests_with_text(token, owner=owner, repo=repo, text=cve_id)) > 0


def github_browse_url(base_url: str, issue_key: str) -> str:
    """Best-effort browse URL for a Jira issue (Cloud)."""
    parsed = urlparse(base_url)
    host = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else base_url.rstrip("/")
    return f"{host.rstrip('/')}/browse/{issue_key}"
