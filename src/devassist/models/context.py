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
