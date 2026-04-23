"""Tests for Jira enhanced JQL search (GET /rest/api/3/search/jql)."""

from __future__ import annotations

import httpx
import pytest

from devassist.jira_enhanced_search import JQL_SEARCH_PATH, fetch_jql_search_jql_page


def _handler_two_pages(request: httpx.Request) -> httpx.Response:
    assert request.url.path.endswith(JQL_SEARCH_PATH)
    token = request.url.params.get("nextPageToken")
    if token is None:
        return httpx.Response(
            200,
            json={
                "issues": [{"key": "A-1", "fields": {"summary": "one"}}],
                "nextPageToken": "cursor-2",
                "isLast": False,
            },
        )
    assert token == "cursor-2"
    return httpx.Response(
        200,
        json={
            "issues": [{"key": "A-2", "fields": {"summary": "two"}}],
            "isLast": True,
        },
    )


@pytest.mark.asyncio
async def test_fetch_jql_search_paginates_with_next_page_token() -> None:
    transport = httpx.MockTransport(_handler_two_pages)
    async with httpx.AsyncClient(transport=transport) as client:
        issues1, tok1, last1 = await fetch_jql_search_jql_page(
            client,
            "https://example.atlassian.net",
            ("user@x.com", "token"),
            jql="project = FOO",
            max_results=50,
            fields="summary",
            next_page_token=None,
        )
        assert [i["key"] for i in issues1] == ["A-1"]
        assert tok1 == "cursor-2"
        assert last1 is False

        issues2, tok2, last2 = await fetch_jql_search_jql_page(
            client,
            "https://example.atlassian.net",
            ("user@x.com", "token"),
            jql="project = FOO",
            max_results=50,
            fields="summary",
            next_page_token=tok1,
        )
        assert [i["key"] for i in issues2] == ["A-2"]
        assert tok2 is None
        assert last2 is True


@pytest.mark.asyncio
async def test_fetch_jql_search_empty_issues_is_last_without_token() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"issues": [], "isLast": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        issues, tok, last = await fetch_jql_search_jql_page(
            client,
            "https://example.atlassian.net",
            ("e", "t"),
            jql="project = X",
            max_results=10,
            fields="summary",
        )
        assert issues == []
        assert tok is None
        assert last is True
