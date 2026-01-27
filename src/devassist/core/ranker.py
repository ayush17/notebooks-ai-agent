"""Relevance ranker for DevAssist.

Scores and ranks context items by relevance.
"""

import re
from datetime import datetime, timedelta

from devassist.models.context import ContextItem


class RelevanceRanker:
    """Ranks context items by computed relevance."""

    # Scoring weights
    RECENCY_WEIGHT = 0.4
    KEYWORD_WEIGHT = 0.3
    SENDER_WEIGHT = 0.3

    # Recency decay (items older than this get minimum recency score)
    RECENCY_DECAY_DAYS = 7

    def __init__(
        self,
        priority_keywords: list[str] | None = None,
        priority_senders: list[str] | None = None,
    ) -> None:
        """Initialize RelevanceRanker.

        Args:
            priority_keywords: Keywords that boost relevance.
            priority_senders: Senders/authors that boost relevance.
        """
        self.priority_keywords = [k.lower() for k in (priority_keywords or [])]
        self.priority_senders = [s.lower() for s in (priority_senders or [])]

    def rank(self, items: list[ContextItem]) -> list[ContextItem]:
        """Rank items by computed relevance.

        Args:
            items: Context items to rank.

        Returns:
            Items sorted by relevance (highest first), with updated scores.
        """
        if not items:
            return []

        # Compute scores for each item
        scored_items = []
        for item in items:
            new_score = self._compute_score(item)
            # Create new item with updated score
            updated_item = item.model_copy(update={"relevance_score": new_score})
            scored_items.append(updated_item)

        # Sort by score descending
        scored_items.sort(key=lambda x: x.relevance_score, reverse=True)

        return scored_items

    def _compute_score(self, item: ContextItem) -> float:
        """Compute relevance score for an item.

        Args:
            item: Context item to score.

        Returns:
            Relevance score between 0.0 and 1.0.
        """
        recency_score = self._score_recency(item.timestamp)
        keyword_score = self._score_keywords(item)
        sender_score = self._score_sender(item.author)

        # Weighted combination
        raw_score = (
            self.RECENCY_WEIGHT * recency_score
            + self.KEYWORD_WEIGHT * keyword_score
            + self.SENDER_WEIGHT * sender_score
        )

        # Ensure bounded [0, 1]
        return max(0.0, min(1.0, raw_score))

    def _score_recency(self, timestamp: datetime) -> float:
        """Score based on how recent the item is.

        Args:
            timestamp: Item timestamp.

        Returns:
            Recency score (1.0 for now, decreasing to 0.0 for old items).
        """
        now = datetime.now()
        if timestamp.tzinfo:
            # Handle timezone-aware timestamps
            now = datetime.now(timestamp.tzinfo)

        age = now - timestamp
        max_age = timedelta(days=self.RECENCY_DECAY_DAYS)

        if age <= timedelta(0):
            return 1.0

        if age >= max_age:
            return 0.0

        # Linear decay
        return 1.0 - (age.total_seconds() / max_age.total_seconds())

    def _score_keywords(self, item: ContextItem) -> float:
        """Score based on priority keyword matches.

        Args:
            item: Context item to check.

        Returns:
            Keyword score (0.0 to 1.0).
        """
        if not self.priority_keywords:
            return 0.5  # Neutral score when no keywords configured

        text = f"{item.title} {item.content or ''}".lower()

        matches = sum(1 for keyword in self.priority_keywords if keyword in text)

        if matches == 0:
            return 0.0

        # Diminishing returns for multiple matches
        return min(1.0, matches * 0.5)

    def _score_sender(self, author: str | None) -> float:
        """Score based on sender priority.

        Args:
            author: Sender/author string.

        Returns:
            Sender score (0.0 to 1.0).
        """
        if not self.priority_senders:
            return 0.5  # Neutral score when no senders configured

        if not author:
            return 0.0

        author_lower = author.lower()

        # Check for exact or partial matches
        for sender in self.priority_senders:
            if sender in author_lower:
                return 1.0

        return 0.0
