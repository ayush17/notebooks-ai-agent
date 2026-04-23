"""Vertex AI client for DevAssist.

Handles AI summarization using Google Cloud Vertex AI (Gemini).
"""

import asyncio
from typing import Any

from devassist.ai.brief_context import format_brief_user_prompt
from devassist.ai.prompts import NO_ITEMS_SUMMARY, get_system_prompt
from devassist.models.config import DEFAULT_VERTEX_GEMINI_MODEL, sanitize_gcp_field
from devassist.utils.gcp_env import resolve_gcp_project_id
from devassist.models.context import ContextItem

# Google Cloud AI imports are done lazily to avoid initialization issues
# when using other LLM providers (e.g., Anthropic on Vertex)
_genai_module = None
_types_module = None


def _get_genai():
    """Lazily import google.genai to avoid initialization at module load."""
    global _genai_module
    if _genai_module is None:
        try:
            from google import genai
            _genai_module = genai
        except ImportError:
            _genai_module = False
    return _genai_module if _genai_module else None


def _get_types():
    """Lazily import google.genai.types."""
    global _types_module
    if _types_module is None:
        try:
            from google.genai import types
            _types_module = types
        except ImportError:
            _types_module = False
    return _types_module if _types_module else None


def _is_vertex_available() -> bool:
    """Check if Vertex AI is available."""
    return _get_genai() is not None


class VertexAIClient:
    """Client for Vertex AI Gemini model interactions."""

    DEFAULT_MODEL = DEFAULT_VERTEX_GEMINI_MODEL
    DEFAULT_LOCATION = "us-central1"
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_TIMEOUT = 60
    DEFAULT_MAX_INPUT_TOKENS = 30000  # Conservative limit for context

    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
        model: str | None = None,
        max_retries: int | None = None,
        timeout_seconds: int | None = None,
        max_input_tokens: int | None = None,
    ) -> None:
        """Initialize VertexAIClient.

        Args:
            project_id: GCP project ID.
            location: GCP region.
            model: Model name to use.
            max_retries: Maximum retry attempts.
            timeout_seconds: Request timeout.
            max_input_tokens: Maximum input tokens for context.
        """
        pid = sanitize_gcp_field(project_id or "")
        self.project_id = sanitize_gcp_field(pid or resolve_gcp_project_id())
        self.location = sanitize_gcp_field(location or self.DEFAULT_LOCATION)
        self.model = sanitize_gcp_field(model or self.DEFAULT_MODEL)
        self.max_retries = max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES
        self.timeout_seconds = timeout_seconds or self.DEFAULT_TIMEOUT
        self.max_input_tokens = max_input_tokens or self.DEFAULT_MAX_INPUT_TOKENS

        self._client: Any = None

    def _get_client(self) -> Any:
        """Get or create the Vertex AI client.

        Returns:
            Configured genai client.

        Raises:
            RuntimeError: If Vertex AI is not available.
        """
        genai = _get_genai()
        if not genai:
            raise RuntimeError(
                "Vertex AI libraries not installed. Run: pip install google-cloud-aiplatform"
            )

        if self._client is None:
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

    async def _generate_content(self, prompt: str) -> str:
        """Generate content using the AI model.

        Args:
            prompt: The prompt to send.

        Returns:
            Generated content string.
        """
        if not _is_vertex_available():
            # Fallback for testing without Vertex AI
            return "AI summarization unavailable. Please configure Vertex AI."

        types = _get_types()
        client = self._get_client()

        # Run in thread pool since google-genai may be sync
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=get_system_prompt(),
                    temperature=0.3,  # Lower for more consistent outputs
                    max_output_tokens=1024,
                ),
            ),
        )

        return response.text

    def _build_prompt(self, items: list[ContextItem]) -> str:
        """Build the prompt from context items.

        Args:
            items: Context items to include in prompt.

        Returns:
            Formatted prompt string.
        """
        return format_brief_user_prompt(items, self.max_input_tokens)
