"""Unit tests for BriefGenerator.

TDD: These tests are written FIRST and must FAIL before implementation.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from devassist.core.brief_generator import BriefGenerator
from devassist.models.brief import Brief, BriefSection
from devassist.models.context import ContextItem, SourceType


class TestBriefGenerator:
    """Tests for BriefGenerator class."""

    @pytest.mark.asyncio
    async def test_generate_returns_brief(self) -> None:
        """Should generate a Brief with sections from aggregated context."""
        generator = BriefGenerator()

        items = [
            ContextItem(
                id="email-1",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=datetime.now(),
                title="Important email",
                content="Meeting at 10am",
                relevance_score=0.8,
            ),
            ContextItem(
                id="jira-1",
                source_id="jira",
                source_type=SourceType.JIRA,
                timestamp=datetime.now(),
                title="[PROJ-123] Fix bug",
                content="Bug description",
                relevance_score=0.7,
            ),
        ]

        with patch.object(generator, "_aggregator") as mock_agg, \
             patch.object(generator, "_ranker") as mock_ranker, \
             patch.object(generator, "_ai_client") as mock_ai:
            mock_agg.fetch_all = AsyncMock(return_value=items)
            mock_ranker.rank.return_value = items
            mock_ai.summarize = AsyncMock(return_value="Today's summary: You have an important email and a bug to fix.")

            brief = await generator.generate()

        assert isinstance(brief, Brief)
        assert brief.summary is not None
        assert len(brief.sections) > 0

    @pytest.mark.asyncio
    async def test_generate_groups_by_source(self) -> None:
        """Should group items by source type in sections."""
        generator = BriefGenerator()

        now = datetime.now()
        items = [
            ContextItem(id="email-1", source_id="gmail", source_type=SourceType.GMAIL,
                       timestamp=now, title="Email 1", relevance_score=0.5),
            ContextItem(id="email-2", source_id="gmail", source_type=SourceType.GMAIL,
                       timestamp=now, title="Email 2", relevance_score=0.5),
            ContextItem(id="slack-1", source_id="slack", source_type=SourceType.SLACK,
                       timestamp=now, title="Message 1", relevance_score=0.5),
        ]

        with patch.object(generator, "_aggregator") as mock_agg, \
             patch.object(generator, "_ranker") as mock_ranker, \
             patch.object(generator, "_ai_client") as mock_ai:
            mock_agg.fetch_all = AsyncMock(return_value=items)
            mock_ranker.rank.return_value = items
            mock_ai.summarize = AsyncMock(return_value="Summary")

            brief = await generator.generate()

        # Should have sections for Gmail and Slack
        source_types = [s.source_type for s in brief.sections]
        assert SourceType.GMAIL in source_types
        assert SourceType.SLACK in source_types

    @pytest.mark.asyncio
    async def test_generate_respects_source_filter(self) -> None:
        """Should only include specified sources when filtered."""
        generator = BriefGenerator()

        now = datetime.now()
        gmail_items = [
            ContextItem(id="email-1", source_id="gmail", source_type=SourceType.GMAIL,
                       timestamp=now, title="Email 1", relevance_score=0.5),
        ]

        with patch.object(generator, "_aggregator") as mock_agg, \
             patch.object(generator, "_ranker") as mock_ranker, \
             patch.object(generator, "_ai_client") as mock_ai:
            mock_agg.fetch_all = AsyncMock(return_value=gmail_items)
            mock_ranker.rank.return_value = gmail_items
            mock_ai.summarize = AsyncMock(return_value="Gmail summary")

            brief = await generator.generate(sources=[SourceType.GMAIL])

        assert all(s.source_type == SourceType.GMAIL for s in brief.sections)

    @pytest.mark.asyncio
    async def test_generate_with_refresh_bypasses_cache(self) -> None:
        """Should bypass cache when refresh=True."""
        generator = BriefGenerator()

        now = datetime.now()
        items = [
            ContextItem(id="email-1", source_id="gmail", source_type=SourceType.GMAIL,
                       timestamp=now, title="Email 1", relevance_score=0.5),
        ]

        with patch.object(generator, "_aggregator") as mock_agg, \
             patch.object(generator, "_ranker") as mock_ranker, \
             patch.object(generator, "_ai_client") as mock_ai, \
             patch.object(generator, "_cache") as mock_cache:
            mock_agg.fetch_all = AsyncMock(return_value=items)
            mock_ranker.rank.return_value = items
            mock_ai.summarize = AsyncMock(return_value="Summary")
            mock_cache.get.return_value = None

            brief = await generator.generate(refresh=True)

        # Cache should be cleared for refresh
        mock_cache.clear_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_without_ai_returns_structured_brief(self) -> None:
        """Should return structured brief even when AI is unavailable."""
        generator = BriefGenerator()

        now = datetime.now()
        items = [
            ContextItem(id="email-1", source_id="gmail", source_type=SourceType.GMAIL,
                       timestamp=now, title="Email 1", relevance_score=0.5),
        ]

        with patch.object(generator, "_aggregator") as mock_agg, \
             patch.object(generator, "_ranker") as mock_ranker, \
             patch.object(generator, "_ai_client") as mock_ai:
            mock_agg.fetch_all = AsyncMock(return_value=items)
            mock_ranker.rank.return_value = items
            mock_ai.summarize = AsyncMock(side_effect=Exception("AI unavailable"))

            brief = await generator.generate()

        # Should still have sections even without AI summary
        assert len(brief.sections) > 0
        # Summary should indicate AI was unavailable
        assert brief.summary is not None

    @pytest.mark.asyncio
    async def test_brief_includes_generation_timestamp(self) -> None:
        """Brief should include when it was generated."""
        generator = BriefGenerator()

        now = datetime.now()
        items = [
            ContextItem(id="email-1", source_id="gmail", source_type=SourceType.GMAIL,
                       timestamp=now, title="Email 1", relevance_score=0.5),
        ]

        with patch.object(generator, "_aggregator") as mock_agg, \
             patch.object(generator, "_ranker") as mock_ranker, \
             patch.object(generator, "_ai_client") as mock_ai:
            mock_agg.fetch_all = AsyncMock(return_value=items)
            mock_ranker.rank.return_value = items
            mock_ai.summarize = AsyncMock(return_value="Summary")

            brief = await generator.generate()

        assert brief.generated_at is not None
        assert isinstance(brief.generated_at, datetime)

    @pytest.mark.asyncio
    async def test_brief_includes_item_count(self) -> None:
        """Brief should track total items processed."""
        generator = BriefGenerator()

        now = datetime.now()
        items = [
            ContextItem(id=f"item-{i}", source_id="gmail", source_type=SourceType.GMAIL,
                       timestamp=now, title=f"Item {i}", relevance_score=0.5)
            for i in range(5)
        ]

        with patch.object(generator, "_aggregator") as mock_agg, \
             patch.object(generator, "_ranker") as mock_ranker, \
             patch.object(generator, "_ai_client") as mock_ai:
            mock_agg.fetch_all = AsyncMock(return_value=items)
            mock_ranker.rank.return_value = items
            mock_ai.summarize = AsyncMock(return_value="Summary")

            brief = await generator.generate()

        assert brief.total_items == 5
