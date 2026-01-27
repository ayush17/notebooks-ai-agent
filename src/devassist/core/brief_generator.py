"""Brief generator for DevAssist.

Orchestrates aggregation, ranking, and AI summarization to create morning briefs.
"""

from datetime import datetime
from typing import Any

from devassist.ai.vertex_client import VertexAIClient
from devassist.core.aggregator import ContextAggregator
from devassist.core.cache_manager import CacheManager
from devassist.core.config_manager import ConfigManager
from devassist.core.ranker import RelevanceRanker
from devassist.models.brief import Brief, BriefItem, BriefSection
from devassist.models.context import ContextItem, SourceType


class BriefGenerator:
    """Generates Unified Morning Briefs from aggregated context."""

    CACHE_KEY = "brief:latest"

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        aggregator: ContextAggregator | None = None,
        ranker: RelevanceRanker | None = None,
        ai_client: VertexAIClient | None = None,
        cache: CacheManager | None = None,
    ) -> None:
        """Initialize BriefGenerator.

        Args:
            config_manager: Configuration manager.
            aggregator: Context aggregator.
            ranker: Relevance ranker.
            ai_client: AI client for summarization.
            cache: Cache manager.
        """
        self._config_manager = config_manager or ConfigManager()
        self._aggregator = aggregator or ContextAggregator(self._config_manager)
        self._cache = cache or CacheManager()

        # Load preferences for ranker
        config = self._config_manager.load_config()
        priority_keywords = config.preferences.priority_keywords

        self._ranker = ranker or RelevanceRanker(priority_keywords=priority_keywords)

        # Initialize AI client with config
        self._ai_client = ai_client or VertexAIClient(
            project_id=config.ai.project_id,
            location=config.ai.location,
            model=config.ai.model,
            max_retries=config.ai.max_retries,
            timeout_seconds=config.ai.timeout_seconds,
        )

    async def generate(
        self,
        sources: list[SourceType] | None = None,
        refresh: bool = False,
    ) -> Brief:
        """Generate a morning brief.

        Args:
            sources: Optional list of sources to include.
            refresh: If True, bypass cache and fetch fresh data.

        Returns:
            Generated Brief object.
        """
        if refresh:
            self._cache.clear_all()

        # Fetch from all configured sources
        items = await self._aggregator.fetch_all(sources=sources)

        # Rank items by relevance
        ranked_items = self._ranker.rank(items)

        # Group by source
        sections = self._group_by_source(ranked_items)

        # Generate AI summary
        summary = await self._generate_summary(ranked_items)

        # Build the brief
        brief = Brief(
            summary=summary,
            sections=sections,
            generated_at=datetime.now(),
            total_items=len(ranked_items),
            sources_queried=[s for s in SourceType if self._is_source_configured(s)],
            sources_failed=self._aggregator.failed_sources,
        )

        return brief

    def _group_by_source(self, items: list[ContextItem]) -> list[BriefSection]:
        """Group items by source type into sections.

        Args:
            items: Ranked context items.

        Returns:
            List of BriefSections.
        """
        # Group items by source
        grouped: dict[SourceType, list[ContextItem]] = {}
        for item in items:
            if item.source_type not in grouped:
                grouped[item.source_type] = []
            grouped[item.source_type].append(item)

        # Create sections
        sections = []
        for source_type, source_items in grouped.items():
            brief_items = [BriefItem.from_context_item(item) for item in source_items]

            section = BriefSection(
                source_type=source_type,
                display_name=self._get_display_name(source_type),
                items=brief_items,
                item_count=len(brief_items),
            )
            sections.append(section)

        # Sort sections by total relevance
        sections.sort(
            key=lambda s: sum(i.relevance_score for i in s.items),
            reverse=True,
        )

        return sections

    async def _generate_summary(self, items: list[ContextItem]) -> str:
        """Generate AI summary of items.

        Args:
            items: Ranked context items.

        Returns:
            Summary string.
        """
        try:
            return await self._ai_client.summarize(items)
        except Exception as e:
            # Graceful degradation when AI is unavailable
            return self._generate_fallback_summary(items, str(e))

    def _generate_fallback_summary(
        self,
        items: list[ContextItem],
        error_msg: str,
    ) -> str:
        """Generate a fallback summary when AI is unavailable.

        Args:
            items: Context items.
            error_msg: Error message from AI failure.

        Returns:
            Fallback summary string.
        """
        if not items:
            return "No new items to review."

        # Count by source
        source_counts: dict[str, int] = {}
        for item in items:
            name = item.source_type.value.title()
            source_counts[name] = source_counts.get(name, 0) + 1

        counts_str = ", ".join(f"{count} from {name}" for name, count in source_counts.items())

        return (
            f"AI summarization unavailable. Manual review recommended.\n\n"
            f"You have {len(items)} items to review: {counts_str}.\n\n"
            f"(AI error: {error_msg[:100]})"
        )

    def _get_display_name(self, source_type: SourceType) -> str:
        """Get display name for a source type.

        Args:
            source_type: Source type enum.

        Returns:
            Human-readable name.
        """
        display_names = {
            SourceType.GMAIL: "Gmail",
            SourceType.SLACK: "Slack",
            SourceType.JIRA: "JIRA",
            SourceType.GITHUB: "GitHub",
        }
        return display_names.get(source_type, source_type.value.title())

    def _is_source_configured(self, source_type: SourceType) -> bool:
        """Check if a source type is configured.

        Args:
            source_type: Source type to check.

        Returns:
            True if configured.
        """
        return source_type.value in self._config_manager.list_sources()
