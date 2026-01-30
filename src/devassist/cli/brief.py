"""Brief CLI commands for DevAssist (refactored for Claude Agent SDK).

Provides commands to generate and view the Unified Morning Brief using Claude.
"""

import asyncio
import json
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from devassist.ai.claude_client import ClaudeClient
from devassist.core.brief_generator import BriefGenerator
from devassist.models.config import ClientConfig
from devassist.models.context import SourceType

# Create router for brief commands
app = typer.Typer(
    name="brief",
    help="Generate and view your morning brief using Claude.",
)

console = Console()


def parse_sources(sources_str: str | None) -> list[SourceType] | None:
    """Parse comma-separated source string into list.

    Args:
        sources_str: Comma-separated source names.

    Returns:
        List of SourceType or None if all sources.
    """
    if not sources_str:
        return None

    sources = []
    for name in sources_str.split(","):
        name = name.strip().lower()
        try:
            sources.append(SourceType(name))
        except ValueError:
            console.print(f"[yellow]Warning:[/yellow] Unknown source '{name}', skipping.")

    return sources if sources else None


def display_brief_markdown(response: str, session_id: str | None = None) -> None:
    """Display brief in markdown format.

    Args:
        response: Claude's markdown response.
        session_id: Session ID if available.
    """
    console.print()
    header = "[bold]Unified Morning Brief[/bold]"
    if session_id:
        header += f"\n[dim]Session: {session_id}[/dim]"

    console.print(Panel(header, border_style="blue"))

    # Render markdown
    console.print()
    console.print(Markdown(response))
    console.print()

    if session_id:
        console.print(
            f"[dim]Tip: Resume this session with --session-id {session_id} or --resume[/dim]\n"
        )


def display_brief_json(response: str, session_id: str | None = None) -> None:
    """Display brief as JSON.

    Args:
        response: Claude's response.
        session_id: Session ID if available.
    """
    from datetime import datetime

    output = {
        "response": response,
        "session_id": session_id,
        "generated_at": datetime.now().isoformat(),
    }

    console.print_json(json.dumps(output, indent=2))


@app.callback(invoke_without_command=True)
def generate_brief(
    ctx: typer.Context,
    sources: Optional[str] = typer.Option(
        None,
        "--sources",
        "-s",
        help="Comma-separated list of sources (gmail,slack,jira,github). Default: all configured.",
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        "-r",
        help="Start a new session instead of resuming.",
    ),
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        help="Resume a specific session by ID.",
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        help="Resume the most recent session.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON for machine processing.",
    ),
    prompt: Optional[str] = typer.Option(
        None,
        "--prompt",
        "-p",
        help="Custom prompt or follow-up question.",
    ),
) -> None:
    """Generate your Unified Morning Brief using Claude.

    Fetches context from configured MCP servers and uses Claude to
    generate an AI-powered summary of what you need to know today.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Parse sources
    source_filter = parse_sources(sources)

    # Show progress
    if not json_output:
        console.print("[dim]Generating your morning brief with Claude...[/dim]")

    try:
        # Initialize with unified config and self-contained components
        config = ClientConfig()
        generator = BriefGenerator(config=config)

        # Determine session handling
        target_session_id = None

        if session_id:
            # Use specific session
            target_session_id = session_id
        elif resume and not refresh:
            # Resume latest session from ClaudeClient
            latest = ClaudeClient.get_latest_session()

            if latest:
                target_session_id = latest.session_id
                if not json_output:
                    console.print(f"[dim]Resuming session: {target_session_id}[/dim]")

        # Handle follow-up vs new brief with custom prompt
        if prompt and target_session_id:
            # Follow-up question on existing session
            response = asyncio.run(
                generator.resume_brief_session(target_session_id, prompt)
            )
        else:
            # Generate new brief (with optional custom prompt)
            brief = asyncio.run(
                generator.generate(
                    sources=source_filter,
                    refresh=refresh,
                    user_prompt=prompt,  # Pass custom prompt if provided
                    session_id=target_session_id,
                )
            )
            response = brief.summary
            target_session_id = brief.metadata.get("session_id")

        # Display result
        if json_output:
            display_brief_json(response, target_session_id)
        else:
            display_brief_markdown(response, target_session_id)

    except Exception as e:
        if json_output:
            console.print_json(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error generating brief:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def sessions(
    limit: int = typer.Option(
        10,
        "--limit",
        "-n",
        help="Number of sessions to list.",
    ),
) -> None:
    """List recent brief sessions."""
    generator = BriefGenerator()
    sessions_list = generator.list_recent_sessions(limit=limit)

    if not sessions_list:
        console.print("[dim]No sessions found.[/dim]")
        return

    # Create table
    table = Table(title="Recent Brief Sessions", show_header=True, header_style="bold")
    table.add_column("Session ID", style="cyan")
    table.add_column("Created", style="white")
    table.add_column("Last Used", style="white")
    table.add_column("Resources", style="green")
    table.add_column("Turns", style="yellow")

    for session in sessions_list:
        from datetime import datetime

        created = datetime.fromisoformat(session["created_at"])
        last_used = datetime.fromisoformat(session["last_used"])

        table.add_row(
            session["session_id"][:16] + "...",
            created.strftime("%Y-%m-%d %H:%M"),
            last_used.strftime("%Y-%m-%d %H:%M"),
            ", ".join(session["resources"]),
            str(session["turns"]),
        )

    console.print(table)


@app.command()
def clear(
    session_id: str = typer.Argument(..., help="Session ID to clear."),
) -> None:
    """Clear a specific session."""
    # Check if session exists
    session = ClaudeClient.get_session_by_id(session_id)
    if not session:
        console.print(f"[red]Session {session_id} not found.[/red]")
        raise typer.Exit(1)

    # Create temporary client to clear session
    config = ClientConfig()
    client = ClaudeClient(config)
    client.clear_session(session_id)

    console.print(f"[green]Session {session_id} cleared.[/green]")


@app.command()
def clean(
    days: int = typer.Option(
        30,
        "--days",
        "-d",
        help="Delete sessions older than this many days.",
    ),
) -> None:
    """Clean up old sessions."""
    from datetime import datetime, timedelta

    # Get all sessions and find expired ones
    all_sessions = ClaudeClient._session_store.values() if ClaudeClient._session_store else []
    cutoff_date = datetime.now() - timedelta(days=days)

    expired_sessions = [
        s for s in all_sessions
        if s.last_used < cutoff_date
    ]

    # Delete expired sessions
    config = ClientConfig()
    client = ClaudeClient(config)
    deleted_count = 0

    for session in expired_sessions:
        client.clear_session(session.session_id)
        deleted_count += 1

    console.print(f"[green]Deleted {deleted_count} expired sessions.[/green]")
