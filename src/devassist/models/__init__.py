"""Data models for DevAssist."""

from devassist.models.context import (
    ConnectionStatus,
    SourceType,
)
from devassist.models.mcp_config import McpServerConfig

__all__ = [
    "ConnectionStatus",
    "SourceType",
    "McpServerConfig",
    # Legacy models removed - not used in MCP-based architecture:
    # - ContextSource: Replaced by McpServerConfig + MCP servers
    # - ContextItem: Replaced by direct Claude API aggregation via MCP
]
