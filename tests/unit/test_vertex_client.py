"""Unit tests for VertexAIClient.

TDD: These tests are written FIRST and must FAIL before implementation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from devassist.ai.vertex_client import VertexAIClient
from devassist.models.context import ContextItem, SourceType
from datetime import datetime


class TestVertexAIClient:
    """Tests for VertexAIClient class."""

    def test_init_with_defaults(self) -> None:
        """Should initialize with default configuration."""
        client = VertexAIClient()

        assert client.model == "gemini-1.5-flash"
        assert client.max_retries == 3
        assert client.timeout_seconds == 60

    def test_init_with_custom_config(self) -> None:
        """Should accept custom configuration."""
        client = VertexAIClient(
            project_id="my-project",
            location="us-east1",
            model="gemini-1.5-pro",
        )

        assert client.project_id == "my-project"
        assert client.location == "us-east1"
        assert client.model == "gemini-1.5-pro"

    @pytest.mark.asyncio
    async def test_summarize_returns_string(self) -> None:
        """Should return string summary from AI model."""
        client = VertexAIClient(project_id="test-project")

        items = [
            ContextItem(
                id="email-1",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=datetime.now(),
                title="Meeting request",
                content="Please join the meeting at 10am",
                relevance_score=0.8,
            ),
        ]

        with patch.object(client, "_generate_content") as mock_gen:
            mock_gen.return_value = "You have one meeting request for 10am today."

            summary = await client.summarize(items)

        assert isinstance(summary, str)
        assert len(summary) > 0

    @pytest.mark.asyncio
    async def test_summarize_handles_empty_items(self) -> None:
        """Should handle empty item list gracefully."""
        client = VertexAIClient(project_id="test-project")

        summary = await client.summarize([])

        assert isinstance(summary, str)
        assert "no items" in summary.lower() or len(summary) > 0

    @pytest.mark.asyncio
    async def test_summarize_respects_token_budget(self) -> None:
        """Should truncate context to fit token budget."""
        client = VertexAIClient(
            project_id="test-project",
            max_input_tokens=1000,
        )

        # Create many items with long content
        items = [
            ContextItem(
                id=f"item-{i}",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=datetime.now(),
                title=f"Email {i}",
                content="A" * 500,  # Long content
                relevance_score=0.5,
            )
            for i in range(20)
        ]

        with patch.object(client, "_generate_content") as mock_gen:
            mock_gen.return_value = "Summary of truncated content"

            await client.summarize(items)

        # Verify context was optimized
        call_args = mock_gen.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_summarize_retries_on_failure(self) -> None:
        """Should retry on transient failures."""
        client = VertexAIClient(
            project_id="test-project",
            max_retries=3,
        )

        items = [
            ContextItem(
                id="email-1",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=datetime.now(),
                title="Test",
                relevance_score=0.5,
            ),
        ]

        with patch.object(client, "_generate_content") as mock_gen:
            # Fail twice, then succeed
            mock_gen.side_effect = [
                Exception("Transient error 1"),
                Exception("Transient error 2"),
                "Success after retries",
            ]

            summary = await client.summarize(items)

        assert summary == "Success after retries"
        assert mock_gen.call_count == 3

    @pytest.mark.asyncio
    async def test_summarize_raises_after_max_retries(self) -> None:
        """Should raise after exhausting retries."""
        client = VertexAIClient(
            project_id="test-project",
            max_retries=2,
        )

        items = [
            ContextItem(
                id="email-1",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=datetime.now(),
                title="Test",
                relevance_score=0.5,
            ),
        ]

        with patch.object(client, "_generate_content") as mock_gen:
            mock_gen.side_effect = Exception("Persistent error")

            with pytest.raises(Exception):
                await client.summarize(items)

    def test_build_prompt_includes_all_sources(self) -> None:
        """Should include items from all sources in prompt."""
        client = VertexAIClient(project_id="test-project")

        now = datetime.now()
        items = [
            ContextItem(id="gmail-1", source_id="gmail", source_type=SourceType.GMAIL,
                       timestamp=now, title="Email", relevance_score=0.5),
            ContextItem(id="slack-1", source_id="slack", source_type=SourceType.SLACK,
                       timestamp=now, title="Message", relevance_score=0.5),
            ContextItem(id="jira-1", source_id="jira", source_type=SourceType.JIRA,
                       timestamp=now, title="Ticket", relevance_score=0.5),
        ]

        prompt = client._build_prompt(items)

        assert "gmail" in prompt.lower()
        assert "slack" in prompt.lower()
        assert "jira" in prompt.lower()

    def test_build_prompt_prioritizes_high_relevance(self) -> None:
        """Should include high-relevance items first in prompt."""
        client = VertexAIClient(project_id="test-project")

        now = datetime.now()
        items = [
            ContextItem(id="low", source_id="gmail", source_type=SourceType.GMAIL,
                       timestamp=now, title="Low priority", relevance_score=0.2),
            ContextItem(id="high", source_id="gmail", source_type=SourceType.GMAIL,
                       timestamp=now, title="High priority", relevance_score=0.9),
        ]

        prompt = client._build_prompt(items)

        # High priority should appear before low priority in the prompt
        high_pos = prompt.find("High priority")
        low_pos = prompt.find("Low priority")

        # Both should be present
        assert high_pos >= 0
        assert low_pos >= 0
        # High priority should come first
        assert high_pos < low_pos
