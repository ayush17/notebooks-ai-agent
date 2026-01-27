"""Integration tests for JiraAdapter.

TDD: These tests are written FIRST and verify the JIRA API token
authentication and issue retrieval functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from devassist.adapters.jira import JiraAdapter
from devassist.adapters.errors import AuthenticationError, SourceUnavailableError
from devassist.models.context import ContextItem, SourceType


class TestJiraAdapterContract:
    """Verify JiraAdapter fulfills the ContextSourceAdapter contract."""

    def test_source_type_is_jira(self) -> None:
        """JiraAdapter should have JIRA source type."""
        adapter = JiraAdapter()
        assert adapter.source_type == SourceType.JIRA

    def test_display_name_is_jira(self) -> None:
        """JiraAdapter should have 'JIRA' display name."""
        adapter = JiraAdapter()
        assert adapter.display_name == "JIRA"

    def test_required_config_fields(self) -> None:
        """JiraAdapter should require url, email, and api_token."""
        fields = JiraAdapter.get_required_config_fields()
        assert "url" in fields
        assert "email" in fields
        assert "api_token" in fields


class TestJiraAuthentication:
    """Tests for JIRA API token authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_with_valid_credentials(self) -> None:
        """Should authenticate successfully with valid API token."""
        adapter = JiraAdapter()

        with patch("devassist.adapters.jira.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"displayName": "Test User"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await adapter.authenticate({
                "url": "https://company.atlassian.net",
                "email": "user@company.com",
                "api_token": "valid-token",
            })

        assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_raises_on_invalid_credentials(self) -> None:
        """Should raise AuthenticationError when credentials are invalid."""
        adapter = JiraAdapter()

        with patch("devassist.adapters.jira.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(AuthenticationError):
                await adapter.authenticate({
                    "url": "https://company.atlassian.net",
                    "email": "user@company.com",
                    "api_token": "invalid-token",
                })

    @pytest.mark.asyncio
    async def test_test_connection_returns_true_when_authenticated(self) -> None:
        """Should return True when connection is healthy."""
        adapter = JiraAdapter()
        adapter._url = "https://company.atlassian.net"
        adapter._auth = ("user@company.com", "valid-token")

        with patch("devassist.adapters.jira.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"self": "https://company.atlassian.net/rest/api/3/myself"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await adapter.test_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_raises_when_not_authenticated(self) -> None:
        """Should raise SourceUnavailableError when not authenticated."""
        adapter = JiraAdapter()
        adapter._url = None
        adapter._auth = None

        with pytest.raises(SourceUnavailableError):
            await adapter.test_connection()


class TestJiraFetchItems:
    """Tests for fetching issues from JIRA."""

    @pytest.mark.asyncio
    async def test_fetch_items_returns_context_items(self) -> None:
        """Should yield ContextItem objects for each issue."""
        adapter = JiraAdapter()
        adapter._url = "https://company.atlassian.net"
        adapter._auth = ("user@company.com", "valid-token")

        with patch("devassist.adapters.jira.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "issues": [
                    {
                        "key": "PROJ-123",
                        "fields": {
                            "summary": "Fix bug in login",
                            "description": "Users cannot login...",
                            "assignee": {"displayName": "John Doe"},
                            "status": {"name": "In Progress"},
                            "updated": "2024-01-15T10:30:00.000+0000",
                        }
                    },
                    {
                        "key": "PROJ-124",
                        "fields": {
                            "summary": "Add feature X",
                            "description": "Implement new feature...",
                            "assignee": None,
                            "status": {"name": "Open"},
                            "updated": "2024-01-14T09:00:00.000+0000",
                        }
                    },
                ]
            }
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            items = []
            async for item in adapter.fetch_items(limit=10):
                items.append(item)

        assert len(items) == 2
        assert all(isinstance(item, ContextItem) for item in items)
        assert all(item.source_type == SourceType.JIRA for item in items)

    @pytest.mark.asyncio
    async def test_fetch_items_includes_issue_key_in_title(self) -> None:
        """Should include JIRA issue key in item title."""
        adapter = JiraAdapter()
        adapter._url = "https://company.atlassian.net"
        adapter._auth = ("user@company.com", "valid-token")

        with patch("devassist.adapters.jira.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "issues": [
                    {
                        "key": "PROJ-123",
                        "fields": {
                            "summary": "Test issue",
                            "updated": "2024-01-15T10:30:00.000+0000",
                            "status": {"name": "Open"},
                        }
                    }
                ]
            }
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            items = []
            async for item in adapter.fetch_items(limit=10):
                items.append(item)

        assert len(items) == 1
        assert "PROJ-123" in items[0].title or items[0].id == "PROJ-123"
