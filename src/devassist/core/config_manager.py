"""Configuration manager for DevAssist.

Handles loading, saving, and managing application configuration.
Supports environment variable overrides.
"""

import os
from pathlib import Path
from typing import Any

import yaml

from devassist.core.env_store import (
    SOURCE_ENV_KEYS,
    read_devassist_env_dict,
    remove_devassist_env_keys,
    source_config_from_env,
)
from devassist.models.config import AIConfig, AppConfig, sanitize_gcp_field
from devassist.utils.gcp_env import resolve_gcp_project_id


def infer_ai_updates_from_env(env: dict[str, str]) -> dict[str, Any]:
    """Derive persisted ``ai`` YAML fields from ``~/.devassist/env`` (brief + tooling alignment).

    Honors ``DEVASSIST_AI_PROVIDER`` when set in the env file, else infers from
    Vertex vs direct Anthropic API credentials.
    """
    explicit = sanitize_gcp_field(env.get("DEVASSIST_AI_PROVIDER", "")).lower()
    if explicit:
        if explicit in ("vertex", "google"):
            explicit = "gemini"
        if explicit in ("anthropic", "gemini"):
            return {"provider": explicit}

    use_vertex = (env.get("CLAUDE_CODE_USE_VERTEX") or "").strip() == "1"
    pid = sanitize_gcp_field(env.get("ANTHROPIC_VERTEX_PROJECT_ID", ""))
    region = sanitize_gcp_field(env.get("CLOUD_ML_REGION", ""))
    if use_vertex and pid:
        updates: dict[str, Any] = {"provider": "gemini", "project_id": pid}
        if region:
            updates["location"] = region
        return updates
    if (env.get("ANTHROPIC_API_KEY") or "").strip():
        return {"provider": "anthropic"}
    return {}


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
        if provider := os.environ.get(f"{self.ENV_PREFIX}AI_PROVIDER"):
            ai_overrides["provider"] = provider
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

        # Brief uses ``config.ai.project_id``; honor env vars and active ``gcloud`` profile
        current_ai = config_dict.get("ai") or {}
        if not (current_ai.get("project_id") or "").strip():
            if pid := resolve_gcp_project_id():
                current_ai["project_id"] = pid
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

        Secrets live in ``~/.devassist/env``; YAML may only store ``enabled: true``.
        Values from the environment override YAML for the same keys.

        Args:
            source_name: Name of the source (e.g., 'gmail', 'slack').

        Returns:
            Source configuration dict or None if not configured.
        """
        config = self._config or self.load_config()
        yaml_cfg = config.sources.get(source_name) or {}
        env_cfg = source_config_from_env(source_name)
        merged: dict[str, Any] = {**yaml_cfg}
        for k, v in env_cfg.items():
            if v:
                merged[k] = v
        if not merged:
            return None
        return merged

    def set_source_config(
        self, source_name: str, source_config: dict[str, Any]
    ) -> None:
        """Set non-secret source flags in YAML (secrets belong in ``~/.devassist/env``).

        Args:
            source_name: Name of the source.
            source_config: Configuration dict for the source.
        """
        config = self._config or self.load_config()
        config.sources[source_name] = source_config
        self.save_config(config)

    def remove_source_config(self, source_name: str) -> bool:
        """Remove YAML entry and clear related keys from env files.

        Args:
            source_name: Name of the source to remove.

        Returns:
            True if something was removed from YAML or from the env file.
        """
        config = self._config or self.load_config()
        sn = source_name.lower()
        removed = False
        if sn in config.sources:
            del config.sources[sn]
            self.save_config(config)
            removed = True
        keys = SOURCE_ENV_KEYS.get(sn, ())
        if keys:
            prior = read_devassist_env_dict()
            if any(k in prior for k in keys):
                remove_devassist_env_keys(keys)
                removed = True
        return removed

    def list_sources(self) -> list[str]:
        """List all configured source names.

        Includes sources declared in YAML and sources implied by env files.

        Returns:
            List of configured source names.
        """
        config = self._config or self.load_config()
        names = set(config.sources.keys())
        for candidate in sorted(SOURCE_ENV_KEYS):
            if source_config_from_env(candidate):
                names.add(candidate)
        return sorted(names)

    def get_ai_config(self) -> dict[str, Any]:
        """Get AI configuration.

        Returns:
            AI configuration dict.
        """
        config = self._config or self.load_config()
        return config.ai.model_dump() if config.ai else {}

    def get_mcp_config(self) -> dict[str, Any]:
        """Get MCP servers configuration.

        Returns:
            MCP configuration dict with server configs.
        """
        config = self._config or self.load_config()
        return getattr(config, "mcp_servers", {}) or {}

    def set_mcp_server_config(
        self, server_name: str, server_config: dict[str, Any]
    ) -> None:
        """Set configuration for an MCP server.

        Args:
            server_name: Name of the MCP server.
            server_config: Configuration dict for the server.
        """
        config = self._config or self.load_config()
        if not hasattr(config, "mcp_servers") or config.mcp_servers is None:
            config.mcp_servers = {}
        config.mcp_servers[server_name] = server_config
        self.save_config(config)

    def sync_ai_yaml_from_env_store(self) -> bool:
        """Merge ``infer_ai_updates_from_env`` into ``config.yaml`` and save if anything changes.

        Call after updating ``~/.devassist/env`` so ``ai.provider`` / ``project_id`` stay aligned
        with Claude (Vertex vs API) credentials.
        """
        merged = read_devassist_env_dict()
        updates = infer_ai_updates_from_env(merged)
        if not updates:
            return False
        config = self.load_config()
        ai_dict = config.ai.model_dump()
        ai_dict.update(updates)
        new_ai = AIConfig(**ai_dict)
        new_config = config.model_copy(update={"ai": new_ai})
        self.save_config(new_config)
        return True
