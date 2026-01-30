"""Unit tests for MCP configuration models."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from devassist.models.mcp_config import (
    AIProviderConfig,
    ClaudeConfig,
    MCPConfig,
    MCPServerConfig,
    RunnerConfig,
    VertexConfig,
    expand_env_vars,
)


class TestClaudeConfig:
    """Tests for ClaudeConfig model."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        config = ClaudeConfig()
        assert config.api_key is None
        assert config.model == "claude-sonnet-4-5-20250929"
        assert config.max_tokens == 4096
        assert config.temperature == 0.7

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        config = ClaudeConfig(
            api_key="sk-ant-test123",
            model="claude-opus-4",
            max_tokens=8192,
            temperature=0.5,
        )
        assert config.api_key == "sk-ant-test123"
        assert config.model == "claude-opus-4"
        assert config.max_tokens == 8192
        assert config.temperature == 0.5


class TestVertexConfig:
    """Tests for VertexConfig model."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        config = VertexConfig()
        assert config.api_key is None
        assert config.project_id == ""
        assert config.location == "us-central1"
        assert config.model == "gemini-2.5-flash"

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        config = VertexConfig(
            project_id="my-gcp-project",
            location="us-east1",
            model="gemini-pro",
        )
        assert config.project_id == "my-gcp-project"
        assert config.location == "us-east1"
        assert config.model == "gemini-pro"


class TestAIProviderConfig:
    """Tests for AIProviderConfig model."""

    def test_default_provider_is_claude(self) -> None:
        """Should default to Claude provider."""
        config = AIProviderConfig()
        assert config.provider == "claude"
        assert isinstance(config.claude, ClaudeConfig)
        assert isinstance(config.vertex, VertexConfig)

    def test_can_set_vertex_provider(self) -> None:
        """Should allow setting Vertex AI as provider."""
        config = AIProviderConfig(provider="vertex")
        assert config.provider == "vertex"

    def test_invalid_provider_raises_error(self) -> None:
        """Should raise validation error for invalid provider."""
        with pytest.raises(ValidationError):
            AIProviderConfig(provider="invalid")  # type: ignore


class TestRunnerConfig:
    """Tests for RunnerConfig model."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        config = RunnerConfig()
        assert config.enabled is False
        assert config.interval_minutes == 5
        assert config.prompt == "Review my context and summarize urgent items."
        assert config.last_run is None
        assert config.status == "stopped"
        assert config.last_error is None
        assert config.output_destination == "~/.devassist/runner-output.md"
        assert config.notify_on_completion is False
        assert config.sources == []

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        config = RunnerConfig(
            enabled=True,
            interval_minutes=10,
            prompt="Custom prompt",
            status="running",
            sources=["gmail", "slack"],
        )
        assert config.enabled is True
        assert config.interval_minutes == 10
        assert config.prompt == "Custom prompt"
        assert config.status == "running"
        assert config.sources == ["gmail", "slack"]

    def test_invalid_status_raises_error(self) -> None:
        """Should raise validation error for invalid status."""
        with pytest.raises(ValidationError):
            RunnerConfig(status="invalid")  # type: ignore


class TestMCPServerConfig:
    """Tests for MCPServerConfig model."""

    def test_minimal_config(self) -> None:
        """Should require only command."""
        config = MCPServerConfig(command="devassist")
        assert config.command == "devassist"
        assert config.args == []
        assert config.env == {}

    def test_with_args_and_env(self) -> None:
        """Should accept args and env vars."""
        config = MCPServerConfig(
            command="devassist",
            args=["--config", "/path/to/config"],
            env={"VAR": "value"},
        )
        assert config.command == "devassist"
        assert config.args == ["--config", "/path/to/config"]
        assert config.env == {"VAR": "value"}


class TestMCPConfig:
    """Tests for MCPConfig model."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        config = MCPConfig()
        assert config.version == "1.0"
        assert config.mcp_servers == {}
        assert isinstance(config.ai, AIProviderConfig)
        assert isinstance(config.runner, RunnerConfig)
        assert config.sources == {}

    def test_from_dict(self) -> None:
        """Should construct from dictionary."""
        data = {
            "version": "1.0",
            "mcp_servers": {
                "devassist": {
                    "command": "devassist",
                    "args": ["--config", "config.json"],
                }
            },
            "ai": {
                "provider": "claude",
                "claude": {"api_key": "sk-ant-test"},
            },
            "runner": {
                "enabled": True,
                "interval_minutes": 10,
            },
            "sources": {
                "gmail": {"enabled": True},
            },
        }
        config = MCPConfig(**data)
        assert config.version == "1.0"
        assert "devassist" in config.mcp_servers
        assert config.ai.provider == "claude"
        assert config.ai.claude.api_key == "sk-ant-test"
        assert config.runner.enabled is True
        assert config.runner.interval_minutes == 10
        assert "gmail" in config.sources


class TestEnvVarExpansion:
    """Tests for environment variable expansion."""

    def test_expand_single_var(self) -> None:
        """Should expand single environment variable."""
        os.environ["TEST_VAR"] = "test_value"
        result = expand_env_vars({"key": "${TEST_VAR}"})
        assert result["key"] == "test_value"
        del os.environ["TEST_VAR"]

    def test_expand_multiple_vars(self) -> None:
        """Should expand multiple environment variables."""
        os.environ["VAR1"] = "value1"
        os.environ["VAR2"] = "value2"
        result = expand_env_vars({
            "key1": "${VAR1}",
            "key2": "${VAR2}",
        })
        assert result["key1"] == "value1"
        assert result["key2"] == "value2"
        del os.environ["VAR1"]
        del os.environ["VAR2"]

    def test_expand_nested_dict(self) -> None:
        """Should expand vars in nested dictionaries."""
        os.environ["NESTED_VAR"] = "nested_value"
        result = expand_env_vars({
            "outer": {
                "inner": "${NESTED_VAR}",
            }
        })
        assert result["outer"]["inner"] == "nested_value"
        del os.environ["NESTED_VAR"]

    def test_expand_in_list(self) -> None:
        """Should expand vars in lists."""
        os.environ["LIST_VAR"] = "list_value"
        result = expand_env_vars({"items": ["${LIST_VAR}", "other"]})
        assert result["items"][0] == "list_value"
        assert result["items"][1] == "other"
        del os.environ["LIST_VAR"]

    def test_undefined_var_becomes_empty(self) -> None:
        """Should replace undefined vars with empty string."""
        result = expand_env_vars({"key": "${UNDEFINED_VAR}"})
        assert result["key"] == ""

    def test_partial_expansion(self) -> None:
        """Should handle partial variable references in strings."""
        os.environ["PARTIAL_VAR"] = "test"
        result = expand_env_vars({"key": "prefix_${PARTIAL_VAR}_suffix"})
        assert result["key"] == "prefix_test_suffix"
        del os.environ["PARTIAL_VAR"]

    def test_non_string_values_unchanged(self) -> None:
        """Should not modify non-string values."""
        result = expand_env_vars({
            "int": 42,
            "bool": True,
            "none": None,
        })
        assert result["int"] == 42
        assert result["bool"] is True
        assert result["none"] is None
