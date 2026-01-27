"""Unit tests for RelevanceRanker.

TDD: These tests are written FIRST and must FAIL before implementation.
"""

import pytest
from datetime import datetime, timedelta

from devassist.core.ranker import RelevanceRanker
from devassist.models.context import ContextItem, SourceType


class TestRelevanceRanker:
    """Tests for RelevanceRanker class."""

    def test_rank_by_recency(self) -> None:
        """More recent items should have higher relevance scores."""
        ranker = RelevanceRanker()

        now = datetime.now()
        old_item = ContextItem(
            id="old",
            source_id="gmail",
            source_type=SourceType.GMAIL,
            timestamp=now - timedelta(days=7),
            title="Old email",
            relevance_score=0.5,
        )
        new_item = ContextItem(
            id="new",
            source_id="gmail",
            source_type=SourceType.GMAIL,
            timestamp=now - timedelta(hours=1),
            title="New email",
            relevance_score=0.5,
        )

        ranked = ranker.rank([old_item, new_item])

        # New item should be ranked first
        assert ranked[0].id == "new"
        assert ranked[0].relevance_score > ranked[1].relevance_score

    def test_rank_by_keywords(self) -> None:
        """Items matching priority keywords should rank higher."""
        ranker = RelevanceRanker(priority_keywords=["urgent", "critical"])

        now = datetime.now()
        normal_item = ContextItem(
            id="normal",
            source_id="gmail",
            source_type=SourceType.GMAIL,
            timestamp=now,
            title="Regular update",
            relevance_score=0.5,
        )
        urgent_item = ContextItem(
            id="urgent",
            source_id="gmail",
            source_type=SourceType.GMAIL,
            timestamp=now,
            title="URGENT: Action required",
            relevance_score=0.5,
        )

        ranked = ranker.rank([normal_item, urgent_item])

        # Urgent item should be ranked first
        assert ranked[0].id == "urgent"
        assert ranked[0].relevance_score > ranked[1].relevance_score

    def test_rank_by_sender_importance(self) -> None:
        """Items from priority senders should rank higher."""
        ranker = RelevanceRanker(priority_senders=["boss@company.com", "ceo@company.com"])

        now = datetime.now()
        normal_item = ContextItem(
            id="normal",
            source_id="gmail",
            source_type=SourceType.GMAIL,
            timestamp=now,
            title="FYI",
            author="colleague@company.com",
            relevance_score=0.5,
        )
        vip_item = ContextItem(
            id="vip",
            source_id="gmail",
            source_type=SourceType.GMAIL,
            timestamp=now,
            title="Meeting request",
            author="boss@company.com",
            relevance_score=0.5,
        )

        ranked = ranker.rank([normal_item, vip_item])

        # VIP item should be ranked first
        assert ranked[0].id == "vip"
        assert ranked[0].relevance_score > ranked[1].relevance_score

    def test_combined_ranking_factors(self) -> None:
        """Multiple ranking factors should combine appropriately."""
        ranker = RelevanceRanker(
            priority_keywords=["urgent"],
            priority_senders=["boss@company.com"],
        )

        now = datetime.now()
        items = [
            ContextItem(
                id="old-normal",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=now - timedelta(days=3),
                title="Old update",
                author="random@company.com",
                relevance_score=0.5,
            ),
            ContextItem(
                id="new-normal",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=now - timedelta(hours=1),
                title="Recent update",
                author="random@company.com",
                relevance_score=0.5,
            ),
            ContextItem(
                id="vip-urgent",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=now - timedelta(hours=2),
                title="URGENT from boss",
                author="boss@company.com",
                relevance_score=0.5,
            ),
        ]

        ranked = ranker.rank(items)

        # VIP urgent should be first (keyword + sender bonus)
        assert ranked[0].id == "vip-urgent"

    def test_empty_list_returns_empty(self) -> None:
        """Should handle empty input gracefully."""
        ranker = RelevanceRanker()

        ranked = ranker.rank([])

        assert ranked == []

    def test_preserves_all_items(self) -> None:
        """Ranking should not lose any items."""
        ranker = RelevanceRanker()

        now = datetime.now()
        items = [
            ContextItem(
                id=f"item-{i}",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=now - timedelta(hours=i),
                title=f"Item {i}",
                relevance_score=0.5,
            )
            for i in range(10)
        ]

        ranked = ranker.rank(items)

        assert len(ranked) == 10
        assert set(item.id for item in ranked) == set(item.id for item in items)

    def test_relevance_scores_bounded(self) -> None:
        """All relevance scores should be between 0.0 and 1.0."""
        ranker = RelevanceRanker(
            priority_keywords=["urgent", "critical"],
            priority_senders=["vip@company.com"],
        )

        now = datetime.now()
        items = [
            ContextItem(
                id="super-important",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=now,
                title="URGENT CRITICAL action needed",
                author="vip@company.com",
                relevance_score=0.5,
            ),
            ContextItem(
                id="normal",
                source_id="gmail",
                source_type=SourceType.GMAIL,
                timestamp=now - timedelta(days=30),
                title="Old newsletter",
                author="newsletter@random.com",
                relevance_score=0.5,
            ),
        ]

        ranked = ranker.rank(items)

        for item in ranked:
            assert 0.0 <= item.relevance_score <= 1.0
