"""Tests for MCP server registry."""

import tempfile
from unittest.mock import patch

import pytest

from devassist.mcp.registry import (
    ATLASSIAN_REMOTE_MCP_URL,
    MCPRegistry,
    _resolve_mcp_executable,
)


def test_resolve_mcp_executable_prefers_which() -> None:
    with patch("devassist.mcp.registry.shutil.which", return_value="/custom/bin/some-mcp"):
        assert _resolve_mcp_executable("some-mcp") == "/custom/bin/some-mcp"


def test_atlassian_default_uses_mcp_remote() -> None:
    reg = MCPRegistry()
    cfg = reg.get("atlassian")
    assert cfg is not None
    assert "npx" in cfg.command.lower()
    assert cfg.args == ["-y", "mcp-remote", ATLASSIAN_REMOTE_MCP_URL]
    assert cfg.env == {}
    assert cfg.enabled is False  # opt-in via -s atlassian, not default auto-connect


def test_github_registry_accepts_github_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Official GitHub MCP reads GITHUB_PERSONAL_ACCESS_TOKEN; many users only set GITHUB_TOKEN."""
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_from_alt")
    reg = MCPRegistry()
    gh = reg.get("github")
    assert gh is not None
    assert gh.env.get("GITHUB_PERSONAL_ACCESS_TOKEN") == "ghp_from_alt"
    assert gh.is_configured()


def test_filesystem_mcp_uses_os_temp_dir() -> None:
    reg = MCPRegistry()
    fs = reg.get("filesystem")
    assert fs is not None
    assert fs.args[-1] == tempfile.gettempdir()
