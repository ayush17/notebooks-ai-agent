"""DevAssist - Developer Assistant CLI.

A CLI application that aggregates context from multiple developer tools
and uses AI to generate a Unified Morning Brief.
"""

__version__ = "0.1.0"
__author__ = "kami619"
__email__ = "kakella@redhat.com"

from devassist.models.context import SourceType

__all__ = [
    "__version__",
    "SourceType",
    # Legacy models removed - not used in MCP-based architecture:
    # - "ContextItem": Replaced by direct Claude API aggregation via MCP
    # - "ContextSource": Replaced by McpServerConfig + MCP servers
]
