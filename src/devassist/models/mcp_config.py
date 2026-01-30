"""MCP Server configuration models for DevAssist."""

import logging
import os
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class McpServerConfig(BaseModel):
    """MCP Server configuration with environment variable resolution."""

    type: str = Field(default="stdio", description="MCP server type")
    command: str = Field(..., description="Command to run the MCP server")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    description: str = Field(default="", description="Server description")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")

    @field_validator("env", mode="before")
    @classmethod
    def resolve_env_variables(cls, v: dict[str, str]) -> dict[str, str]:
        """Resolve environment variables for empty values.

        If a value is empty, fetch it from os.environ using the key name.
        Supports default values for specific variables.

        Args:
            v: Dictionary of environment variables

        Returns:
            Dictionary with resolved environment variables
        """
        if not isinstance(v, dict):
            return v

        # Default values for common environment variables
        defaults = {
            "CONFLUENCE_URL": "https://issues.redhat.com",
            "JIRA_SSL_VERIFY": "false",
            "CONFLUENCE_SSL_VERIFY": "false",
            "JIRA_URL": "https://issues.redhat.com"
        }

        resolved_env = {}
        for key, value in v.items():
            if not value:  # Empty string or None
                # Try to get value from environment
                env_value = os.getenv(key)
                if env_value:
                    resolved_env[key] = env_value
                    logger.debug(f"Resolved {key} from environment: ✓")
                else:
                    # Use default if available
                    default_value = defaults.get(key, "")
                    resolved_env[key] = default_value
                    logger.debug(f"Resolved {key} to default: {'✓' if default_value else '✗'}")
                if not resolved_env[key]:
                    raise RuntimeError(f"Required environment variable {key} is missing")
            elif value.startswith("${") and value.endswith("}"):
                # Handle placeholder syntax like ${JIRA_URL}
                env_var_name = value[2:-1]  # Remove ${ and }
                env_value = os.getenv(env_var_name)
                if env_value:
                    resolved_env[key] = env_value
                    logger.debug(f"Resolved {key} from placeholder ${env_var_name}: ✓")
                else:
                    # Use default if available for the env var name
                    default_value = defaults.get(env_var_name, "")
                    resolved_env[key] = default_value
                    logger.debug(f"Resolved {key} placeholder ${env_var_name} to default: {'✓' if default_value else '✗'}")
            else:
                resolved_env[key] = value

        return resolved_env