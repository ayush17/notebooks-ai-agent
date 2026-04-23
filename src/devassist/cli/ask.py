"""Ask command for DevAssist CLI.

Provides natural language interface to the orchestration agent.
"""

import asyncio
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from devassist.cli.mcp_prepare import (
    ensure_setup_complete,
    prepare_orchestration_agent,
    print_mcp_connection_error,
)
from devassist.orchestrator.native_jira_tools import build_jira_native_tool_schemas

console = Console()


def ask(
    prompt: Annotated[
        str,
        typer.Argument(help="Your question or request in natural language"),
    ],
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            "-p",
            help="LLM provider to use (vertex for Gemini, anthropic for Claude)",
        ),
    ] = "anthropic",  # Default to Anthropic (Claude), works with both direct API and Vertex AI
    servers: Annotated[
        str | None,
        typer.Option(
            "--servers",
            "-s",
            help="Comma-separated MCP servers (github,atlassian,filesystem). Jira REST tools (no browser) are added when ATLASSIAN_* or JIRA_* token env vars are set.",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show detailed output including tool calls",
        ),
    ] = False,
) -> None:
    """Ask the assistant a question using natural language.

    The assistant will use available MCP tools to gather information
    and provide a helpful response.

    Examples:
        devassist ask "What are my GitHub notifications?"
        devassist ask "What are my open Jira issues?" -s atlassian
        devassist ask "Give me a morning brief" -s github,atlassian
    """
    ensure_setup_complete()
    asyncio.run(_ask_async(prompt, provider, servers, verbose))


async def _ask_async(
    prompt: str,
    provider: str,
    servers: str | None,
    verbose: bool,
) -> None:
    """Async implementation of the ask command."""
    prepared = prepare_orchestration_agent(
        provider,
        servers,
        verbose,
        no_servers_mode="ask",
        console=console,
    )
    if prepared is None:
        return
    agent, mcp_client, server_configs = prepared

    # Connect to MCP servers and process
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Connecting to MCP servers...", total=None)

        try:
            async with mcp_client.connect_all(server_configs):
                progress.update(task, description="Processing your request...")

                # Get available tools for verbose output
                if verbose:
                    tools = build_jira_native_tool_schemas() + mcp_client.get_all_tools()
                    console.print(f"\n[dim]Available tools: {len(tools)}[/dim]")
                    for tool in tools:
                        console.print(f"[dim]  - {tool.name}: {tool.description[:50]}...[/dim]")
                    console.print()

                # Process the prompt
                response = await agent.process(prompt)

        except Exception as e:
            print_mcp_connection_error(console, e, verbose)
            return

    # Display response
    if response.error:
        console.print(f"\n[yellow]Warning: {response.error}[/yellow]\n")

    console.print(Panel(response.content, title="Assistant Response", border_style="green"))

    if verbose:
        console.print(f"\n[dim]Sources used: {', '.join(response.sources_used) or 'none'}[/dim]")
        console.print(f"[dim]Tool calls made: {response.tool_calls_made}[/dim]")
