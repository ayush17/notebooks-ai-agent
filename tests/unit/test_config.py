"""Unit tests for ClientConfig.

Tests smart deserialization, validation, and computed fields.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from devassist.models.config import ClientConfig
from devassist.models.context import SourceType


class TestClientConfigValidation:
    """Tests for ClientConfig validation and smart deserialization."""

    def test_default_initialization(self):
        """Should initialize with sensible defaults."""
        config = ClientConfig()

        assert config.workspace_dir == Path.home() / ".devassist"
        assert config.ai_model == "Sonnet 4"
        assert config.ai_timeout_seconds == 60
        assert config.output_format == "markdown"
        assert config.permission_mode == "bypassPermissions"
        assert config.session_id is None
        assert config.session_auto_resume is False
        assert config.priority_keywords == []

    def test_workspace_dir_expansion(self):
        """Should expand workspace directory paths."""
        config = ClientConfig(workspace_dir="~/test-workspace")
        assert config.workspace_dir == Path.home() / "test-workspace"

        config = ClientConfig(workspace_dir="/tmp/test-workspace")
        assert config.workspace_dir == Path("/tmp/test-workspace")

    def test_sources_parsing_from_string(self):
        """Should parse sources from comma-separated string."""
        config = ClientConfig(sources="gmail,jira")
        assert SourceType.GMAIL in config.resolved_sources
        assert SourceType.JIRA in config.resolved_sources
        assert len(config.resolved_sources) == 2

    def test_sources_parsing_invalid_sources(self):
        """Should skip invalid sources with warning."""
        with patch('devassist.models.config.logger') as mock_logger:
            config = ClientConfig(sources="gmail,invalid_source,jira")
            assert SourceType.GMAIL in config.resolved_sources
            assert SourceType.JIRA in config.resolved_sources
            assert len(config.resolved_sources) == 2
            mock_logger.warning.assert_called_once_with("Unknown source type: invalid_source")

    def test_sources_empty_defaults_to_all_available(self):
        """Should default to all available sources when empty."""
        with patch.object(ClientConfig, 'get_available_sources', return_value=[SourceType.GMAIL, SourceType.SLACK]):
            config = ClientConfig(sources="")
            assert config.resolved_sources == [SourceType.GMAIL, SourceType.SLACK]

            config = ClientConfig(sources=[])
            assert config.resolved_sources == [SourceType.GMAIL, SourceType.SLACK]

            config = ClientConfig()  # None sources
            assert config.resolved_sources == [SourceType.GMAIL, SourceType.SLACK]

    def test_ai_model_user_friendly_mapping(self):
        """Should resolve user-friendly AI model names."""
        test_cases = [
            ("Opus 4", "claude-opus-4-1@20250805"),
            ("opus 4.5", "claude-opus-4-5@20251101"),
            ("Sonnet", "claude-sonnet-4-5@20250929"),
            ("fast", "claude-sonnet-4-5@20250929"),
            ("best", "claude-opus-4-5@20251101"),
            ("claude-sonnet-4@20250514", "claude-sonnet-4@20250514"),  # Already technical
        ]

        for user_input, expected in test_cases:
            config = ClientConfig(ai_model=user_input)
            assert config.ai_model == expected

    def test_ai_model_unknown_defaults_to_default(self):
        """Should default to fallback model for unknown names."""
        with patch('devassist.models.config.logger') as mock_logger:
            config = ClientConfig(ai_model="unknown_model")
            assert config.ai_model == "claude-sonnet-4@20250514"  # Default
            mock_logger.warning.assert_called_once()

    def test_ai_timeout_validation(self):
        """Should validate and clamp timeout values."""
        # Too low - should clamp to 10
        config = ClientConfig(ai_timeout_seconds=5)
        assert config.ai_timeout_seconds == 10

        # Too high - should clamp to 600
        config = ClientConfig(ai_timeout_seconds=1000)
        assert config.ai_timeout_seconds == 600

        # Valid range
        config = ClientConfig(ai_timeout_seconds=120)
        assert config.ai_timeout_seconds == 120

    def test_output_format_validation(self):
        """Should validate output format."""
        config = ClientConfig(output_format="json")
        assert config.output_format == "json"

        config = ClientConfig(output_format="markdown")
        assert config.output_format == "markdown"

        with patch('devassist.models.config.logger') as mock_logger:
            config = ClientConfig(output_format="invalid")
            assert config.output_format == "markdown"
            mock_logger.warning.assert_called_once()

    def test_permission_mode_validation(self):
        """Should validate permission mode."""
        config = ClientConfig(permission_mode="plan")
        assert config.permission_mode == "plan"

        with patch('devassist.models.config.logger') as mock_logger:
            config = ClientConfig(permission_mode="invalid")
            assert config.permission_mode == "bypassPermissions"
            mock_logger.warning.assert_called_once()

    def test_session_options_mutual_exclusion(self):
        """Should reject conflicting session options."""
        # Valid individual options
        ClientConfig(session_id="test-123")
        ClientConfig(session_auto_resume=True)
        ClientConfig()  # Neither

        # Invalid combination
        with pytest.raises(ValueError, match="Cannot specify both session_id and session_auto_resume"):
            ClientConfig(session_id="test-123", session_auto_resume=True)


class TestClientConfigComputedFields:
    """Tests for computed properties."""

    def test_resolved_ai_model(self):
        """Should return the resolved technical model ID."""
        config = ClientConfig(ai_model="Opus 4")
        assert config.resolved_ai_model == "claude-opus-4-1@20250805"

    def test_enabled_sources(self):
        """Should return only enabled sources."""
        config = ClientConfig(
            sources=[SourceType.GMAIL, SourceType.SLACK],
            source_configs={
                "gmail": {"enabled": True},
                "slack": {"enabled": False},
                "jira": {"enabled": True},  # Not in sources list
            }
        )
        assert config.enabled_sources == [SourceType.GMAIL]

    def test_enabled_sources_defaults_to_true(self):
        """Should default to enabled if not specified."""
        config = ClientConfig(sources=[SourceType.GMAIL, SourceType.JIRA])
        assert config.enabled_sources == [SourceType.GMAIL, SourceType.JIRA]

    def test_resolved_system_prompt_default(self):
        """Should return default system prompt when None."""
        with patch('devassist.models.config.get_system_prompt', return_value="Default prompt"):
            config = ClientConfig()
            assert config.resolved_system_prompt == "Default prompt"

    def test_resolved_system_prompt_from_file(self):
        """Should load system prompt from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Custom system prompt from file")
            temp_path = f.name

        try:
            config = ClientConfig(system_prompt=temp_path)
            assert config.resolved_system_prompt == "Custom system prompt from file"
        finally:
            os.unlink(temp_path)

    def test_resolved_system_prompt_direct_string(self):
        """Should use direct string as system prompt."""
        config = ClientConfig(system_prompt="Direct prompt string")
        assert config.resolved_system_prompt == "Direct prompt string"

    def test_resolved_system_prompt_nonexistent_file(self):
        """Should fall back to default for nonexistent file."""
        with patch('devassist.models.config.get_system_prompt', return_value="Fallback"):
            config = ClientConfig(system_prompt="/nonexistent/file.md")
            assert config.resolved_system_prompt == "Fallback"


class TestClientConfigSourcesHandling:
    """Tests for available source handling."""

    def test_get_available_sources(self):
        """Should return sources based on available MCP servers."""
        # Test with actual MCP config (which should have jira and github)
        sources = ClientConfig.get_available_sources()

        # Should include sources from MCP config
        assert SourceType.JIRA in sources
        assert SourceType.GITHUB in sources

        # Should be based on actual MCP servers, not all source types
        assert len(sources) > 0

    def test_get_available_sources_fallback(self):
        """Should fallback to all sources if MCP config fails."""
        from unittest.mock import patch

        # Mock get_mcp_servers_config to raise an exception
        with patch('devassist.resources.get_mcp_servers_config', side_effect=Exception("Config error")):
            sources = ClientConfig.get_available_sources()
            # Should fallback to all source types
            assert len(sources) == len(SourceType)
            assert SourceType.GMAIL in sources
            assert SourceType.SLACK in sources
            assert SourceType.JIRA in sources
            assert SourceType.GITHUB in sources


class TestClientConfigCLIIntegration:
    """Tests for CLI argument parsing."""

    def test_from_cli_args_basic(self):
        """Should create config from CLI arguments."""
        config = ClientConfig.from_cli_args(
            sources="gmail,jira",
            model="Opus 4",
            timeout=120,
            output_format="json"
        )

        assert SourceType.GMAIL in config.resolved_sources
        assert SourceType.JIRA in config.resolved_sources
        assert config.ai_model == "claude-opus-4-1@20250805"
        assert config.ai_timeout_seconds == 120
        assert config.output_format == "json"

    def test_from_cli_args_session_management(self):
        """Should handle session options correctly."""
        config = ClientConfig.from_cli_args(session_id="test-123")
        assert config.session_id == "test-123"
        assert config.session_auto_resume is False

        config = ClientConfig.from_cli_args(resume=True)
        assert config.session_id is None
        assert config.session_auto_resume is True

    def test_from_cli_args_system_prompt(self):
        """Should handle custom system prompts."""
        config = ClientConfig.from_cli_args(system_prompt="Custom prompt")
        assert config.system_prompt == "Custom prompt"

    def test_from_cli_args_with_config_file(self):
        """Should merge CLI args with config file."""
        # Create temporary config file
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config_data = {
                "ai_model": "Sonnet 4",
                "source_configs": {
                    "gmail": {"enabled": True}
                }
            }
            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            # CLI should override file
            config = ClientConfig.from_cli_args(
                workspace_dir=temp_dir,
                model="Opus 4",
                sources="jira"
            )

            assert config.ai_model == "claude-opus-4-1@20250805"  # CLI override
            assert SourceType.JIRA in config.resolved_sources  # CLI override
            assert config.source_configs == {"gmail": {"enabled": True}}  # From file

    def test_from_cli_args_env_var_overrides(self):
        """Should apply environment variable overrides."""
        with patch.dict(os.environ, {
            "DEVASSIST_AI_MODEL": "fast",
            "DEVASSIST_AI_TIMEOUT_SECONDS": "180",
            "DEVASSIST_SOURCES": "gmail,slack"
        }):
            config = ClientConfig.from_cli_args()

            assert config.ai_model == "claude-sonnet-4-5@20250929"  # "fast"
            assert config.ai_timeout_seconds == 180
            assert SourceType.GMAIL in config.resolved_sources
            assert SourceType.SLACK in config.resolved_sources


class TestClientConfigPersistence:
    """Tests for loading and saving configuration."""

    def test_load_from_file_nonexistent(self):
        """Should return empty dict for nonexistent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = ClientConfig.load_from_file(Path(temp_dir))
            assert data == {}

    def test_load_from_file_valid(self):
        """Should load valid YAML config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config_data = {
                "ai_model": "Opus 4",
                "sources": ["gmail", "jira"],
                "ai_timeout_seconds": 120
            }

            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            loaded_data = ClientConfig.load_from_file(Path(temp_dir))
            assert loaded_data["ai_model"] == "Opus 4"
            assert loaded_data["sources"] == ["gmail", "jira"]
            assert loaded_data["ai_timeout_seconds"] == 120

    def test_save_to_file(self):
        """Should save config to YAML file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ClientConfig(
                workspace_dir=temp_dir,
                ai_model="Opus 4",
                sources=[SourceType.GMAIL, SourceType.JIRA],
                ai_timeout_seconds=120
            )

            config.save_to_file()

            # Verify file was created and has correct content
            config_path = Path(temp_dir) / "config.yaml"
            assert config_path.exists()

            with open(config_path) as f:
                saved_data = yaml.safe_load(f)

            assert saved_data["ai_model"] == "claude-opus-4-1@20250805"  # Resolved
            # Sources is a list of SourceType values, need to check properly
            sources_values = [s.value if hasattr(s, 'value') else s for s in saved_data.get("sources", [])]
            assert "gmail" in sources_values or SourceType.GMAIL in saved_data.get("sources", [])
            assert "jira" in sources_values or SourceType.JIRA in saved_data.get("sources", [])
            assert saved_data["ai_timeout_seconds"] == 120

    def test_save_excludes_computed_fields(self):
        """Should exclude computed fields from saved config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ClientConfig(workspace_dir=temp_dir)
            config.save_to_file()

            config_path = Path(temp_dir) / "config.yaml"
            with open(config_path) as f:
                saved_data = yaml.safe_load(f)

            # Should not contain computed fields
            assert "resolved_ai_model" not in saved_data
            assert "enabled_sources" not in saved_data
            assert "resolved_system_prompt" not in saved_data


class TestClientConfigLegacyCompatibility:
    """Tests for legacy configuration compatibility."""

    def test_from_legacy_config_warns(self):
        """Should emit deprecation warning."""
        legacy_config = {
            "workspace_dir": "~/test",
            "ai": {"model": "test", "timeout_seconds": 30},
            "sources": {"gmail": {"enabled": True}}
        }

        with pytest.warns(DeprecationWarning, match="from_legacy_config is deprecated"):
            config = ClientConfig.from_legacy_config(legacy_config)
            assert config.workspace_dir == Path.home() / "test"