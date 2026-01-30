"""Unit tests for ClaudeClient.

Tests the Claude Agent SDK wrapper client for session management and calling.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from devassist.ai.claude_client import ClaudeClient, ClaudeSession
from devassist.models.config import ClientConfig


class TestClaudeSession:
    """Tests for ClaudeSession data model."""

    def test_claude_session_creation(self):
        """Test creating a ClaudeSession object."""
        session = ClaudeSession(
            session_id="test-session-123",
            created_at=datetime.now(),
            last_used=datetime.now(),
            resources=["gmail", "slack"],
            turns=0,
        )

        assert session.session_id == "test-session-123"
        assert session.resources == ["gmail", "slack"]
        assert session.turns == 0

    def test_claude_session_serialization(self):
        """Test serializing ClaudeSession to dict."""
        now = datetime.now()
        session = ClaudeSession(
            session_id="test-session-123",
            created_at=now,
            last_used=now,
            resources=["gmail"],
            turns=5,
        )

        data = session.to_dict()
        assert data["session_id"] == "test-session-123"
        assert data["resources"] == ["gmail"]
        assert data["turns"] == 5
        assert "created_at" in data
        assert "last_used" in data

    def test_claude_session_deserialization(self):
        """Test deserializing ClaudeSession from dict."""
        data = {
            "session_id": "test-session-123",
            "created_at": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
            "resources": ["gmail", "slack"],
            "turns": 3,
        }

        session = ClaudeSession.from_dict(data)
        assert session.session_id == "test-session-123"
        assert session.resources == ["gmail", "slack"]
        assert session.turns == 3


class TestClaudeClient:
    """Tests for ClaudeClient.

    NOTE: Some tests in this class are outdated and test the old ClaudeClient
    architecture with instance-level SDK clients and session management.
    The new static session store functionality is comprehensively tested in
    test_claude_client_static_sessions.py and test_config.py.
    """

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        from devassist.models.context import SourceType

        config = ClientConfig(
            sources=[SourceType.GMAIL, SourceType.SLACK],
            source_configs={
                "gmail": {"enabled": True, "credentials_file": "/path/to/gmail.json"},
                "slack": {"enabled": True, "token": "xoxb-test-token"},
            }
        )
        return config

    @pytest.fixture
    def client(self, mock_config):
        """Create a ClaudeClient instance."""
        # Clear session store before each test
        ClaudeClient.clear_all_sessions()

        # Mock the Claude SDK to prevent actual calls
        with patch('claude_agent_sdk.ClaudeSDKClient') as mock_sdk_class:
            mock_sdk_instance = MagicMock()
            mock_sdk_class.return_value = mock_sdk_instance
            yield ClaudeClient(config=mock_config)

    def test_client_initialization(self, mock_config):
        """Test ClaudeClient initializes correctly."""
        with patch('claude_agent_sdk.ClaudeSDKClient') as mock_sdk_class:
            mock_sdk_instance = MagicMock()
            mock_sdk_class.return_value = mock_sdk_instance

            client = ClaudeClient(config=mock_config)
            assert client.config == mock_config
            # Should auto-create a session
            assert client.session is not None
            assert client.session.session_id is not None


    @pytest.mark.skip(reason="Test needs update for new static session architecture")
    @pytest.mark.asyncio
    async def test_create_session(self, client):
        """Test creating a new Claude session."""
        with patch.object(client._sdk_client, "connect", new_callable=AsyncMock) as mock_connect:
            session = await client.create_session(
                resources=["gmail", "slack"], output_format="markdown"
            )

            assert session.session_id is not None
            assert session.resources == ["gmail", "slack"]
            assert session.turns == 0
            mock_connect.assert_called_once()

    @pytest.mark.skip(reason="Test needs update for new static session architecture")
    @pytest.mark.asyncio
    async def test_make_call_new_session(self, client):
        """Test making a call without an existing session creates one."""
        with patch.object(client._sdk_client, "connect", new_callable=AsyncMock), patch.object(
            client._sdk_client, "query", new_callable=AsyncMock
        ), patch.object(
            client._sdk_client, "receive_response"
        ) as mock_receive:
            # Mock response
            mock_message = MagicMock()
            mock_message.content = [MagicMock(text="Test response")]

            async def async_iter():
                yield mock_message

            mock_receive.return_value = async_iter()

            response = await client.make_call("Generate my morning brief")

            assert response is not None
            assert "Test response" in response

    @pytest.mark.skip(reason="Test needs update for new static session architecture")
    @pytest.mark.asyncio
    async def test_make_call_existing_session(self, client):
        """Test making a call with an existing session ID."""
        # First create a session
        with patch.object(client._sdk_client, "connect", new_callable=AsyncMock):
            session = await client.create_session(resources=["gmail"])

        # Now make a call with that session
        with patch.object(client._sdk_client, "query", new_callable=AsyncMock), patch.object(
            client._sdk_client, "receive_response"
        ) as mock_receive:
            mock_message = MagicMock()
            mock_message.content = [MagicMock(text="Follow-up response")]

            async def async_iter():
                yield mock_message

            mock_receive.return_value = async_iter()

            response = await client.make_call(
                "Follow up question", session_id=session.session_id
            )

            assert "Follow-up response" in response

    @pytest.mark.skip(reason="Test needs update for new static session architecture")
    @pytest.mark.asyncio
    async def test_resume_session(self, client):
        """Test resuming an existing session."""
        # Create a session first
        with patch.object(client._sdk_client, "connect", new_callable=AsyncMock):
            original_session = await client.create_session(resources=["gmail"])
            original_session.turns = 5

        # Store it
        client._active_sessions[original_session.session_id] = original_session

        # Resume it
        resumed_session = await client.resume_session(original_session.session_id)

        assert resumed_session.session_id == original_session.session_id
        assert resumed_session.turns == 5

    @pytest.mark.skip(reason="Test needs update for new static session architecture")
    @pytest.mark.asyncio
    async def test_resume_nonexistent_session_fails(self, client):
        """Test resuming a non-existent session raises error."""
        with pytest.raises(ValueError, match="Session .* not found"):
            await client.resume_session("nonexistent-session-id")

    @pytest.mark.skip(reason="Test needs update for new static session architecture")
    @pytest.mark.asyncio
    async def test_compact_conversation(self, client):
        """Test compacting a conversation."""
        # Create a session
        with patch.object(client._sdk_client, "connect", new_callable=AsyncMock):
            session = await client.create_session(resources=["gmail"])

        # Compact it (implementation would use Claude SDK's compact feature)
        with patch("devassist.ai.claude_client.logger") as mock_logger:
            await client.compact_conversation(session.session_id)
            mock_logger.info.assert_called()

    @pytest.mark.skip(reason="Test needs update for new static session architecture")
    @pytest.mark.asyncio
    async def test_clear_session(self, client):
        """Test clearing a session."""
        # Create a session
        with patch.object(client._sdk_client, "connect", new_callable=AsyncMock):
            session = await client.create_session(resources=["gmail"])

        # Clear it
        await client.clear_session(session.session_id)

        # Verify it's removed
        assert session.session_id not in client._active_sessions

    @pytest.mark.skip(reason="Test needs update for new static session architecture")
    def test_list_sessions(self, client):
        """Test listing all active sessions."""
        # Add some sessions
        session1 = ClaudeSession(
            session_id="session-1",
            created_at=datetime.now(),
            last_used=datetime.now(),
            resources=["gmail"],
            turns=0,
        )
        session2 = ClaudeSession(
            session_id="session-2",
            created_at=datetime.now(),
            last_used=datetime.now(),
            resources=["slack"],
            turns=0,
        )

        client._active_sessions["session-1"] = session1
        client._active_sessions["session-2"] = session2

        sessions = client.list_sessions()
        assert len(sessions) == 2
        assert any(s.session_id == "session-1" for s in sessions)
        assert any(s.session_id == "session-2" for s in sessions)

    @pytest.mark.skip(reason="Test needs update for new static session architecture")
    def test_get_latest_session(self, client):
        """Test getting the most recently used session."""
        from datetime import timedelta

        now = datetime.now()

        session1 = ClaudeSession(
            session_id="session-1",
            created_at=now - timedelta(hours=2),
            last_used=now - timedelta(hours=1),
            resources=["gmail"],
            turns=0,
        )
        session2 = ClaudeSession(
            session_id="session-2",
            created_at=now - timedelta(hours=1),
            last_used=now,  # Most recent
            resources=["slack"],
            turns=0,
        )

        client._active_sessions["session-1"] = session1
        client._active_sessions["session-2"] = session2

        latest = client.get_latest_session()
        assert latest is not None
        assert latest.session_id == "session-2"

    @pytest.mark.skip(reason="Test needs update for new static session architecture")
    def test_get_latest_session_empty(self, client):
        """Test getting latest session when none exist."""
        latest = client.get_latest_session()
        assert latest is None
