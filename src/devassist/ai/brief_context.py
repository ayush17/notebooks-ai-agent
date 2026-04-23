"""Format context items into the morning-brief user prompt (shared by Gemini + Anthropic)."""

from __future__ import annotations

from devassist.ai.prompts import build_summarization_prompt
from devassist.models.context import ContextItem


def format_brief_user_prompt(items: list[ContextItem], max_input_tokens: int = 30000) -> str:
    """Build the main user message text for summarization from ranked context items."""
    sorted_items = sorted(items, key=lambda x: x.relevance_score, reverse=True)
    context_parts: list[str] = []
    estimated_tokens = 0

    for item in sorted_items:
        item_text = format_brief_item(item)
        item_tokens = len(item_text) // 4
        if estimated_tokens + item_tokens > max_input_tokens:
            break
        context_parts.append(item_text)
        estimated_tokens += item_tokens

    context_text = "\n\n".join(context_parts)
    return build_summarization_prompt(context_text)


def format_brief_item(item: ContextItem) -> str:
    """Format a single context item for the brief prompt."""
    parts = [
        f"[{item.source_type.value.upper()}] {item.title}",
    ]
    if item.author:
        parts.append(f"From: {item.author}")
    parts.append(f"Time: {item.timestamp.strftime('%Y-%m-%d %H:%M')}")
    if item.content:
        content = item.content[:500]
        if len(item.content) > 500:
            content += "..."
        parts.append(f"Content: {content}")
    if item.url:
        parts.append(f"Link: {item.url}")
    return "\n".join(parts)
