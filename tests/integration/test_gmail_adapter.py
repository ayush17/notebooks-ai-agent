"""Integration tests for GmailAdapter.

TDD: These tests are written FIRST and verify the Gmail OAuth flow
and email retrieval functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from devassist.adapters.gmail import GmailAdapter
from devassist.adapters.errors import AuthenticationError, SourceUnavailableError
from devassist.models.context import ContextItem, SourceType


class TestGmailAdapterContract:
    """Verify GmailAdapter fulfills the ContextSourceAdapter contract."""

    def test_source_type_is_gmail(self) -> None:
        """GmailAdapter should have GMAIL source type."""
        adapter = GmailAdapter()
        assert adapter.source_type == SourceType.GMAIL

    def test_display_name_is_gmail(self) -> None:
        """GmailAdapter should have 'Gmail' display name."""
        adapter = GmailAdapter()
        assert adapter.display_name == "Gmail"

    def test_required_config_fields(self) -> None:
        """GmailAdapter should require credentials_file."""
        fields = GmailAdapter.get_required_config_fields()
        assert "credentials_file" in fields


class TestGmailAuthentication:
    """Tests for Gmail OAuth2 authentication flow."""

    @pytest.mark.asyncio
    async def test_authenticate_with_valid_credentials(self, tmp_path: Path) -> None:
        """Should authenticate successfully with valid OAuth credentials."""
        adapter = GmailAdapter()

        # Mock the Google auth flow and GOOGLE_API_AVAILABLE
        with patch("devassist.adapters.gmail.GOOGLE_API_AVAILABLE", True), \
             patch("devassist.adapters.gmail.InstalledAppFlow") as mock_flow, \
             patch("devassist.adapters.gmail.build") as mock_build, \
             patch("devassist.adapters.gmail.Credentials") as mock_creds_class:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.to_json.return_value = "{}"
            mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = mock_creds
            mock_creds_class.from_authorized_user_file.side_effect = Exception("No token")

            result = await adapter.authenticate({
                "credentials_file": str(tmp_path / "credentials.json"),
            })

        assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_raises_on_invalid_credentials(self) -> None:
        """Should raise AuthenticationError when OAuth fails."""
        adapter = GmailAdapter()

        with patch("devassist.adapters.gmail.GOOGLE_API_AVAILABLE", True), \
             patch("devassist.adapters.gmail.InstalledAppFlow") as mock_flow:
            mock_flow.from_client_secrets_file.side_effect = Exception("Invalid credentials")

            with pytest.raises(AuthenticationError):
                await adapter.authenticate({
                    "credentials_file": "/nonexistent/credentials.json",
                })

    @pytest.mark.asyncio
    async def test_authenticate_raises_when_google_api_not_available(self) -> None:
        """Should raise AuthenticationError when Google API libraries not installed."""
        adapter = GmailAdapter()

        with patch("devassist.adapters.gmail.GOOGLE_API_AVAILABLE", False):
            with pytest.raises(AuthenticationError) as exc_info:
                await adapter.authenticate({
                    "credentials_file": "/path/to/creds.json",
                })
            assert "Google API libraries not installed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_test_connection_returns_true_when_authenticated(self) -> None:
        """Should return True when connection is healthy."""
        adapter = GmailAdapter()
        adapter._creds = MagicMock(valid=True)

        with patch("devassist.adapters.gmail.build") as mock_build:
            mock_service = MagicMock()
            mock_service.users.return_value.getProfile.return_value.execute.return_value = {
                "emailAddress": "test@gmail.com"
            }
            mock_build.return_value = mock_service

            result = await adapter.test_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_raises_when_not_authenticated(self) -> None:
        """Should raise SourceUnavailableError when not authenticated."""
        adapter = GmailAdapter()
        adapter._creds = None

        with pytest.raises(SourceUnavailableError):
            await adapter.test_connection()


class TestGmailFetchItems:
    """Tests for fetching emails from Gmail."""

    @pytest.mark.asyncio
    async def test_fetch_items_returns_context_items(self) -> None:
        """Should yield ContextItem objects for each email."""
        adapter = GmailAdapter()
        adapter._creds = MagicMock(valid=True)

        with patch("devassist.adapters.gmail.build") as mock_build:
            mock_service = MagicMock()
            mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
                "messages": [{"id": "msg1"}, {"id": "msg2"}]
            }
            mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
                "id": "msg1",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Test Email"},
                        {"name": "From", "value": "sender@example.com"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                    ]
                },
                "snippet": "Email content preview..."
            }
            mock_build.return_value = mock_service
            adapter._service = mock_service

            items = []
            async for item in adapter.fetch_items(limit=10):
                items.append(item)

        assert len(items) > 0
        assert all(isinstance(item, ContextItem) for item in items)
        assert all(item.source_type == SourceType.GMAIL for item in items)

    @pytest.mark.asyncio
    async def test_fetch_items_respects_limit(self) -> None:
        """Should not fetch more than the specified limit."""
        adapter = GmailAdapter()
        adapter._creds = MagicMock(valid=True)

        with patch("devassist.adapters.gmail.build") as mock_build:
            # Return more messages than limit
            mock_service = MagicMock()
            mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
                "messages": [{"id": f"msg{i}"} for i in range(20)]
            }
            mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
                "id": "msg1",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Test"},
                        {"name": "From", "value": "sender@example.com"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                    ]
                },
                "snippet": "Content..."
            }
            mock_build.return_value = mock_service
            adapter._service = mock_service

            items = []
            async for item in adapter.fetch_items(limit=5):
                items.append(item)

        assert len(items) <= 5
