"""Tests for JiraAdapter (enhanced JQL search + token auth)."""

from __future__ import annotations

import types

import httpx
import pytest

import devassist.adapters.jira as jira_module
from devassist.adapters.jira import JiraAdapter
from devassist.jira_enhanced_search import JQL_SEARCH_PATH


def _make_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rest/api/3/myself"):
            return httpx.Response(200, json={"accountId": "x", "displayName": "User"})
        if request.url.path.endswith(JQL_SEARCH_PATH):
            assert "jql" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "issues": [
                        {
                            "key": "TST-1",
                            "fields": {
                                "summary": "Fix thing",
                                "description": "plain text body",
                                "assignee": {"displayName": "Alice"},
                                "status": {"name": "In Progress"},
                                "priority": {"name": "Major"},
                                "issuetype": {"name": "Task"},
                                "updated": "2024-01-15T10:30:00.000+0000",
                            },
                        }
                    ],
                    "isLast": True,
                },
            )
        return httpx.Response(404, json={"error": request.url.path})

    return httpx.MockTransport(handler)


@pytest.fixture
def patched_httpx_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace ``jira`` module's ``httpx`` binding so we do not patch the global httpx package."""

    transport = _make_transport()

    def _client_factory(**kwargs: object) -> object:
        inner = httpx.AsyncClient(transport=transport, **kwargs)

        class _CM:
            async def __aenter__(self) -> httpx.AsyncClient:
                return inner

            async def __aexit__(self, *_a: object) -> None:
                await inner.aclose()

        return _CM()

    fake = types.SimpleNamespace(
        AsyncClient=_client_factory,
        RequestError=httpx.RequestError,
        HTTPStatusError=httpx.HTTPStatusError,
    )
    monkeypatch.setattr(jira_module, "httpx", fake)


@pytest.mark.asyncio
async def test_fetch_items_uses_search_jql(patched_httpx_client: None) -> None:
    adapter = JiraAdapter()
    await adapter.authenticate(
        {
            "url": "https://example.atlassian.net",
            "email": "a@example.com",
            "api_token": "tok",
        }
    )
    items = [x async for x in adapter.fetch_items(limit=10)]
    assert len(items) == 1
    assert items[0].id == "TST-1"
    assert "Fix thing" in items[0].title
    assert items[0].content == "plain text body"
    assert items[0].author == "Alice"
    assert items[0].metadata["status"] == "In Progress"
