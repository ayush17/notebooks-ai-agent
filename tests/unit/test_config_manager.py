"""Unit tests for ConfigManager.

TDD: These tests are written FIRST and must FAIL before implementation.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from devassist.core.config_manager import ConfigManager
from devassist.models.config import AppConfig


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_init_creates_workspace_directory(self, tmp_path: Path) -> None:
        """ConfigManager should create workspace directory if it doesn't exist."""
        workspace = tmp_path / ".devassist"
        manager = ConfigManager(workspace_dir=workspace)

        assert workspace.exists()
        assert workspace.is_dir()

    def test_load_config_returns_default_when_no_file(self, tmp_path: Path) -> None:
        """Should return default config when no config file exists."""
        workspace = tmp_path / ".devassist"
        manager = ConfigManager(workspace_dir=workspace)

        config = manager.load_config()

        assert isinstance(config, AppConfig)
        assert config.sources == {}

    def test_save_and_load_config_roundtrip(self, tmp_path: Path) -> None:
        """Should be able to save and load config correctly."""
        workspace = tmp_path / ".devassist"
        manager = ConfigManager(workspace_dir=workspace)

        config = AppConfig(
            workspace_dir=str(workspace),
            sources={"gmail": {"enabled": True}},
        )
        manager.save_config(config)

        loaded = manager.load_config()

        assert loaded.sources == {"gmail": {"enabled": True}}

    def test_env_var_overrides_config_file(self, tmp_path: Path) -> None:
        """Environment variables should take precedence over config file."""
        workspace = tmp_path / ".devassist"
        manager = ConfigManager(workspace_dir=workspace)

        config = AppConfig(workspace_dir=str(workspace))
        manager.save_config(config)

        with patch.dict("os.environ", {"DEVASSIST_AI_PROJECT_ID": "env-project"}):
            loaded = manager.load_config()

        assert loaded.ai.project_id == "env-project"

    def test_get_source_config_returns_none_when_not_configured(
        self, tmp_path: Path
    ) -> None:
        """Should return None for unconfigured sources."""
        workspace = tmp_path / ".devassist"
        manager = ConfigManager(workspace_dir=workspace)

        result = manager.get_source_config("gmail")

        assert result is None

    def test_set_source_config_persists(self, tmp_path: Path) -> None:
        """Should persist source configuration."""
        workspace = tmp_path / ".devassist"
        manager = ConfigManager(workspace_dir=workspace)

        manager.set_source_config("gmail", {"enabled": True, "token_file": "gmail.json"})

        result = manager.get_source_config("gmail")
        assert result is not None
        assert result["enabled"] is True

    def test_remove_source_config(self, tmp_path: Path) -> None:
        """Should remove source configuration."""
        workspace = tmp_path / ".devassist"
        manager = ConfigManager(workspace_dir=workspace)

        manager.set_source_config("gmail", {"enabled": True})
        manager.remove_source_config("gmail")

        result = manager.get_source_config("gmail")
        assert result is None

    def test_list_configured_sources(self, tmp_path: Path) -> None:
        """Should list all configured sources."""
        workspace = tmp_path / ".devassist"
        manager = ConfigManager(workspace_dir=workspace)

        manager.set_source_config("gmail", {"enabled": True})
        manager.set_source_config("slack", {"enabled": True})

        sources = manager.list_sources()

        assert "gmail" in sources
        assert "slack" in sources
        assert len(sources) == 2
