"""Context aggregator for DevAssist.

Fetches and combines context from multiple sources.
"""

import asyncio
from typing import Any

from devassist.adapters import get_adapter
from devassist.adapters.errors import AuthenticationError, SourceUnavailableError
from devassist.core.config_manager import ConfigManager
from devassist.models.context import ContextItem, SourceType


class ContextAggregator:
    """Aggregates context items from multiple configured sources."""

    DEFAULT_LIMIT_PER_SOURCE = 50

    def __init__(self, config_manager: ConfigManager | None = None) -> None:
        """Initialize ContextAggregator.

        Args:
            config_manager: Optional config manager. Uses default if not provided.
        """
        self._config_manager = config_manager or ConfigManager()
        self._failed_sources: list[str] = []

    @property
    def failed_sources(self) -> list[str]:
        """Get list of sources that failed during last fetch."""
        return self._failed_sources.copy()

    async def fetch_all(
        self,
        sources: list[SourceType] | None = None,
        limit_per_source: int | None = None,
    ) -> list[ContextItem]:
        """Fetch context items from all configured sources.

        Args:
            sources: Optional list of source types to fetch from.
                    If None, fetches from all configured sources.
            limit_per_source: Maximum items per source.

        Returns:
            Combined list of context items from all sources.
        """
        limit = limit_per_source or self.DEFAULT_LIMIT_PER_SOURCE
        self._failed_sources = []

        adapters = self._get_configured_adapters()
        if not adapters:
            return []

        # Filter by source types if specified
        if sources:
            adapters = [
                (adapter, config)
                for adapter, config in adapters
                if adapter.source_type in sources
            ]

        # Fetch from all sources in parallel
        tasks = [
            self._fetch_from_source(adapter, config, limit)
            for adapter, config in adapters
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results, handling exceptions
        all_items: list[ContextItem] = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                adapter, _ = adapters[idx]
                self._failed_sources.append(adapter.display_name)
            elif isinstance(result, list):
                all_items.extend(result)

        return all_items

    def _get_configured_adapters(self) -> list[tuple[Any, dict[str, Any]]]:
        """Get list of configured adapters with their configs.

        Returns:
            List of (adapter, config) tuples.
        """
        configured_sources = self._config_manager.list_sources()
        adapters = []

        for source_name in configured_sources:
            config = self._config_manager.get_source_config(source_name)
            if not config or not config.get("enabled", True):
                continue

            try:
                adapter = get_adapter(source_name)
                adapters.append((adapter, config))
            except ValueError:
                # Unknown source type, skip
                continue

        return adapters

    async def _fetch_from_source(
        self,
        adapter: Any,
        config: dict[str, Any],
        limit: int,
    ) -> list[ContextItem]:
        """Fetch items from a single source.

        Args:
            adapter: The source adapter.
            config: Source configuration.
            limit: Maximum items to fetch.

        Returns:
            List of context items.

        Raises:
            AuthenticationError: If authentication fails.
            SourceUnavailableError: If source is unavailable.
        """
        try:
            # Authenticate with stored config
            await adapter.authenticate(config)

            # Fetch items
            items = []
            async for item in adapter.fetch_items(limit=limit):
                items.append(item)
                if len(items) >= limit:
                    break

            return items

        except (AuthenticationError, SourceUnavailableError):
            raise
        except Exception as e:
            raise SourceUnavailableError(
                f"Failed to fetch from {adapter.display_name}: {e}",
                source_type=adapter.source_type.value,
            ) from e
