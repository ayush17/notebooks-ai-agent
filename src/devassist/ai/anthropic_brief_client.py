"""Morning brief summarization via Anthropic Claude (direct API or Vertex)."""

from __future__ import annotations

import asyncio

from devassist.ai.brief_context import format_brief_user_prompt
from devassist.ai.prompts import NO_ITEMS_SUMMARY, get_system_prompt
from devassist.models.context import ContextItem
from devassist.orchestrator.llm_client import AnthropicLLMClient, Message


class AnthropicBriefClient:
    """Summarize brief context using the same Claude stack as ``devassist ask``."""

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_MAX_INPUT_TOKENS = 30000

    def __init__(
        self,
        max_retries: int | None = None,
        max_input_tokens: int | None = None,
    ) -> None:
        self.max_retries = max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES
        self.max_input_tokens = max_input_tokens or self.DEFAULT_MAX_INPUT_TOKENS
        self._llm = AnthropicLLMClient()

    async def summarize(self, items: list[ContextItem]) -> str:
        if not items:
            return NO_ITEMS_SUMMARY

        user_content = format_brief_user_prompt(items, self.max_input_tokens)
        messages: list[Message] = [
            Message(role="system", content=get_system_prompt()),
            Message(role="user", content=user_content),
        ]

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._llm.chat(messages, tools=None)
                text = (resp.content or "").strip()
                if text:
                    return text
                raise RuntimeError("Empty response from Claude")
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)

        if last_error:
            raise last_error
        raise RuntimeError("Summarization failed with unknown error")
