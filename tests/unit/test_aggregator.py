"""Unit tests for ContextAggregator.

TDD: These tests are written FIRST and must FAIL before implementation.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from devassist.core.aggregator import ContextAggregator
from devassist.models.context import ContextItem, SourceType


class TestContextAggregator:
    """Tests for ContextAggregator class."""

    @pytest.mark.asyncio
    async def test_fetch_all_sources_returns_combined_items(self) -> None:
        """Should fetch from all configured sources and combine results."""
        aggregator = ContextAggregator()

        # Mock adapters
        mock_gmail = MagicMock()
        mock_slack = MagicMock()

        gmail_items = [
            ContextItem(
                id="gmail-1",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=datetime.now(),
                title="Email 1",
                relevance_score=0.5,
            )
        ]
        slack_items = [
            ContextItem(
                id="slack-1",
                source_id="slack",
                source_type=SourceType.SLACK,
                timestamp=datetime.now(),
                title="Message 1",
                relevance_score=0.5,
            )
        ]

        async def gmail_fetch(*args, **kwargs):
            for item in gmail_items:
                yield item

        async def slack_fetch(*args, **kwargs):
            for item in slack_items:
                yield item

        mock_gmail.fetch_items = gmail_fetch
        mock_slack.fetch_items = slack_fetch
        mock_gmail.authenticate = AsyncMock(return_value=True)
        mock_slack.authenticate = AsyncMock(return_value=True)

        with patch.object(aggregator, "_get_configured_adapters") as mock_get:
            mock_get.return_value = [
                (mock_gmail, {"enabled": True}),
                (mock_slack, {"enabled": True}),
            ]

            items = await aggregator.fetch_all()

        assert len(items) == 2
        assert any(item.source_type == SourceType.GMAIL for item in items)
        assert any(item.source_type == SourceType.SLACK for item in items)

    @pytest.mark.asyncio
    async def test_fetch_with_source_filter(self) -> None:
        """Should only fetch from specified sources when filtered."""
        aggregator = ContextAggregator()

        mock_gmail = MagicMock()
        gmail_items = [
            ContextItem(
                id="gmail-1",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=datetime.now(),
                title="Email 1",
                relevance_score=0.5,
            )
        ]

        async def gmail_fetch(*args, **kwargs):
            for item in gmail_items:
                yield item

        mock_gmail.fetch_items = gmail_fetch
        mock_gmail.authenticate = AsyncMock(return_value=True)
        mock_gmail.source_type = SourceType.GMAIL

        with patch.object(aggregator, "_get_configured_adapters") as mock_get:
            mock_get.return_value = [(mock_gmail, {"enabled": True})]

            items = await aggregator.fetch_all(sources=[SourceType.GMAIL])

        assert len(items) == 1
        assert items[0].source_type == SourceType.GMAIL

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_source_failure(self) -> None:
        """Should continue fetching from other sources if one fails."""
        aggregator = ContextAggregator()

        mock_gmail = MagicMock()
        mock_slack = MagicMock()

        # Gmail fails
        async def gmail_fetch(*args, **kwargs):
            raise Exception("Gmail unavailable")
            yield  # Make it a generator

        # Slack succeeds
        slack_items = [
            ContextItem(
                id="slack-1",
                source_id="slack",
                source_type=SourceType.SLACK,
                timestamp=datetime.now(),
                title="Message 1",
                relevance_score=0.5,
            )
        ]

        async def slack_fetch(*args, **kwargs):
            for item in slack_items:
                yield item

        mock_gmail.fetch_items = gmail_fetch
        mock_gmail.authenticate = AsyncMock(return_value=True)
        mock_gmail.display_name = "Gmail"

        mock_slack.fetch_items = slack_fetch
        mock_slack.authenticate = AsyncMock(return_value=True)

        with patch.object(aggregator, "_get_configured_adapters") as mock_get:
            mock_get.return_value = [
                (mock_gmail, {"enabled": True}),
                (mock_slack, {"enabled": True}),
            ]

            items = await aggregator.fetch_all()

        # Should still get Slack items despite Gmail failure
        assert len(items) >= 1
        assert any(item.source_type == SourceType.SLACK for item in items)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_sources_configured(self) -> None:
        """Should return empty list when no sources are configured."""
        aggregator = ContextAggregator()

        with patch.object(aggregator, "_get_configured_adapters") as mock_get:
            mock_get.return_value = []

            items = await aggregator.fetch_all()

        assert items == []

    @pytest.mark.asyncio
    async def test_respects_item_limit_per_source(self) -> None:
        """Should respect per-source item limits."""
        aggregator = ContextAggregator()

        mock_gmail = MagicMock()
        gmail_items = [
            ContextItem(
                id=f"gmail-{i}",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=datetime.now(),
                title=f"Email {i}",
                relevance_score=0.5,
            )
            for i in range(20)
        ]

        async def gmail_fetch(limit=50, **kwargs):
            for item in gmail_items[:limit]:
                yield item

        mock_gmail.fetch_items = gmail_fetch
        mock_gmail.authenticate = AsyncMock(return_value=True)

        with patch.object(aggregator, "_get_configured_adapters") as mock_get:
            mock_get.return_value = [(mock_gmail, {"enabled": True})]

            items = await aggregator.fetch_all(limit_per_source=10)

        assert len(items) <= 10
