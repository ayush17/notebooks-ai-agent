"""Base adapter class for context sources.

Defines the contract that ALL source adapters must implement.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from devassist.models.context import ContextItem, SourceType


class ContextSourceAdapter(ABC):
    """Abstract base class for all context source adapters.

    Each adapter connects to a specific service (Gmail, Slack, JIRA, GitHub)
    and retrieves context items for the morning brief.
    """

    @property
    @abstractmethod
    def source_type(self) -> SourceType:
        """Get the source type for this adapter.

        Returns:
            SourceType enum value identifying this source.
        """
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Get human-readable name for this source.

        Returns:
            Display name string (e.g., 'Gmail', 'Slack').
        """
        ...

    @abstractmethod
    async def authenticate(self, config: dict[str, Any]) -> bool:
        """Authenticate with the source service.

        Args:
            config: Configuration dict with credentials.

        Returns:
            True if authentication succeeded.

        Raises:
            AuthenticationError: If authentication fails.
        """
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the connection to the source is working.

        Returns:
            True if connection is healthy.

        Raises:
            SourceUnavailableError: If source cannot be reached.
        """
        ...

    @abstractmethod
    def fetch_items(
        self,
        limit: int = 50,
        **kwargs: Any,
    ) -> AsyncIterator[ContextItem]:
        """Fetch context items from the source.

        Args:
            limit: Maximum number of items to fetch.
            **kwargs: Additional source-specific parameters.

        Yields:
            ContextItem instances from the source.

        Raises:
            SourceUnavailableError: If fetch fails.
            AuthenticationError: If not authenticated.
        """
        ...

    @classmethod
    @abstractmethod
    def get_required_config_fields(cls) -> list[str]:
        """Get list of required configuration field names.

        Returns:
            List of required field names for setup.
        """
        ...
