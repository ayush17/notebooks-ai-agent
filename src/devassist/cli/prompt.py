"""Custom prompt CLI commands for DevAssist.

Provides commands to generate briefs with completely custom prompts
that override the default brief structure.
"""

import asyncio
import json
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from devassist.ai.claude_client import ClaudeClient
from devassist.core.brief_generator import BriefGenerator
from devassist.models.config import ClientConfig
from devassist.models.context import SourceType

# Create router for prompt commands
app = typer.Typer(
    name="prompt",
    help="Generate custom AI responses with your own prompts.",
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


def display_response_markdown(response: str, session_id: str | None = None) -> None:
    """Display response in markdown format.

    Args:
        response: Claude's markdown response.
        session_id: Session ID if available.
    """
    console.print()
    header = "[bold]Custom Prompt Response[/bold]"
    if session_id:
        header += f"\n[dim]Session: {session_id}[/dim]"

    console.print(Panel(header, border_style="green"))

    # Render markdown
    console.print()
    console.print(Markdown(response))
    console.print()

    if session_id:
        console.print(
            f"[dim]Tip: Continue this conversation with --session-id {session_id} or --resume[/dim]\n"
        )


def display_response_json(response: str, session_id: str | None = None) -> None:
    """Display response as JSON.

    Args:
        response: Claude's response.
        session_id: Session ID if available.
    """
    output = {
        "response": response,
        "session_id": session_id,
        "generated_at": asyncio.get_event_loop().time(),
    }

    console.print_json(json.dumps(output, indent=2))


@app.callback(invoke_without_command=True)
def ask(
    ctx: typer.Context,
    prompt: str = typer.Argument(..., help="Your custom prompt/question."),
    sources: Optional[str] = typer.Option(
        None,
        "--sources",
        "-s",
        help="Comma-separated list of sources (gmail,slack,jira,github). Default: all configured.",
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
) -> None:
    """Ask Claude a custom question with access to your developer context.

    This command sends your custom prompt directly to Claude with access to
    your configured MCP servers (Gmail, Slack, JIRA, GitHub, etc.).

    Unlike 'brief', this completely replaces the default morning brief prompt
    with your custom prompt.

    Examples:
      devassist prompt "What PRs need my review?"
      devassist prompt "Summarize my emails from last week" --sources gmail
      devassist prompt "What's blocking the frontend team?" --resume
    """
    if ctx.invoked_subcommand is not None:
        return

    # Parse sources
    source_filter = parse_sources(sources)

    # Show progress
    if not json_output:
        console.print(f"[dim]Asking Claude: '{prompt[:50]}{'...' if len(prompt) > 50 else ''}'[/dim]")

    try:
        # Initialize with unified config
        config = ClientConfig()
        client = ClaudeClient(config)

        # Determine session handling
        target_session_id = None

        if session_id:
            # Use specific session
            target_session_id = session_id
        elif resume:
            # Resume latest session
            latest = ClaudeClient.get_latest_session()
            if latest:
                target_session_id = latest.session_id
                if not json_output:
                    console.print(f"[dim]Resuming session: {target_session_id}[/dim]")

        # Make the call to Claude with custom prompt
        # Note: We bypass BriefGenerator entirely and call ClaudeClient directly
        # This gives us full control over the prompt without any brief structure
        response = asyncio.run(
            client.make_call(
                user_prompt=prompt,
                session_id=target_session_id
            )
        )

        # Get session ID from the response metadata
        latest_session = client.get_latest_session()
        if latest_session:
            target_session_id = latest_session.session_id

        # Display result
        if json_output:
            display_response_json(response, target_session_id)
        else:
            display_response_markdown(response, target_session_id)

    except Exception as e:
        if json_output:
            console.print_json(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error processing prompt:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def examples() -> None:
    """Show example prompts you can use."""
    examples_text = """
# DevAssist Custom Prompt Examples

## Development & Code Review
```bash
devassist prompt "What PRs are waiting for my review?"
devassist prompt "Show me any build failures or CI issues"
devassist prompt "What's the status of feature branches?"
```

## Project Management
```bash
devassist prompt "What are my blocked tasks in JIRA?"
devassist prompt "Show me all high-priority issues assigned to me"
devassist prompt "What deadlines are coming up this week?"
```

## Communication
```bash
devassist prompt "Summarize important emails from yesterday"
devassist prompt "What meetings do I have today?"
devassist prompt "Are there any urgent Slack messages I missed?"
```

## Team Coordination
```bash
devassist prompt "What's the frontend team working on?"
devassist prompt "Are there any security issues that need attention?"
devassist prompt "What decisions are waiting for my input?"
```

## Research & Analysis
```bash
devassist prompt "How is the performance of our main API endpoints?"
devassist prompt "What are the common issues in recent bug reports?"
devassist prompt "Give me a technical summary of project X progress"
```

## Session Management
```bash
devassist prompt "What did we discuss last time?" --resume
devassist prompt "Follow up on the deployment question" --session-id abc123
```

## Source-Specific Queries
```bash
devassist prompt "What's in my Gmail today?" --sources gmail
devassist prompt "JIRA status update" --sources jira
devassist prompt "GitHub activity summary" --sources github
```
    """

    console.print(Markdown(examples_text))