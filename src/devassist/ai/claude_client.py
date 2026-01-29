"""Claude AI client for DevAssist.

Handles AI operations using Anthropic's Claude API.
Supports both direct Anthropic API and Vertex AI authentication.
"""

import asyncio
import json
import os
from typing import Any

from anthropic import Anthropic, AnthropicVertex

from devassist.ai.base_client import BaseAIClient
from devassist.ai.prompts import NO_ITEMS_SUMMARY, build_summarization_prompt, get_system_prompt
from devassist.models.context import ContextItem


class ClaudeClient(BaseAIClient):
    """Client for Anthropic Claude API interactions.

    Supports two authentication modes:
    1. Direct API: Uses ANTHROPIC_API_KEY
    2. Vertex AI: Uses Google Cloud Application Default Credentials
       when CLAUDE_CODE_USE_VERTEX=1 is set
    """

    DEFAULT_MODEL = "claude-sonnet-4-5@20250929"
    DEFAULT_MAX_TOKENS = 4096
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_MAX_INPUT_TOKENS = 30000  # Conservative limit for context

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        max_retries: int | None = None,
        max_input_tokens: int | None = None,
        project_id: str | None = None,
        region: str | None = None,
    ) -> None:
        """Initialize ClaudeClient.

        Args:
            api_key: Anthropic API key (not required if using Vertex AI).
            model: Model name to use.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature (0.0-1.0).
            max_retries: Maximum retry attempts.
            max_input_tokens: Maximum input tokens for context.
            project_id: GCP project ID for Vertex AI (or use ANTHROPIC_VERTEX_PROJECT_ID env var).
            region: GCP region for Vertex AI (or use CLOUD_ML_REGION env var).

        Raises:
            ValueError: If neither api_key nor Vertex AI configuration is available.
        """
        # Check if using Vertex AI
        self.use_vertex = os.environ.get("CLAUDE_CODE_USE_VERTEX", "").lower() in ("1", "true")

        if self.use_vertex:
            # Vertex AI mode - use GCP credentials
            self.project_id = project_id or os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
            self.region = region or os.environ.get("CLOUD_ML_REGION", "us-east5")

            if not self.project_id:
                raise ValueError(
                    "Vertex AI mode requires project_id or ANTHROPIC_VERTEX_PROJECT_ID env var"
                )
            self.api_key = None
        else:
            # Direct API mode - requires API key
            if not api_key:
                raise ValueError(
                    "api_key is required for ClaudeClient (or set CLAUDE_CODE_USE_VERTEX=1 for Vertex AI)"
                )
            self.api_key = api_key
            self.project_id = None
            self.region = None

        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens if max_tokens is not None else self.DEFAULT_MAX_TOKENS
        self.temperature = (
            temperature if temperature is not None else self.DEFAULT_TEMPERATURE
        )
        self.max_retries = max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES
        self.max_input_tokens = max_input_tokens or self.DEFAULT_MAX_INPUT_TOKENS

        self._client: Anthropic | AnthropicVertex | None = None

    def _get_client(self) -> Anthropic | AnthropicVertex:
        """Get or create the Anthropic client.

        Returns:
            Configured Anthropic or AnthropicVertex client.
        """
        if self._client is None:
            if self.use_vertex:
                self._client = AnthropicVertex(
                    project_id=self.project_id,
                    region=self.region,
                )
            else:
                self._client = Anthropic(api_key=self.api_key)
        return self._client

    async def summarize(self, items: list[ContextItem]) -> str:
        """Generate a summary from context items.

        Args:
            items: List of context items to summarize.

        Returns:
            AI-generated summary string.

        Raises:
            Exception: If summarization fails after retries.
        """
        if not items:
            return NO_ITEMS_SUMMARY

        prompt = self._build_prompt(items)

        # Execute with retry logic
        return await self._execute_with_retry(prompt)

    async def execute_prompt(
        self,
        prompt: str,
        context: dict[str, Any],
        system_prompt: str | None = None,
    ) -> str:
        """Execute a custom prompt with provided context.

        Args:
            prompt: The user's custom prompt/instruction.
            context: Dictionary of context data.
            system_prompt: Optional custom system prompt. If None, uses default.

        Returns:
            AI-generated response string.

        Raises:
            Exception: If execution fails after retries.
        """
        # Build full prompt with context
        context_json = json.dumps(context, indent=2, default=str)
        full_prompt = f"{prompt}\n\nContext:\n{context_json}"

        return await self._execute_with_retry(full_prompt, system_prompt=system_prompt)

    async def test_connection(self) -> bool:
        """Test connection to Claude API.

        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            # Simple test prompt
            await self._execute_with_retry("Respond with 'OK' if you can read this.")
            return True
        except Exception:
            return False

    async def _execute_with_retry(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Execute prompt with retry logic and exponential backoff.

        Args:
            prompt: The prompt to execute.
            system_prompt: Optional custom system prompt. If None, uses default.

        Returns:
            Generated response string.

        Raises:
            Exception: If all retries fail.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                return await self._generate_content(prompt, system_prompt=system_prompt)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    await asyncio.sleep(2**attempt)

        if last_error:
            raise last_error
        raise RuntimeError("Request failed with unknown error")

    async def _generate_content(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate content using Claude API.

        Args:
            prompt: The prompt to send.
            system_prompt: Optional custom system prompt. If None, uses default.

        Returns:
            Generated content string.
        """
        client = self._get_client()
        effective_system_prompt = system_prompt if system_prompt is not None else get_system_prompt()

        # Run in thread pool since Anthropic SDK is sync
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=effective_system_prompt,
                messages=[{"role": "user", "content": prompt}],
            ),
        )

        # Extract text from response
        if response.content and len(response.content) > 0:
            return response.content[0].text
        return ""

    def _build_prompt(self, items: list[ContextItem]) -> str:
        """Build the prompt from context items.

        Args:
            items: Context items to include in prompt.

        Returns:
            Formatted prompt string.
        """
        # Sort by relevance score (highest first)
        sorted_items = sorted(items, key=lambda x: x.relevance_score, reverse=True)

        # Build context text with token budget awareness
        context_parts: list[str] = []
        estimated_tokens = 0

        for item in sorted_items:
            item_text = self._format_item(item)
            # Rough token estimate: ~4 chars per token
            item_tokens = len(item_text) // 4

            if estimated_tokens + item_tokens > self.max_input_tokens:
                break

            context_parts.append(item_text)
            estimated_tokens += item_tokens

        context_text = "\n\n".join(context_parts)
        return build_summarization_prompt(context_text)
