"""Vertex AI client for DevAssist.

Handles AI summarization using Google Cloud Vertex AI (Gemini).
"""

import asyncio
import json
from typing import Any

from devassist.ai.base_client import BaseAIClient
from devassist.ai.prompts import NO_ITEMS_SUMMARY, build_summarization_prompt, get_system_prompt
from devassist.models.context import ContextItem

# Google Cloud AI imports - optional, checked at runtime
try:
    from google import genai
    from google.genai import types

    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    genai = None  # type: ignore
    types = None  # type: ignore


class VertexAIClient(BaseAIClient):
    """Client for Vertex AI Gemini model interactions."""

    DEFAULT_MODEL = "gemini-1.5-flash"
    DEFAULT_LOCATION = "us-central1"
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_TIMEOUT = 60
    DEFAULT_MAX_INPUT_TOKENS = 30000  # Conservative limit for context

    def __init__(
        self,
        api_key: str | None = None,
        project_id: str | None = None,
        location: str | None = None,
        model: str | None = None,
        max_retries: int | None = None,
        timeout_seconds: int | None = None,
        max_input_tokens: int | None = None,
    ) -> None:
        """Initialize VertexAIClient.

        Args:
            api_key: Google AI API key (alternative to Vertex AI).
            project_id: GCP project ID (for Vertex AI).
            location: GCP region (for Vertex AI).
            model: Model name to use.
            max_retries: Maximum retry attempts.
            timeout_seconds: Request timeout.
            max_input_tokens: Maximum input tokens for context.
        """
        self.api_key = api_key
        self.project_id = project_id or ""
        self.location = location or self.DEFAULT_LOCATION
        self.model = model or self.DEFAULT_MODEL
        self.max_retries = max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES
        self.timeout_seconds = timeout_seconds or self.DEFAULT_TIMEOUT
        self.max_input_tokens = max_input_tokens or self.DEFAULT_MAX_INPUT_TOKENS

        self._client: Any = None

    def _get_client(self) -> Any:
        """Get or create the AI client.

        Uses Google AI API key if provided, otherwise falls back to Vertex AI.

        Returns:
            Configured genai client.

        Raises:
            RuntimeError: If AI libraries are not available.
        """
        if not VERTEX_AI_AVAILABLE:
            raise RuntimeError(
                "Google AI libraries not installed. Run: pip install google-genai"
            )

        if self._client is None:
            if self.api_key:
                # Use Google AI Studio with API key
                self._client = genai.Client(api_key=self.api_key)
            else:
                # Use Vertex AI with ADC
                self._client = genai.Client(
                    vertexai=True,
                    project=self.project_id,
                    location=self.location,
                )

        return self._client

    async def summarize(self, items: list[ContextItem]) -> str:
        """Generate a summary of context items.

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

        # Retry loop
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return await self._generate_content(prompt)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    await asyncio.sleep(2**attempt)

        if last_error:
            raise last_error
        raise RuntimeError("Summarization failed with unknown error")

    async def _generate_content(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate content using the AI model.

        Args:
            prompt: The prompt to send.
            system_prompt: Optional custom system prompt. If None, uses default.

        Returns:
            Generated content string.
        """
        if not VERTEX_AI_AVAILABLE:
            # Fallback for testing without Vertex AI
            return "AI summarization unavailable. Please configure Vertex AI."

        client = self._get_client()
        effective_system_prompt = system_prompt if system_prompt is not None else get_system_prompt()

        # Run in thread pool since google-genai may be sync
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=effective_system_prompt,
                    temperature=0.3,  # Lower for more consistent outputs
                    max_output_tokens=1024,
                ),
            ),
        )

        return response.text

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

        # Retry loop
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return await self._generate_content(full_prompt, system_prompt=system_prompt)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)

        if last_error:
            raise last_error
        raise RuntimeError("Execution failed with unknown error")

    async def test_connection(self) -> bool:
        """Test connection to Vertex AI.

        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            # Simple test prompt
            await self._generate_content("Respond with 'OK' if you can read this.")
            return True
        except Exception:
            return False

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
