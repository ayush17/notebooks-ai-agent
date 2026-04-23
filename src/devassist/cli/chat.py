"""Chat command for DevAssist CLI.

Provides an interactive REPL interface for continuous conversation with the assistant.
"""

import asyncio
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.table import Table

from devassist.cli.mcp_prepare import (
    ensure_setup_complete,
    prepare_orchestration_agent,
    print_mcp_connection_error,
)
from devassist.orchestrator.native_jira_tools import build_jira_native_tool_schemas

console = Console()

HELP_TEXT = """
[bold]Available Commands:[/bold]
  /help     - Show this help message
  /servers  - List connected MCP servers
  /tools    - List available tools
  /clear    - Clear conversation history
  /quit     - Exit the chat session
  /exit     - Exit the chat session

[bold]Examples:[/bold]
  What are my open Jira issues?
  Show me GitHub PRs that need my review
  Give me a morning brief
  What did I work on last week?
"""


def chat(
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            "-p",
            help="LLM provider to use (vertex for Gemini, anthropic for Claude)",
        ),
    ] = "anthropic",
    servers: Annotated[
        str | None,
        typer.Option(
            "--servers",
            "-s",
            help="Comma-separated MCP servers (github,atlassian,filesystem). Jira REST tools appear when Jira API token env is set.",
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
    """Start an interactive chat session with the assistant.

    Connect to MCP servers and engage in a continuous conversation.
    The assistant maintains context across turns and can access
    GitHub, Atlassian (Jira/Confluence), and other configured services.

    Examples:
        devassist chat
        devassist chat -s github,atlassian
        devassist chat -p vertex -v
    """
    ensure_setup_complete()
    asyncio.run(_chat_loop(provider, servers, verbose))


async def _chat_loop(
    provider: str,
    servers: str | None,
    verbose: bool,
) -> None:
    """Async implementation of the chat REPL loop."""
    prepared = prepare_orchestration_agent(
        provider,
        servers,
        verbose,
        no_servers_mode="chat",
        console=console,
    )
    if prepared is None:
        return
    agent, mcp_client, server_configs = prepared

    # Connect to MCP servers
    console.print()
    console.print(Panel.fit(
        "[bold blue]DevAssist Interactive Chat[/bold blue]\n"
        "[dim]Type /help for commands, /quit to exit[/dim]",
        border_style="blue",
    ))
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Connecting to MCP servers...", total=None)

        try:
            async with mcp_client.connect_all(server_configs):
                progress.stop()

                # Show connected servers
                connected_servers = [c.name for c in server_configs]
                console.print(f"[green]Connected to:[/green] {', '.join(connected_servers)}")

                if verbose:
                    tools = build_jira_native_tool_schemas() + mcp_client.get_all_tools()
                    console.print(f"[dim]Available tools: {len(tools)}[/dim]")

                console.print()

                # Conversation history for context
                conversation_history: list[dict] = []

                # Main REPL loop
                while True:
                    try:
                        user_input = console.input("[bold green]You>[/bold green] ").strip()
                    except (EOFError, KeyboardInterrupt):
                        console.print("\n[dim]Goodbye![/dim]")
                        break

                    if not user_input:
                        continue

                    # Handle commands
                    if user_input.startswith("/"):
                        command = user_input.lower()

                        if command in ["/quit", "/exit", "/q"]:
                            console.print("[dim]Goodbye![/dim]")
                            break

                        elif command == "/help":
                            console.print(Panel(HELP_TEXT, title="Help", border_style="cyan"))
                            continue

                        elif command == "/servers":
                            table = Table(title="Connected MCP Servers")
                            table.add_column("Name", style="cyan")
                            table.add_column("Description", style="dim")
                            for config in server_configs:
                                table.add_row(config.name, config.description)
                            console.print(table)
                            continue

                        elif command == "/tools":
                            tools = build_jira_native_tool_schemas() + mcp_client.get_all_tools()
                            table = Table(title="Available Tools")
                            table.add_column("Tool", style="cyan")
                            table.add_column("Description", style="dim", max_width=60)
                            for tool in tools:
                                desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
                                table.add_row(tool.name, desc)
                            console.print(table)
                            continue

                        elif command == "/clear":
                            conversation_history.clear()
                            console.print("[dim]Conversation history cleared.[/dim]")
                            continue

                        else:
                            console.print(f"[yellow]Unknown command: {user_input}[/yellow]")
                            console.print("[dim]Type /help for available commands[/dim]")
                            continue

                    # Process user message
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console,
                        transient=True,
                    ) as inner_progress:
                        inner_progress.add_task("Thinking...", total=None)

                        try:
                            # Add context from conversation history
                            context_prompt = user_input
                            if conversation_history:
                                history_text = "\n".join([
                                    f"User: {h['user']}\nAssistant: {h['assistant']}"
                                    for h in conversation_history[-3:]  # Keep last 3 turns for context
                                ])
                                context_prompt = f"Previous conversation:\n{history_text}\n\nCurrent question: {user_input}"

                            response = await agent.process(context_prompt)

                            # Store in history
                            conversation_history.append({
                                "user": user_input,
                                "assistant": response.content[:500]  # Truncate for context
                            })

                        except Exception as e:
                            console.print(f"[red]Error: {e}[/red]")
                            if verbose:
                                import traceback
                                console.print(f"[dim]{traceback.format_exc()}[/dim]")
                            continue

                    # Display response
                    console.print()
                    if response.error:
                        console.print(f"[yellow]Warning: {response.error}[/yellow]")

                    console.print(Panel(
                        Markdown(response.content),
                        title="[bold blue]Assistant[/bold blue]",
                        border_style="blue",
                    ))

                    if verbose:
                        console.print(f"[dim]Sources: {', '.join(response.sources_used) or 'none'} | Tool calls: {response.tool_calls_made}[/dim]")

                    console.print()

        except Exception as e:
            print_mcp_connection_error(console, e, verbose)
            return
