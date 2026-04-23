"""Configuration models for DevAssist.

Defines application configuration structures.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Vertex AI: gemini-1.5-* IDs are retired; use a current stable Flash model ID.
DEFAULT_VERTEX_GEMINI_MODEL = "gemini-2.0-flash-001"


def sanitize_gcp_field(value: Any) -> str:
    """Strip whitespace and copy-paste junk from GCP project IDs, regions, and model names.

    Catches pasted values like ``itpc-gcp-ai-eng-claude)``, ``"my-project",``, or ``my-proj/``
    that would otherwise produce invalid Vertex resource paths (404 Publisher Model).
    """
    if value is None:
        return ""
    s = str(value).strip()
    _lead_junk = frozenset({'"', "'", "(", "<", "[", "{"})
    _trail_junk = frozenset({')', '"', "'", "]", "}", ">", "/", ",", ";", ":"})
    while s and s[0] in _lead_junk:
        s = s[1:].lstrip()
    while s and s[-1] in _trail_junk:
        s = s[:-1].rstrip()
    return s


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

    provider: str = Field(
        "anthropic",
        description="Brief summarization: 'anthropic' (Claude) or 'gemini' (Vertex AI Gemini)",
    )
    project_id: str = Field("", description="GCP project ID (for Gemini on Vertex)")
    location: str = Field("us-central1", description="GCP region")
    model: str = Field(DEFAULT_VERTEX_GEMINI_MODEL, description="Gemini model id when provider is gemini")
    max_retries: int = Field(3, description="Max retry attempts")
    timeout_seconds: int = Field(60, description="Request timeout")

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize_provider(cls, v: Any) -> str:
        s = sanitize_gcp_field(v or "anthropic").lower()
        if s in ("vertex", "google"):
            return "gemini"
        return s if s in ("anthropic", "gemini") else "anthropic"

    @field_validator("project_id", "location", "model", mode="before")
    @classmethod
    def _sanitize_ids(cls, v: Any) -> str:
        return sanitize_gcp_field(v)


class PreferencesConfig(BaseModel):
    """User preference configuration."""

    priority_keywords: list[str] = Field(
        default_factory=list, description="Keywords to prioritize"
    )


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""

    command: str = Field("npx", description="Command to run the server")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    enabled: bool = Field(True, description="Whether server is enabled")


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
    mcp_servers: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="MCP server configurations"
    )

    def get_workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.workspace_dir).expanduser()
