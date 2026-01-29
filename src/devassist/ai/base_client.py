"""Base AI client interface for DevAssist.

Defines the contract that all AI clients (Claude, Vertex, etc.) must implement.
"""

from abc import ABC, abstractmethod
from typing import Any

from devassist.models.context import ContextItem


class BaseAIClient(ABC):
    """Abstract base class for AI client implementations.

    All AI clients must implement:
    - summarize(): Generate brief from context items
    - execute_prompt(): Execute custom prompts with context
    - test_connection(): Verify API connectivity
    """

    @abstractmethod
    async def summarize(self, items: list[ContextItem]) -> str:
        """Generate a summary from context items.

        Args:
            items: List of context items to summarize.

        Returns:
            AI-generated summary string.

        Raises:
            Exception: If summarization fails after retries.
        """
        pass

    @abstractmethod
    async def execute_prompt(
        self,
        prompt: str,
        context: dict[str, Any],
        system_prompt: str | None = None,
    ) -> str:
        """Execute a custom prompt with provided context.

        Used by the background runner to execute user-defined tasks.

        Args:
            prompt: The user's custom prompt/instruction.
            context: Dictionary of context data (e.g., aggregated items).
            system_prompt: Optional custom system prompt. If None, uses default.

        Returns:
            AI-generated response string.

        Raises:
            Exception: If execution fails after retries.
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connection to the AI service.

        Returns:
            True if connection is successful, False otherwise.
        """
        pass

    def _format_item(self, item: ContextItem) -> str:
        """Format a single context item for prompts.

        Common formatting shared across all AI clients.

        Args:
            item: Context item to format.

        Returns:
            Formatted string representation.
        """
        parts = [
            f"[{item.source_type.value.upper()}] {item.title}",
        ]

        if item.author:
            parts.append(f"From: {item.author}")

        parts.append(f"Time: {item.timestamp.strftime('%Y-%m-%d %H:%M')}")

        if item.content:
            # Truncate long content
            content = item.content[:500]
            if len(item.content) > 500:
                content += "..."
            parts.append(f"Content: {content}")

        if item.url:
            parts.append(f"Link: {item.url}")

        return "\n".join(parts)
