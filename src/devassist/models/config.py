"""Configuration models for DevAssist.

Defines application configuration structures.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    """Configuration for a single context source."""

    enabled: bool = Field(True, description="Whether source is enabled")
    credentials_file: str | None = Field(None, description="Path to credentials file")
    token: str | None = Field(None, description="API token (if applicable)")
    url: str | None = Field(None, description="Service URL (if applicable)")
    email: str | None = Field(None, description="User email (if applicable)")
    extra: dict[str, Any] = Field(default_factory=dict, description="Additional config")


class AIConfig(BaseModel):
    """Configuration for AI service integration."""

    project_id: str = Field("", description="GCP project ID")
    location: str = Field("us-central1", description="GCP region")
    model: str = Field("gemini-1.5-flash", description="Model to use")
    max_retries: int = Field(3, description="Max retry attempts")
    timeout_seconds: int = Field(60, description="Request timeout")


class PreferencesConfig(BaseModel):
    """User preference configuration."""

    priority_keywords: list[str] = Field(
        default_factory=list, description="Keywords to prioritize"
    )


class AppConfig(BaseModel):
    """Main application configuration."""

    workspace_dir: str = Field(
        "~/.devassist", description="Workspace directory path"
    )
    sources: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Configured sources"
    )
    ai: AIConfig = Field(default_factory=AIConfig, description="AI configuration")
    preferences: PreferencesConfig = Field(
        default_factory=PreferencesConfig, description="User preferences"
    )

    def get_workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.workspace_dir).expanduser()
