"""MCP Server Registry.

Manages the registry of available MCP servers and their configurations.
"""

import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any


def _file_is_executable(path: str) -> bool:
    """True if ``path`` looks runnable on this OS (POSIX + Windows)."""
    if not os.path.isfile(path):
        return False
    if sys.platform == "win32":
        lower = path.lower()
        if lower.endswith((".exe", ".cmd", ".bat", ".ps1")):
            return True
    return os.access(path, os.X_OK)


def _resolve_npm_runner() -> str:
    """Resolve ``npx`` for Node-based MCP servers (handles ``npx.cmd`` on Windows)."""
    for name in ("npx", "npx.cmd"):
        found = shutil.which(name)
        if found:
            return found
    return "npx"


def _resolve_mcp_executable(binary_name: str) -> str:
    """Resolve a standalone MCP binary: PATH, then ``.exe`` on Windows, then Unix prefixes."""
    found = shutil.which(binary_name)
    if found:
        return found
    if sys.platform == "win32":
        found = shutil.which(f"{binary_name}.exe")
        if found:
            return found
        return binary_name
    for prefix in ("/opt/homebrew/bin", "/usr/local/bin"):
        candidate = os.path.join(prefix, binary_name)
        if _file_is_executable(candidate):
            return candidate
    return binary_name


_NPX = _resolve_npm_runner()

# Atlassian-hosted MCP (stdio via ``npx mcp-remote``); see https://mcp.atlassian.com
ATLASSIAN_REMOTE_MCP_URL = "https://mcp.atlassian.com/v1/mcp"


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server.

    Attributes:
        name: Unique identifier for this server (e.g., "github", "atlassian")
        command: Command to launch the server (e.g., "npx", "uvx", "python")
        args: Arguments to pass to the command
        env: Environment variables required by the server
        description: Human-readable description of what this server provides
        enabled: Whether this server is enabled
    """

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    description: str = ""
    enabled: bool = True

    def is_configured(self) -> bool:
        """Check if server has all required environment variables set."""
        # A server is configured if all env vars have non-empty values
        return all(v for v in self.env.values())


class MCPRegistry:
    """Registry of available MCP servers.

    Manages the list of MCP servers that can be connected to,
    including their configurations and credentials.
    """

    # Default MCP servers available
    DEFAULT_SERVERS: dict[str, MCPServerConfig] = {
        "github": MCPServerConfig(
            name="github",
            command=_NPX,
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": ""},
            description="GitHub integration - repos, issues, PRs, notifications",
        ),
        "gmail": MCPServerConfig(
            name="gmail",
            command=_NPX,
            args=["-y", "@modelcontextprotocol/server-google-drive"],
            env={"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": "", "GOOGLE_REDIRECT_URI": ""},
            description="Gmail/Google Drive integration - emails, documents",
        ),
        "filesystem": MCPServerConfig(
            name="filesystem",
            command=_NPX,
            args=["-y", "@modelcontextprotocol/server-filesystem", tempfile.gettempdir()],
            env={},
            description="Local filesystem access",
        ),
        "atlassian": MCPServerConfig(
            name="atlassian",
            command=_NPX,
            args=["-y", "mcp-remote", ATLASSIAN_REMOTE_MCP_URL],
            env={},
            description="Atlassian Cloud (remote MCP) - Jira, Confluence via mcp.atlassian.com",
            enabled=False,
        ),
    }

    def __init__(self) -> None:
        """Initialize the registry with default servers.
        
        Environment variables from the system are automatically loaded
        to configure servers (e.g., GITHUB_PERSONAL_ACCESS_TOKEN). Atlassian uses
        remote MCP (``mcp-remote``); auth is handled when the connector runs.
        """
        self._servers: dict[str, MCPServerConfig] = {}
        # Load defaults and populate from environment
        for name, config in self.DEFAULT_SERVERS.items():
            # Copy env vars and populate from system environment
            env = {}
            for key in config.env.keys():
                if name == "github" and key == "GITHUB_PERSONAL_ACCESS_TOKEN":
                    env[key] = (
                        os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
                        or os.environ.get("GITHUB_TOKEN")
                        or os.environ.get("GH_TOKEN")
                        or ""
                    )
                else:
                    env[key] = os.environ.get(key, "")
            
            # Copy args and handle special cases
            args = config.args.copy()
            
            # For Atlassian, inject the site URL into the --resource arg
            if name == "atlassian" and env.get("ATLASSIAN_SITE_URL"):
                # Replace the empty placeholder with the actual site URL
                for i, arg in enumerate(args):
                    if arg == "" and i > 0 and args[i - 1] == "--resource":
                        args[i] = env["ATLASSIAN_SITE_URL"]
                        break
            
            self._servers[name] = MCPServerConfig(
                name=config.name,
                command=config.command,
                args=args,
                env=env,
                description=config.description,
                enabled=config.enabled,
            )

    def register(self, config: MCPServerConfig) -> None:
        """Register an MCP server configuration.

        Args:
            config: Server configuration to register.
        """
        self._servers[config.name] = config

    def get(self, name: str) -> MCPServerConfig | None:
        """Get a server configuration by name.

        Args:
            name: Server name.

        Returns:
            Server config if found, None otherwise.
        """
        return self._servers.get(name)

    def list_all(self) -> list[MCPServerConfig]:
        """Get all registered servers.

        Returns:
            List of all server configurations.
        """
        return list(self._servers.values())

    def list_configured(self) -> list[MCPServerConfig]:
        """Get servers that have valid credentials configured.

        Returns:
            List of configured and enabled server configurations.
        """
        return [
            server
            for server in self._servers.values()
            if server.enabled and server.is_configured()
        ]

    def configure_server(self, name: str, env_vars: dict[str, str]) -> bool:
        """Configure a server with environment variables.

        Args:
            name: Server name.
            env_vars: Environment variables to set.

        Returns:
            True if server was found and configured.
        """
        server = self._servers.get(name)
        if not server:
            return False

        server.env.update(env_vars)
        return True

    def enable_server(self, name: str, enabled: bool = True) -> bool:
        """Enable or disable a server.

        Args:
            name: Server name.
            enabled: Whether to enable the server.

        Returns:
            True if server was found and updated.
        """
        server = self._servers.get(name)
        if not server:
            return False

        server.enabled = enabled
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry to dictionary for persistence.

        Returns:
            Dictionary representation of the registry.
        """
        return {
            name: {
                "command": server.command,
                "args": server.args,
                "env": server.env,
                "description": server.description,
                "enabled": server.enabled,
            }
            for name, server in self._servers.items()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPRegistry":
        """Create registry from dictionary.

        Args:
            data: Dictionary representation.

        Returns:
            New MCPRegistry instance.
        """
        registry = cls()
        for name, config_data in data.items():
            registry.register(
                MCPServerConfig(
                    name=name,
                    command=config_data.get("command", ""),
                    args=config_data.get("args", []),
                    env=config_data.get("env", {}),
                    description=config_data.get("description", ""),
                    enabled=config_data.get("enabled", True),
                )
            )
        return registry
