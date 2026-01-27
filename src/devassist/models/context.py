"""Context models for DevAssist.

Defines core entities for context sources and items.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceType(str, Enum):
    """Types of context sources supported by DevAssist."""

    GMAIL = "gmail"
    SLACK = "slack"
    JIRA = "jira"
    GITHUB = "github"


class ConnectionStatus(str, Enum):
    """Connection status for a context source."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PENDING = "pending"  # OAuth in progress


class ContextSource(BaseModel):
    """Represents a configured integration with an external service."""

    id: str = Field(..., description="Unique identifier for this source")
    type: SourceType = Field(..., description="Type of context source")
    name: str | None = Field(None, description="User-defined display name")
    enabled: bool = Field(True, description="Whether source is active")
    config: dict[str, Any] = Field(default_factory=dict, description="Source-specific config")
    credentials: dict[str, Any] = Field(
        default_factory=dict, description="Authentication credentials"
    )
    last_sync: datetime | None = Field(None, description="Last successful sync time")
    status: ConnectionStatus = Field(
        ConnectionStatus.DISCONNECTED, description="Current connection state"
    )
    error_message: str | None = Field(None, description="Last error if status=ERROR")


class ContextItem(BaseModel):
    """A single piece of information retrieved from a context source."""

    id: str = Field(..., description="Unique identifier")
    source_id: str = Field(..., description="Reference to ContextSource")
    source_type: SourceType = Field(..., description="Type of source (denormalized)")
    timestamp: datetime = Field(..., description="When item was created/updated")
    title: str = Field(..., description="Brief title/subject", max_length=500)
    content: str | None = Field(None, description="Full content/body")
    url: str | None = Field(None, description="Link to original item")
    author: str | None = Field(None, description="Who created/sent item")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Source-specific metadata"
    )
    relevance_score: float = Field(
        0.5, description="Computed relevance", ge=0.0, le=1.0
    )
    is_read: bool = Field(False, description="Whether user has seen this item")

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    @field_validator("relevance_score")
    @classmethod
    def validate_relevance_score(cls, v: float) -> float:
        """Ensure relevance score is within bounds."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("relevance_score must be between 0.0 and 1.0")
        return v
