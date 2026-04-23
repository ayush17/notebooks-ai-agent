"""Jira Cloud enhanced JQL issue search (GET ``/rest/api/3/search/jql``).

Replaces deprecated ``GET /rest/api/3/search``; see Atlassian Issue search API:
https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/
"""

from __future__ import annotations

from typing import Any, cast

import httpx

JQL_SEARCH_PATH = "/rest/api/3/search/jql"


async def fetch_jql_search_jql_page(
    client: httpx.AsyncClient,
    base_url: str,
    auth: tuple[str, str],
    *,
    jql: str,
    max_results: int,
    fields: str,
    next_page_token: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, bool]:
    """One page of enhanced JQL search.

    Returns:
        Tuple of ``(issues, next_page_token, is_last)`` where ``next_page_token`` is
        passed on the following request until ``is_last`` is True.
    """
    params: dict[str, Any] = {
        "jql": jql,
        "maxResults": max_results,
        "fields": fields,
    }
    if next_page_token:
        params["nextPageToken"] = next_page_token

    r = await client.get(
        f"{base_url.rstrip('/')}{JQL_SEARCH_PATH}",
        auth=auth,
        params=params,
    )
    r.raise_for_status()
    data = cast(dict[str, Any], r.json())
    issues_raw = data.get("issues")
    issues: list[dict[str, Any]] = list(issues_raw) if isinstance(issues_raw, list) else []

    token_raw = data.get("nextPageToken")
    next_tok: str | None = None
    if isinstance(token_raw, str) and token_raw.strip():
        next_tok = token_raw.strip()

    is_last = bool(data["isLast"]) if "isLast" in data else next_tok is None

    return issues, next_tok, is_last
