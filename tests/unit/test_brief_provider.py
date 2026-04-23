"""Tests for brief summarization provider (Anthropic vs Gemini)."""

from __future__ import annotations

from unittest.mock import MagicMock

from devassist.ai.anthropic_brief_client import AnthropicBriefClient
from devassist.ai.vertex_client import VertexAIClient
from devassist.core.brief_generator import BriefGenerator
from devassist.models.config import AIConfig, AppConfig


def _mock_cm(provider: str) -> MagicMock:
    cm = MagicMock()
    cm.load_config.return_value = AppConfig(ai=AIConfig(provider=provider))
    cm.list_sources.return_value = []
    return cm


def test_brief_defaults_to_anthropic_client() -> None:
    cm = _mock_cm("anthropic")
    gen = BriefGenerator(config_manager=cm, aggregator=MagicMock(), ranker=MagicMock(), cache=MagicMock())
    assert isinstance(gen._ai_client, AnthropicBriefClient)


def test_brief_gemini_provider_uses_vertex_client() -> None:
    cm = _mock_cm("gemini")
    gen = BriefGenerator(config_manager=cm, aggregator=MagicMock(), ranker=MagicMock(), cache=MagicMock())
    assert isinstance(gen._ai_client, VertexAIClient)


def test_brief_cli_override_to_gemini() -> None:
    cm = _mock_cm("anthropic")
    gen = BriefGenerator(
        config_manager=cm,
        aggregator=MagicMock(),
        ranker=MagicMock(),
        ai_provider_override="gemini",
        cache=MagicMock(),
    )
    assert isinstance(gen._ai_client, VertexAIClient)
