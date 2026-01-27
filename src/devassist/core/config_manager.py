"""Configuration manager for DevAssist.

Handles loading, saving, and managing application configuration.
Supports environment variable overrides.
"""

import os
from pathlib import Path
from typing import Any

import yaml

from devassist.models.config import AIConfig, AppConfig


class ConfigManager:
    """Manages application configuration with YAML persistence and env var support."""

    CONFIG_FILENAME = "config.yaml"
    ENV_PREFIX = "DEVASSIST_"

    def __init__(self, workspace_dir: Path | str | None = None) -> None:
        """Initialize ConfigManager.

        Args:
            workspace_dir: Path to workspace directory. Defaults to ~/.devassist
        """
        if workspace_dir is None:
            workspace_dir = Path.home() / ".devassist"
        self.workspace_dir = Path(workspace_dir)
        self._ensure_workspace_exists()
        self._config: AppConfig | None = None

    def _ensure_workspace_exists(self) -> None:
        """Create workspace directory if it doesn't exist."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    @property
    def config_path(self) -> Path:
        """Get path to config file."""
        return self.workspace_dir / self.CONFIG_FILENAME

    def load_config(self) -> AppConfig:
        """Load configuration from file with environment variable overrides.

        Returns:
            AppConfig instance with merged file and env var settings.
        """
        # Start with defaults
        config_data: dict[str, Any] = {}

        # Load from file if exists
        if self.config_path.exists():
            with open(self.config_path) as f:
                file_data = yaml.safe_load(f)
                if file_data:
                    config_data = file_data

        # Create config from file data
        config = AppConfig(**config_data)

        # Apply environment variable overrides
        config = self._apply_env_overrides(config)

        self._config = config
        return config

    def _apply_env_overrides(self, config: AppConfig) -> AppConfig:
        """Apply environment variable overrides to config.

        Supports:
            - DEVASSIST_AI_PROJECT_ID
            - DEVASSIST_AI_LOCATION
            - DEVASSIST_AI_MODEL
            - DEVASSIST_WORKSPACE_DIR

        Args:
            config: Base config to override.

        Returns:
            Config with env var overrides applied.
        """
        config_dict = config.model_dump()

        # AI config overrides
        ai_overrides: dict[str, Any] = {}
        if project_id := os.environ.get(f"{self.ENV_PREFIX}AI_PROJECT_ID"):
            ai_overrides["project_id"] = project_id
        if location := os.environ.get(f"{self.ENV_PREFIX}AI_LOCATION"):
            ai_overrides["location"] = location
        if model := os.environ.get(f"{self.ENV_PREFIX}AI_MODEL"):
            ai_overrides["model"] = model

        if ai_overrides:
            current_ai = config_dict.get("ai", {})
            current_ai.update(ai_overrides)
            config_dict["ai"] = current_ai

        # Workspace dir override
        if workspace := os.environ.get(f"{self.ENV_PREFIX}WORKSPACE_DIR"):
            config_dict["workspace_dir"] = workspace

        return AppConfig(**config_dict)

    def save_config(self, config: AppConfig) -> None:
        """Save configuration to YAML file.

        Args:
            config: AppConfig instance to save.
        """
        self._ensure_workspace_exists()
        config_dict = config.model_dump()

        with open(self.config_path, "w") as f:
            yaml.safe_dump(config_dict, f, default_flow_style=False)

        self._config = config

    def get_source_config(self, source_name: str) -> dict[str, Any] | None:
        """Get configuration for a specific source.

        Args:
            source_name: Name of the source (e.g., 'gmail', 'slack').

        Returns:
            Source configuration dict or None if not configured.
        """
        config = self._config or self.load_config()
        return config.sources.get(source_name)

    def set_source_config(
        self, source_name: str, source_config: dict[str, Any]
    ) -> None:
        """Set configuration for a specific source.

        Args:
            source_name: Name of the source.
            source_config: Configuration dict for the source.
        """
        config = self._config or self.load_config()
        config.sources[source_name] = source_config
        self.save_config(config)

    def remove_source_config(self, source_name: str) -> bool:
        """Remove configuration for a specific source.

        Args:
            source_name: Name of the source to remove.

        Returns:
            True if source was removed, False if it didn't exist.
        """
        config = self._config or self.load_config()
        if source_name in config.sources:
            del config.sources[source_name]
            self.save_config(config)
            return True
        return False

    def list_sources(self) -> list[str]:
        """List all configured source names.

        Returns:
            List of configured source names.
        """
        config = self._config or self.load_config()
        return list(config.sources.keys())
