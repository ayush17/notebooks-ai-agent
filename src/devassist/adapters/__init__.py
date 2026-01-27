"""Adapters module for DevAssist.

Contains context source adapters for different services.
"""

from devassist.adapters.base import ContextSourceAdapter
from devassist.adapters.errors import (
    AuthenticationError,
    RateLimitError,
    SourceUnavailableError,
)
from devassist.adapters.github import GitHubAdapter
from devassist.adapters.gmail import GmailAdapter
from devassist.adapters.jira import JiraAdapter
from devassist.adapters.slack import SlackAdapter
from devassist.models.context import SourceType

# Adapter registry for factory lookup
ADAPTER_REGISTRY: dict[SourceType, type[ContextSourceAdapter]] = {
    SourceType.GMAIL: GmailAdapter,
    SourceType.SLACK: SlackAdapter,
    SourceType.JIRA: JiraAdapter,
    SourceType.GITHUB: GitHubAdapter,
}


def get_adapter(source_type: SourceType | str) -> ContextSourceAdapter:
    """Factory function to get adapter instance by source type.

    Args:
        source_type: SourceType enum or string value.

    Returns:
        New adapter instance.

    Raises:
        ValueError: If source type is not supported.
    """
    if isinstance(source_type, str):
        try:
            source_type = SourceType(source_type.lower())
        except ValueError as e:
            raise ValueError(f"Unknown source type: {source_type}") from e

    adapter_class = ADAPTER_REGISTRY.get(source_type)
    if not adapter_class:
        raise ValueError(f"No adapter registered for source type: {source_type}")

    return adapter_class()


def list_available_adapters() -> list[tuple[SourceType, str]]:
    """List all available adapters.

    Returns:
        List of (source_type, display_name) tuples.
    """
    result = []
    for source_type, adapter_class in ADAPTER_REGISTRY.items():
        adapter = adapter_class()
        result.append((source_type, adapter.display_name))
    return result


__all__ = [
    "ContextSourceAdapter",
    "AuthenticationError",
    "RateLimitError",
    "SourceUnavailableError",
    "GmailAdapter",
    "SlackAdapter",
    "JiraAdapter",
    "GitHubAdapter",
    "get_adapter",
    "list_available_adapters",
    "ADAPTER_REGISTRY",
]
