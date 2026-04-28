"""Tests for Jira REST native tools (``ask`` / ``chat``)."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import devassist.orchestrator.native_jira_tools as nj
from devassist.orchestrator.native_jira_tools import (
    build_jira_native_tool_schemas,
    resolve_jira_rest_credentials,
    run_jira_native_tool,
)


@pytest.fixture
def jira_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://acme.atlassian.net")
    monkeypatch.setenv("ATLASSIAN_EMAIL", "me@acme.com")
    monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret-token")


def test_resolve_prefers_atlassian_vars(jira_env: None) -> None:
    r = resolve_jira_rest_credentials()
    assert r is not None
    base, (email, tok) = r
    assert base == "https://acme.atlassian.net"
    assert email == "me@acme.com"
    assert tok == "secret-token"


def test_schemas_empty_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("ATLASSIAN_BASE_URL", "ATLASSIAN_EMAIL", "ATLASSIAN_API_TOKEN", "JIRA_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("JIRA_USERNAME", raising=False)
    monkeypatch.delenv("JIRA_PERSONAL_TOKEN", raising=False)
    assert build_jira_native_tool_schemas() == []


def test_schemas_when_configured(jira_env: None) -> None:
    names = {t.name for t in build_jira_native_tool_schemas()}
    assert names == {"jira_rest_search", "jira_rest_get_issue"}


@pytest.mark.asyncio
async def test_run_search_uses_enhanced_jql(jira_env: None) -> None:
    with patch.object(nj, "fetch_jql_search_jql_page", new_callable=AsyncMock) as mock_page:
        mock_page.return_value = (
            [
                {
                    "key": "P-1",
                    "fields": {
                        "summary": "Hello",
                        "status": {"name": "To Do"},
                        "assignee": {"displayName": "Sam"},
                        "updated": "2024-06-01T12:00:00.000+0000",
                    },
                }
            ],
            None,
            True,
        )
        out = await run_jira_native_tool("jira_rest_search", {"jql": "project = P", "max_results": 5})
    assert out is not None
    assert not out.is_error
    assert "P-1" in (out.content or "")
    assert mock_page.await_count >= 1


@pytest.mark.asyncio
async def test_run_unknown_tool_returns_none(jira_env: None) -> None:
    assert await run_jira_native_tool("github_list_repos", {}) is None


@pytest.mark.asyncio
async def test_get_issue_via_rest(jira_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rest/api/3/issue/DEMO-9"):
            return httpx.Response(
                200,
                json={
                    "key": "DEMO-9",
                    "fields": {
                        "summary": "Fix bug",
                        "description": "plain",
                        "status": {"name": "Open"},
                        "assignee": {"displayName": "Pat"},
                    },
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

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
        HTTPStatusError=httpx.HTTPStatusError,
        RequestError=httpx.RequestError,
    )
    monkeypatch.setattr(nj, "httpx", fake)

    out = await run_jira_native_tool("jira_rest_get_issue", {"issue_key": "DEMO-9"})
    assert out is not None
    assert not out.is_error
    assert "DEMO-9" in (out.content or "")
    assert "Fix bug" in (out.content or "")
