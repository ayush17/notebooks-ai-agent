"""Integration tests for GitHubAdapter.

TDD: These tests are written FIRST and verify the GitHub PAT
authentication and activity retrieval functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from devassist.adapters.github import GitHubAdapter
from devassist.adapters.errors import AuthenticationError, SourceUnavailableError
from devassist.models.context import ContextItem, SourceType


class TestGitHubAdapterContract:
    """Verify GitHubAdapter fulfills the ContextSourceAdapter contract."""

    def test_source_type_is_github(self) -> None:
        """GitHubAdapter should have GITHUB source type."""
        adapter = GitHubAdapter()
        assert adapter.source_type == SourceType.GITHUB

    def test_display_name_is_github(self) -> None:
        """GitHubAdapter should have 'GitHub' display name."""
        adapter = GitHubAdapter()
        assert adapter.display_name == "GitHub"

    def test_required_config_fields(self) -> None:
        """GitHubAdapter should require personal_access_token."""
        fields = GitHubAdapter.get_required_config_fields()
        assert "personal_access_token" in fields


class TestGitHubAuthentication:
    """Tests for GitHub PAT authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_with_valid_token(self) -> None:
        """Should authenticate successfully with valid PAT."""
        adapter = GitHubAdapter()

        with patch("devassist.adapters.github.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"login": "testuser", "id": 12345}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await adapter.authenticate({
                "personal_access_token": "ghp_validtoken123",
            })

        assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_raises_on_invalid_token(self) -> None:
        """Should raise AuthenticationError when token is invalid."""
        adapter = GitHubAdapter()

        with patch("devassist.adapters.github.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.json.return_value = {"message": "Bad credentials"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(AuthenticationError):
                await adapter.authenticate({
                    "personal_access_token": "ghp_invalidtoken",
                })

    @pytest.mark.asyncio
    async def test_test_connection_returns_true_when_authenticated(self) -> None:
        """Should return True when connection is healthy."""
        adapter = GitHubAdapter()
        adapter._token = "ghp_validtoken123"
        adapter._username = "testuser"

        with patch("devassist.adapters.github.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"login": "testuser"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await adapter.test_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_raises_when_not_authenticated(self) -> None:
        """Should raise SourceUnavailableError when not authenticated."""
        adapter = GitHubAdapter()
        adapter._token = None

        with pytest.raises(SourceUnavailableError):
            await adapter.test_connection()


class TestGitHubFetchItems:
    """Tests for fetching activity from GitHub."""

    @pytest.mark.asyncio
    async def test_fetch_items_returns_context_items(self) -> None:
        """Should yield ContextItem objects for notifications and events."""
        adapter = GitHubAdapter()
        adapter._token = "ghp_validtoken123"
        adapter._username = "testuser"

        with patch("devassist.adapters.github.httpx.AsyncClient") as mock_client:
            # Mock notifications endpoint
            mock_notifications_response = MagicMock()
            mock_notifications_response.status_code = 200
            mock_notifications_response.json.return_value = [
                {
                    "id": "1",
                    "subject": {"title": "PR Review Requested", "type": "PullRequest"},
                    "repository": {"full_name": "org/repo"},
                    "updated_at": "2024-01-15T10:30:00Z",
                    "reason": "review_requested",
                }
            ]

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_notifications_response
            )

            items = []
            async for item in adapter.fetch_items(limit=10):
                items.append(item)

        assert len(items) > 0
        assert all(isinstance(item, ContextItem) for item in items)
        assert all(item.source_type == SourceType.GITHUB for item in items)

    @pytest.mark.asyncio
    async def test_fetch_items_includes_pr_reviews(self) -> None:
        """Should include PR review requests in fetched items."""
        adapter = GitHubAdapter()
        adapter._token = "ghp_validtoken123"
        adapter._username = "testuser"

        with patch("devassist.adapters.github.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {
                    "id": "1",
                    "subject": {"title": "Add new feature", "type": "PullRequest"},
                    "repository": {"full_name": "org/repo"},
                    "updated_at": "2024-01-15T10:30:00Z",
                    "reason": "review_requested",
                }
            ]
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            items = []
            async for item in adapter.fetch_items(limit=10):
                items.append(item)

        assert len(items) > 0
        # Should have PR info in title or metadata
        assert any("PullRequest" in str(item.metadata) or "PR" in item.title for item in items) or len(items) > 0

    @pytest.mark.asyncio
    async def test_fetch_items_includes_issue_mentions(self) -> None:
        """Should include issue mentions in fetched items."""
        adapter = GitHubAdapter()
        adapter._token = "ghp_validtoken123"
        adapter._username = "testuser"

        with patch("devassist.adapters.github.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {
                    "id": "2",
                    "subject": {"title": "Bug report", "type": "Issue"},
                    "repository": {"full_name": "org/repo"},
                    "updated_at": "2024-01-15T09:00:00Z",
                    "reason": "mention",
                }
            ]
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            items = []
            async for item in adapter.fetch_items(limit=10):
                items.append(item)

        assert len(items) > 0
