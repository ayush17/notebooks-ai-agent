"""Shared MCP + orchestration agent bootstrap for ``chat`` and ``ask`` commands."""

from __future__ import annotations

from typing import Literal

import typer
from rich.console import Console
from rich.panel import Panel

from devassist.core.config_manager import ConfigManager
from devassist.core.exceptions import format_user_facing_error
from devassist.mcp.client import MCPClient
from devassist.mcp.registry import MCPServerConfig, MCPRegistry
from devassist.orchestrator.agent import OrchestrationAgent
from devassist.orchestrator.llm_client import AnthropicLLMClient, VertexAILLMClient

_NO_SERVERS_PANELS: dict[Literal["chat", "ask"], tuple[str, str]] = {
    "chat": (
        "[yellow]No MCP servers configured.[/yellow]\n\n"
        "To configure servers, run:\n"
        "  [cyan]devassist setup[/cyan]\n\n"
        "Or specify servers with credentials via environment:\n"
        "  GITHUB_PERSONAL_ACCESS_TOKEN=xxx devassist chat -s github",
        "No Servers Available",
    ),
    "ask": (
        "[yellow]No MCP servers configured.[/yellow]\n\n"
        "To configure servers, add them to your config:\n"
        "  [cyan]devassist config mcp add github --token YOUR_TOKEN[/cyan]\n\n"
        "Put the token in ~/.devassist/env as GITHUB_PERSONAL_ACCESS_TOKEN, or export\n"
        "  GITHUB_PERSONAL_ACCESS_TOKEN, GITHUB_TOKEN, or GH_TOKEN when using -s github.",
        "No Servers Available",
    ),
}


def ensure_setup_complete() -> None:
    """Load ``~/.devassist/env`` and exit if the setup wizard has not been completed."""
    from devassist.cli.setup import check_and_prompt_setup
    from devassist.core.env_store import load_devassist_env_into_os

    load_devassist_env_into_os(prefer_file=True)
    if not check_and_prompt_setup():
        raise typer.Exit(1)


def build_llm_client(
    provider: str,
    *,
    config_manager: ConfigManager | None = None,
) -> AnthropicLLMClient | VertexAILLMClient:
    """Create the LLM client for the given provider name."""
    if provider == "anthropic":
        return AnthropicLLMClient()
    cm = config_manager or ConfigManager()
    ai_config = cm.get_ai_config()
    return VertexAILLMClient(
        project_id=ai_config.get("project_id"),
        location=ai_config.get("location", "us-central1"),
    )


def _apply_yaml_mcp_overrides(registry: MCPRegistry, config_manager: ConfigManager) -> None:
    mcp_config = config_manager.get_mcp_config()
    if not mcp_config:
        return
    for name, server_config in mcp_config.items():
        registry.configure_server(name, server_config.get("env", {}))


def prepare_orchestration_agent(
    provider: str,
    servers: str | None,
    verbose: bool,
    *,
    no_servers_mode: Literal["chat", "ask"],
    console: Console,
) -> tuple[OrchestrationAgent, MCPClient, list[MCPServerConfig]] | None:
    """Build MCP client, registry, and agent. Print diagnostics and return ``None`` on failure."""
    config_manager = ConfigManager()
    llm_client = build_llm_client(provider, config_manager=config_manager)

    mcp_client = MCPClient()
    registry = MCPRegistry()
    _apply_yaml_mcp_overrides(registry, config_manager)

    if servers:
        server_names = [s.strip() for s in servers.split(",")]
    else:
        server_names = [s.name for s in registry.list_configured()]

    if not server_names:
        body, title = _NO_SERVERS_PANELS[no_servers_mode]
        console.print(Panel(body, title=title))
        return None

    server_configs: list[MCPServerConfig] = []
    for name in server_names:
        cfg = registry.get(name)
        if cfg and cfg.is_configured():
            server_configs.append(cfg)
        elif verbose:
            console.print(f"[yellow]Skipping {name}: not configured[/yellow]")

    if not server_configs:
        console.print("[red]No configured MCP servers available.[/red]")
        return None

    agent = OrchestrationAgent(
        llm_client=llm_client,
        mcp_client=mcp_client,
        registry=registry,
    )
    return agent, mcp_client, server_configs


def print_mcp_connection_error(console: Console, exc: BaseException, verbose: bool) -> None:
    """Print connection failure with ExceptionGroup-safe detail."""
    detail = format_user_facing_error(exc)
    console.print(f"[red]Failed to connect to MCP servers:[/red]\n{detail}")
    if verbose:
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
