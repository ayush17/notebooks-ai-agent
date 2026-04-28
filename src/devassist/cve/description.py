"""Normalize Jira issue fields (including Atlassian Document Format) to plain text."""

from __future__ import annotations

from typing import Any


def adf_to_plain_text(node: Any) -> str:
    """Best-effort extraction of searchable text from ADF ``body`` JSON."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return str(node.get("text", ""))
        parts: list[str] = []
        for child in node.get("content") or []:
            parts.append(adf_to_plain_text(child))
        return "".join(parts)
    if isinstance(node, list):
        return "".join(adf_to_plain_text(x) for x in node)
    return ""


def field_to_plain(value: Any) -> str:
    """Jira ``fields.description`` may be a string (server) or ADF (cloud)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return adf_to_plain_text(value)
    return str(value)
