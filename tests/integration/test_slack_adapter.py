"""Integration tests for SlackAdapter.

TDD: These tests are written FIRST and verify the Slack bot token
authentication and message retrieval functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from devassist.adapters.slack import SlackAdapter
from devassist.adapters.errors import AuthenticationError, SourceUnavailableError
from devassist.models.context import ContextItem, SourceType


class TestSlackAdapterContract:
    """Verify SlackAdapter fulfills the ContextSourceAdapter contract."""

    def test_source_type_is_slack(self) -> None:
        """SlackAdapter should have SLACK source type."""
        adapter = SlackAdapter()
        assert adapter.source_type == SourceType.SLACK

    def test_display_name_is_slack(self) -> None:
        """SlackAdapter should have 'Slack' display name."""
        adapter = SlackAdapter()
        assert adapter.display_name == "Slack"

    def test_required_config_fields(self) -> None:
        """SlackAdapter should require bot_token."""
        fields = SlackAdapter.get_required_config_fields()
        assert "bot_token" in fields


class TestSlackAuthentication:
    """Tests for Slack bot token authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_with_valid_token(self) -> None:
        """Should authenticate successfully with valid bot token."""
        adapter = SlackAdapter()

        with patch("devassist.adapters.slack.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True, "user": "bot_user"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await adapter.authenticate({
                "bot_token": "xoxb-valid-token",
            })

        assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_raises_on_invalid_token(self) -> None:
        """Should raise AuthenticationError when token is invalid."""
        adapter = SlackAdapter()

        with patch("devassist.adapters.slack.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": False, "error": "invalid_auth"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(AuthenticationError):
                await adapter.authenticate({
                    "bot_token": "xoxb-invalid-token",
                })

    @pytest.mark.asyncio
    async def test_test_connection_returns_true_when_authenticated(self) -> None:
        """Should return True when connection is healthy."""
        adapter = SlackAdapter()
        adapter._token = "xoxb-valid-token"

        with patch("devassist.adapters.slack.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await adapter.test_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_raises_when_not_authenticated(self) -> None:
        """Should raise SourceUnavailableError when not authenticated."""
        adapter = SlackAdapter()
        adapter._token = None

        with pytest.raises(SourceUnavailableError):
            await adapter.test_connection()


class TestSlackFetchItems:
    """Tests for fetching messages from Slack."""

    @pytest.mark.asyncio
    async def test_fetch_items_returns_context_items(self) -> None:
        """Should yield ContextItem objects for each message."""
        adapter = SlackAdapter()
        adapter._token = "xoxb-valid-token"

        with patch("devassist.adapters.slack.httpx.AsyncClient") as mock_client:
            # Mock conversations.list
            mock_channels_response = MagicMock()
            mock_channels_response.status_code = 200
            mock_channels_response.json.return_value = {
                "ok": True,
                "channels": [{"id": "C123", "name": "general"}]
            }

            # Mock conversations.history
            mock_history_response = MagicMock()
            mock_history_response.status_code = 200
            mock_history_response.json.return_value = {
                "ok": True,
                "messages": [
                    {"ts": "1234567890.000001", "text": "Hello!", "user": "U123"},
                    {"ts": "1234567890.000002", "text": "Hi there!", "user": "U456"},
                ]
            }

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=[mock_channels_response, mock_history_response]
            )

            items = []
            async for item in adapter.fetch_items(limit=10):
                items.append(item)

        assert len(items) > 0
        assert all(isinstance(item, ContextItem) for item in items)
        assert all(item.source_type == SourceType.SLACK for item in items)

    @pytest.mark.asyncio
    async def test_fetch_items_includes_channel_context(self) -> None:
        """Should include channel information in context items."""
        adapter = SlackAdapter()
        adapter._token = "xoxb-valid-token"

        with patch("devassist.adapters.slack.httpx.AsyncClient") as mock_client:
            mock_channels_response = MagicMock()
            mock_channels_response.status_code = 200
            mock_channels_response.json.return_value = {
                "ok": True,
                "channels": [{"id": "C123", "name": "important"}]
            }

            mock_history_response = MagicMock()
            mock_history_response.status_code = 200
            mock_history_response.json.return_value = {
                "ok": True,
                "messages": [{"ts": "1234567890.000001", "text": "Test", "user": "U123"}]
            }

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=[mock_channels_response, mock_history_response]
            )

            items = []
            async for item in adapter.fetch_items(limit=10):
                items.append(item)

        assert len(items) > 0
        # Channel info should be in metadata
        assert "channel" in items[0].metadata or items[0].title
