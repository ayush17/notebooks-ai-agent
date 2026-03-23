"""Unit tests for ClaudeClient static session store.

Tests that sessions persist across multiple ClaudeClient instances.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from devassist.ai.claude_client import ClaudeClient, ClaudeSession
from devassist.models.config import ClientConfig


class TestClaudeClientStaticSessions:
    """Tests for static session store behavior."""

    def setup_method(self):
        """Clear session store before each test."""
        ClaudeClient.clear_all_sessions()

    @pytest.fixture
    def mock_claude_sdk(self):
        """Mock Claude SDK initialization to prevent actual SDK calls."""
        with patch('claude_agent_sdk.ClaudeSDKClient') as mock_sdk_class:
            mock_sdk_instance = MagicMock()
            mock_sdk_class.return_value = mock_sdk_instance
            yield mock_sdk_instance

    def test_session_store_shared_across_instances(self, mock_claude_sdk):
        """Sessions should be shared across different ClaudeClient instances."""
        # Create first client and add a session
        config1 = ClientConfig()
        client1 = ClaudeClient(config1)

        # Manually add a session to the store
        session1 = ClaudeSession(
            session_id="test-session-1",
            created_at=datetime.now(),
            last_used=datetime.now(),
            resources=["gmail", "jira"],
        )
        ClaudeClient._session_store["test-session-1"] = session1

        # Create second client - should see the same session
        config2 = ClientConfig()
        client2 = ClaudeClient(config2)

        # Both clients should see all sessions (including auto-created ones and manual one)
        assert client1.list_sessions() == client2.list_sessions()
        assert len(client1.list_sessions()) == 3  # 2 auto-created + 1 manual
        assert len(client2.list_sessions()) == 3

        # Both clients should be able to access the manually added session
        retrieved_session1 = ClaudeClient.get_session_by_id("test-session-1")
        assert retrieved_session1 is not None
        assert retrieved_session1.session_id == "test-session-1"

    def test_sessions_persist_when_creating_new_instances(self, mock_claude_sdk):
        """Creating new ClaudeClient instances should not clear existing sessions."""
        # Add a session via first instance
        client1 = ClaudeClient()
        session = ClaudeSession(
            session_id="persistent-session",
            created_at=datetime.now(),
            last_used=datetime.now(),
            resources=["slack"],
        )
        ClaudeClient._session_store["persistent-session"] = session

        # Verify session exists (1 auto-created + 1 manual)
        assert ClaudeClient.get_session_count() == 2

        # Create multiple new instances (each adds 1 auto-created session)
        client2 = ClaudeClient()
        client3 = ClaudeClient()
        client4 = ClaudeClient()

        # All sessions should persist (1 original auto + 1 manual + 3 new auto = 5)
        assert ClaudeClient.get_session_count() == 5
        assert all(
            len(client.list_sessions()) == 5
            for client in [client1, client2, client3, client4]
        )

    def test_sessions_accumulate_across_instances(self, mock_claude_sdk):
        """New sessions should be added to existing ones, not replace them."""
        # First client adds a session (auto-creates 1)
        client1 = ClaudeClient()
        session1 = ClaudeSession(
            session_id="session-1",
            created_at=datetime.now(),
            last_used=datetime.now(),
            resources=["gmail"],
        )
        ClaudeClient._session_store["session-1"] = session1

        # Second client adds another session (auto-creates 1 more)
        client2 = ClaudeClient()
        session2 = ClaudeSession(
            session_id="session-2",
            created_at=datetime.now(),
            last_used=datetime.now(),
            resources=["jira"],
        )
        ClaudeClient._session_store["session-2"] = session2

        # All sessions should exist (2 auto + 2 manual = 4)
        assert ClaudeClient.get_session_count() == 4
        assert len(client1.list_sessions()) == 4
        assert len(client2.list_sessions()) == 4

        # Both clients should see both manual sessions
        session_ids = ClaudeClient.get_session_ids()
        assert "session-1" in session_ids
        assert "session-2" in session_ids

    def test_class_methods_work_correctly(self):
        """Class methods should operate on the static store correctly."""
        # Add some test sessions
        for i in range(3):
            session = ClaudeSession(
                session_id=f"session-{i}",
                created_at=datetime.now(),
                last_used=datetime.now(),
                resources=["gmail"],
            )
            ClaudeClient._session_store[f"session-{i}"] = session

        # Test class methods
        assert ClaudeClient.get_session_count() == 3
        assert len(ClaudeClient.get_session_ids()) == 3

        # Test get_session_by_id
        session = ClaudeClient.get_session_by_id("session-1")
        assert session is not None
        assert session.session_id == "session-1"

        # Test nonexistent session
        assert ClaudeClient.get_session_by_id("nonexistent") is None

    def test_clear_all_sessions_affects_all_instances(self, mock_claude_sdk):
        """Clearing all sessions should affect all ClaudeClient instances."""
        # Create multiple clients and add sessions (auto-creates 2 sessions)
        client1 = ClaudeClient()
        client2 = ClaudeClient()

        for i in range(3):
            session = ClaudeSession(
                session_id=f"session-{i}",
                created_at=datetime.now(),
                last_used=datetime.now(),
                resources=["gmail"],
            )
            ClaudeClient._session_store[f"session-{i}"] = session

        # Verify sessions exist for both clients (2 auto + 3 manual = 5)
        assert len(client1.list_sessions()) == 5
        assert len(client2.list_sessions()) == 5

        # Clear all sessions
        ClaudeClient.clear_all_sessions()

        # Both clients should see no sessions
        assert len(client1.list_sessions()) == 0
        assert len(client2.list_sessions()) == 0
        assert ClaudeClient.get_session_count() == 0

    def test_individual_session_clearing_affects_all_instances(self, mock_claude_sdk):
        """Clearing individual sessions should affect all instances."""
        client1 = ClaudeClient()
        client2 = ClaudeClient()

        # Add sessions (2 auto + 3 manual = 5 total)
        for i in range(3):
            session = ClaudeSession(
                session_id=f"session-{i}",
                created_at=datetime.now(),
                last_used=datetime.now(),
                resources=["gmail"],
            )
            ClaudeClient._session_store[f"session-{i}"] = session

        # Clear one session via client1
        client1.clear_session("session-1")

        # Both clients should see the change (5 - 1 = 4)
        assert ClaudeClient.get_session_count() == 4
        assert len(client1.list_sessions()) == 4
        assert len(client2.list_sessions()) == 4

        # Specific session should be gone for both
        assert ClaudeClient.get_session_by_id("session-1") is None

    def test_latest_session_works_across_instances(self, mock_claude_sdk):
        """Getting latest session should work consistently across instances."""
        client1 = ClaudeClient()
        client2 = ClaudeClient()

        # Add sessions with different last_used times
        base_time = datetime.now()

        session1 = ClaudeSession(
            session_id="session-old",
            created_at=base_time,
            last_used=base_time,
            resources=["gmail"],
        )

        session2 = ClaudeSession(
            session_id="session-new",
            created_at=base_time,
            last_used=datetime.fromtimestamp(base_time.timestamp() + 60),  # 1 minute later
            resources=["jira"],
        )

        ClaudeClient._session_store["session-old"] = session1
        ClaudeClient._session_store["session-new"] = session2

        # Both clients should get the same latest session
        latest1 = client1.get_latest_session()
        latest2 = client2.get_latest_session()

        assert latest1 is not None
        assert latest2 is not None
        assert latest1.session_id == latest2.session_id == "session-new"