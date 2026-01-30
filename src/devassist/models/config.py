"""Client configuration model for DevAssist.

Consolidates all configuration into a single, smart ClientConfig class with:
- User-friendly AI model names
- Single sources field with auto-discovery
- Flexible system prompts (file/string/default)
- Session management validation
- Smart deserialization from CLI inputs
"""

import json
import logging
import os
import warnings
from pathlib import Path
from typing import Any, ClassVar

import yaml
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from devassist.models.context import SourceType

# Import resources functions with safe fallback
try:
    from devassist.resources import get_personal_assistant_system_prompt
except ImportError:
    # Fallback for testing
    def get_system_prompt() -> str:
        return "You are a helpful developer assistant."

logger = logging.getLogger(__name__)


class ClientConfig(BaseModel):
    """Client configuration with smart deserialization.

    This class consolidates all configuration needs:
    - Source selection and credentials
    - AI model and timeout configuration
    - Session management settings
    - Output formatting
    - System prompt customization
    """

    # Workspace & Persistence
    workspace_dir: Path = Field(
        default_factory=lambda: Path.home() / ".devassist",
        description="DevAssist workspace directory"
    )

    # Source Configuration (single field approach)
    sources: list[SourceType] | None = Field(
        default=None,
        description="Sources to use for brief generation (None = all available)"
    )
    source_configs: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-source configuration (credentials, settings)"
    )

    # AI Configuration with user-friendly model names
    ai_model: str = Field(
        default="opus",
        description="AI model to use (user-friendly name)"
    )
    ai_timeout_seconds: int = Field(
        default=120,
        description="AI query timeout (10-600 seconds)"
    )

    # Session Management (mutually exclusive)
    session_id: str | None = Field(
        default=None,
        description="Specific session ID to resume"
    )
    session_auto_resume: bool = Field(
        default=False,
        description="Auto-resume latest session"
    )

    # Output Configuration
    output_format: str = Field(
        default="markdown",
        description="Output format (markdown or json)"
    )
    system_prompt: str | Path | None = Field(
        default=None,
        description="System prompt (file path, direct string, or None for default)"
    )
    permission_mode: str = Field(
        default="bypassPermissions",
        description="Claude SDK permission mode (bypassPermissions allows tool usage)"
    )

    # User Preferences (from old PreferencesConfig)
    priority_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords to prioritize in briefs"
    )

    # Legacy compatibility (will be deprecated)
    ai: dict[str, Any] = Field(
        default_factory=dict,
        description="Legacy AI config (deprecated)"
    )

    # Model mapping for user experience
    MODEL_MAPPING: ClassVar[dict[str, str]] = {
        # Sonnet models
        "sonnet 4": "claude-sonnet-4@20250514",
        "sonnet 4.5": "claude-sonnet-4-5@20250929",
        "sonnet": "claude-sonnet-4-5@20250929",  # Latest Sonnet

        # Opus models
        "opus 4": "claude-opus-4-1@20250805",
        "opus 4.1": "claude-opus-4-1@20250805",
        "opus 4.5": "claude-opus-4-5@20251101",
        "opus": "claude-opus-4-5@20251101",  # Latest Opus

        # Convenience aliases
        "fast": "claude-sonnet-4-5@20250929",  # Fast/cheap option
        "best": "claude-opus-4-5@20251101",   # Best quality
        "default": "claude-sonnet-4@20250514",  # Balanced default
        "cheap": "claude-sonnet-4@20250514",   # Most cost-effective
    }

    @field_validator("workspace_dir", mode="before")
    @classmethod
    def expand_workspace_dir(cls, v: Any) -> Path:
        """Expand workspace directory path."""
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        elif isinstance(v, Path):
            return v.expanduser().resolve()
        return Path(v)

    @field_validator("sources", mode="before")
    @classmethod
    def parse_sources(cls, v: Any) -> list[SourceType]:
        """Convert CLI string/None to SourceType list."""
        if v is None:
            # Default: use all available sources
            return cls.get_available_sources()

        if isinstance(v, str):
            if v.strip() == "":
                return cls.get_available_sources()
            # Handle "gmail,jira" from CLI
            v = [s.strip() for s in v.split(",")]

        if isinstance(v, list):
            if len(v) == 0:
                return cls.get_available_sources()

            result = []
            for item in v:
                if isinstance(item, SourceType):
                    result.append(item)
                elif isinstance(item, str):
                    try:
                        result.append(SourceType(item.lower().strip()))
                    except ValueError:
                        logger.warning(f"Unknown source type: {item}")
            return result

        # Fallback to available sources
        return cls.get_available_sources()

    @field_validator("ai_model", mode="before")
    @classmethod
    def resolve_ai_model(cls, v: Any) -> str:
        """Convert user-friendly model name to technical ID."""
        if not isinstance(v, str):
            v = str(v)

        # Normalize input (lowercase, strip)
        normalized = v.lower().strip()

        # Check if it's already a technical ID
        if normalized.startswith("claude-"):
            logger.info(f"Using technical model ID: {v}")
            return v

        # Look up in mapping (exact match)
        if normalized in cls.MODEL_MAPPING:
            technical_id = cls.MODEL_MAPPING[normalized]
            logger.info(f"Resolved model '{v}' → '{technical_id}'")
            return technical_id

        # Partial matching for flexibility
        for friendly_name, technical_id in cls.MODEL_MAPPING.items():
            if friendly_name in normalized or normalized in friendly_name:
                logger.info(f"Partial match: '{v}' → '{technical_id}'")
                return technical_id

        # If no match found, log warning and use default
        logger.warning(f"Unknown model '{v}', using default")
        return cls.MODEL_MAPPING["default"]

    @field_validator("ai_timeout_seconds")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is reasonable."""
        if v < 10:
            logger.warning("Timeout too low, using 10 seconds minimum")
            return 10
        if v > 600:
            logger.warning("Timeout too high, using 10 minutes maximum")
            return 600
        return v

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        """Validate output format."""
        normalized = v.lower().strip()
        if normalized not in ["markdown", "json"]:
            logger.warning(f"Unknown output format '{v}', using markdown")
            return "markdown"
        return normalized

    @field_validator("permission_mode")
    @classmethod
    def validate_permission_mode(cls, v: str) -> str:
        """Validate Claude SDK permission mode."""
        valid_modes = ["default", "acceptEdits", "plan", "bypassPermissions"]
        if v not in valid_modes:
            logger.warning(f"Unknown permission mode '{v}', using bypassPermissions")
            return "bypassPermissions"
        return v

    @model_validator(mode="after")
    def validate_session_options(self) -> "ClientConfig":
        """Ensure session options don't conflict."""
        if self.session_id is not None and self.session_auto_resume:
            raise ValueError(
                "Cannot specify both session_id and session_auto_resume. "
                "Use session_id to resume a specific session, or "
                "session_auto_resume=True to resume the latest session."
            )
        return self

    @computed_field
    @property
    def resolved_ai_model(self) -> str:
        """Get the resolved technical AI model ID."""
        return self.ai_model  # Already resolved by validator

    @computed_field
    @property
    def resolved_sources(self) -> list[SourceType]:
        """Get final resolved list of sources to use."""
        if self.sources is None:
            return self.get_available_sources()
        return self.sources

    @computed_field
    @property
    def enabled_sources(self) -> list[SourceType]:
        """Get sources that are enabled in configuration."""
        enabled = []
        for source in self.resolved_sources:
            source_config = self.source_configs.get(source.value, {})
            if source_config.get("enabled", True):  # Default to enabled
                enabled.append(source)
        return enabled

    @computed_field
    @property
    def resolved_system_prompt(self) -> str:
        """Resolve system prompt from various input types."""
        if self.system_prompt is None:
            # Default: load from resources
            return get_personal_assistant_system_prompt()

        if isinstance(self.system_prompt, (str, Path)):
            # Check if it looks like a file path (contains / or \ or ends with common extensions)
            path_str = str(self.system_prompt)
            looks_like_path = (
                "/" in path_str or
                "\\" in path_str or
                path_str.endswith(('.md', '.txt', '.prompt'))
            )

            if looks_like_path:
                path = Path(self.system_prompt)
                if path.exists() and path.is_file():
                    try:
                        return path.read_text(encoding="utf-8")
                    except Exception as e:
                        logger.warning(f"Failed to read system prompt file {path}: {e}")
                        return get_personal_assistant_system_prompt()
                else:
                    # File path specified but doesn't exist - fall back to default
                    logger.warning(f"System prompt file not found: {path}")
                    return get_personal_assistant_system_prompt()

            # Otherwise treat as direct string content
            return str(self.system_prompt)

        return str(self.system_prompt)


    @classmethod
    def get_available_sources(cls) -> list[SourceType]:
        """Get available source types based on configured MCP servers."""
        try:
            from devassist.resources import get_mcp_servers_config
            mcp_config = get_mcp_servers_config()
            available = []

            # Check which sources have corresponding MCP servers configured
            for server_name in mcp_config.keys():
                try:
                    source_type = SourceType(server_name)
                    available.append(source_type)
                    logger.debug(f"Found available source: {server_name}")
                except ValueError:
                    logger.debug(f"Skipping unknown source type: {server_name}")

            if available:
                logger.info(f"Available sources from MCP config: {[s.value for s in available]}")
                return available
            else:
                logger.warning("No valid sources found in MCP config, falling back to all sources")
                return list(SourceType)

        except Exception as e:
            logger.warning(f"Failed to load MCP config: {e}, falling back to all sources")
            return list(SourceType)


    @classmethod
    def from_cli_args(
        cls,
        sources: str | None = None,
        session_id: str | None = None,
        resume: bool = False,
        output_format: str = "markdown",
        model: str | None = None,
        timeout: int | None = None,
        system_prompt: str | None = None,
        workspace_dir: str | None = None,
        **kwargs
    ) -> "ClientConfig":
        """Create ClientConfig from CLI arguments.

        Args:
            sources: Comma-separated source names or None for all
            session_id: Specific session ID to resume
            resume: Auto-resume latest session
            output_format: Output format (markdown/json)
            model: AI model name (user-friendly)
            timeout: AI timeout in seconds
            system_prompt: Custom system prompt (file or string)
            workspace_dir: Custom workspace directory
            **kwargs: Additional config overrides

        Returns:
            ClientConfig instance with CLI args applied.
        """
        # Load base config from file
        base_config = {}
        try:
            if workspace_dir:
                workspace_path = Path(workspace_dir).expanduser()
            else:
                workspace_path = Path.home() / ".devassist"

            config_path = workspace_path / "config.yaml"
            if config_path.exists():
                with open(config_path) as f:
                    file_data = yaml.safe_load(f)
                    if file_data:
                        base_config = file_data
        except Exception as e:
            logger.warning(f"Failed to load config file: {e}")

        # Apply CLI overrides
        if sources is not None:
            base_config["sources"] = sources
        if session_id is not None:
            base_config["session_id"] = session_id
        if resume:
            base_config["session_auto_resume"] = True
        if output_format != "markdown":
            base_config["output_format"] = output_format
        if model is not None:
            base_config["ai_model"] = model
        if timeout is not None:
            base_config["ai_timeout_seconds"] = timeout
        if system_prompt is not None:
            base_config["system_prompt"] = system_prompt
        if workspace_dir is not None:
            base_config["workspace_dir"] = workspace_dir

        # Apply any additional kwargs
        base_config.update(kwargs)

        # Apply environment variable overrides
        cls._apply_env_overrides(base_config)

        return cls(**base_config)

    @classmethod
    def load_from_file(cls, workspace_dir: Path | None = None) -> dict[str, Any]:
        """Load config data from YAML file.

        Args:
            workspace_dir: Workspace directory path

        Returns:
            Configuration dictionary
        """
        if workspace_dir is None:
            workspace_dir = Path.home() / ".devassist"

        config_path = workspace_dir / "config.yaml"
        if not config_path.exists():
            return {}

        try:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}

            # Apply environment variable overrides
            cls._apply_env_overrides(data)
            return data
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return {}

    def save_to_file(self) -> None:
        """Save config to YAML file.

        Excludes computed fields and sensitive information.
        """
        # Ensure workspace directory exists
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        config_path = self.workspace_dir / "config.yaml"

        # Export config excluding computed fields and internal data
        config_data = self.model_dump(
            mode="json",
            exclude={
                "resolved_ai_model",
                "enabled_sources",
                "resolved_system_prompt"
            }
        )

        try:
            with open(config_path, "w") as f:
                yaml.safe_dump(
                    config_data,
                    f,
                    default_flow_style=False,
                    sort_keys=True
                )
            logger.info(f"Saved config to {config_path}")
        except Exception as e:
            logger.error(f"Failed to save config to {config_path}: {e}")
            raise

    @classmethod
    def _apply_env_overrides(cls, config_data: dict[str, Any]) -> None:
        """Apply environment variable overrides to config data.

        Supports:
            - DEVASSIST_AI_MODEL
            - DEVASSIST_AI_TIMEOUT_SECONDS
            - DEVASSIST_WORKSPACE_DIR
            - DEVASSIST_OUTPUT_FORMAT
            - DEVASSIST_SOURCES

        Args:
            config_data: Config dictionary to modify in-place
        """
        env_prefix = "DEVASSIST_"

        # Direct overrides
        if model := os.environ.get(f"{env_prefix}AI_MODEL"):
            config_data["ai_model"] = model
        if timeout := os.environ.get(f"{env_prefix}AI_TIMEOUT_SECONDS"):
            try:
                config_data["ai_timeout_seconds"] = int(timeout)
            except ValueError:
                logger.warning(f"Invalid timeout value in env: {timeout}")
        if workspace := os.environ.get(f"{env_prefix}WORKSPACE_DIR"):
            config_data["workspace_dir"] = workspace
        if output_fmt := os.environ.get(f"{env_prefix}OUTPUT_FORMAT"):
            config_data["output_format"] = output_fmt
        if sources := os.environ.get(f"{env_prefix}SOURCES"):
            config_data["sources"] = sources

    @classmethod
    def from_legacy_config(cls, legacy_config: Any) -> "ClientConfig":
        """Create ClientConfig from legacy ConfigManager config (deprecated).

        Args:
            legacy_config: Old ClientConfig instance

        Returns:
            New unified ClientConfig
        """
        warnings.warn(
            "from_legacy_config is deprecated. Use ClientConfig.from_cli_args() or ClientConfig.load_from_file()",
            DeprecationWarning,
            stacklevel=2,
        )

        if hasattr(legacy_config, 'model_dump'):
            old_config = legacy_config.model_dump()
        elif hasattr(legacy_config, 'dict'):
            old_config = legacy_config.dict()
        else:
            old_config = dict(legacy_config)

        # Map legacy fields to new structure
        new_config = {
            "workspace_dir": old_config.get("workspace_dir", "~/.devassist"),
            "source_configs": old_config.get("sources", {}),
        }

        # Map legacy AI config
        if "ai" in old_config:
            ai_config = old_config["ai"]
            new_config["ai_model"] = ai_config.get("model", "Sonnet 4")
            new_config["ai_timeout_seconds"] = ai_config.get("timeout_seconds", 60)

        return cls(**new_config)