"""Brief CLI commands for DevAssist.

Provides commands to generate and view the Unified Morning Brief.
"""

import asyncio
import json
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from devassist.core.brief_generator import BriefGenerator
from devassist.models.brief import Brief
from devassist.models.context import SourceType

# Create router for brief commands
app = typer.Typer(
    name="brief",
    help="Generate and view your morning brief.",
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


def display_brief(brief: Brief) -> None:
    """Display brief with Rich formatting.

    Args:
        brief: Brief to display.
    """
    # Header
    console.print()
    console.print(
        Panel(
            f"[bold]Unified Morning Brief[/bold]\n"
            f"[dim]Generated at {brief.generated_at.strftime('%Y-%m-%d %H:%M')}[/dim]",
            border_style="blue",
        )
    )

    # Summary
    console.print("\n[bold cyan]Summary[/bold cyan]")
    console.print(Markdown(brief.summary))

    # Show any failed sources
    if brief.has_errors:
        console.print(
            f"\n[yellow]Warning:[/yellow] Some sources failed: {', '.join(brief.sources_failed)}"
        )

    # Sections by source
    for section in brief.sections:
        if not section.has_items:
            continue

        console.print(f"\n[bold green]{section.display_name}[/bold green] ({section.item_count} items)")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Title", style="white", no_wrap=False, max_width=50)
        table.add_column("From", style="cyan", max_width=20)
        table.add_column("Time", style="dim", max_width=12)
        table.add_column("Score", style="yellow", max_width=6)

        for item in section.items[:10]:  # Show top 10 per section
            time_str = item.timestamp.strftime("%H:%M")
            score_str = f"{item.relevance_score:.2f}"
            author = item.author[:18] + ".." if item.author and len(item.author) > 20 else (item.author or "-")

            table.add_row(
                item.title[:48] + ".." if len(item.title) > 50 else item.title,
                author,
                time_str,
                score_str,
            )

        console.print(table)

        # Show more indicator
        if section.item_count > 10:
            console.print(f"  [dim]... and {section.item_count - 10} more items[/dim]")

    # Footer
    console.print(f"\n[dim]Total items processed: {brief.total_items}[/dim]\n")


def display_brief_json(brief: Brief) -> None:
    """Display brief as JSON.

    Args:
        brief: Brief to display.
    """
    output = {
        "summary": brief.summary,
        "generated_at": brief.generated_at.isoformat(),
        "total_items": brief.total_items,
        "sources_queried": [s.value for s in brief.sources_queried],
        "sources_failed": brief.sources_failed,
        "sections": [
            {
                "source": section.source_type.value,
                "display_name": section.display_name,
                "item_count": section.item_count,
                "items": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "author": item.author,
                        "timestamp": item.timestamp.isoformat(),
                        "relevance_score": item.relevance_score,
                        "url": item.url,
                    }
                    for item in section.items
                ],
            }
            for section in brief.sections
        ],
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
        help="Bypass cache and fetch fresh data.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON for machine processing.",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="Summarization backend: anthropic (Claude) or gemini (Vertex AI). "
        "Default: config ai.provider or anthropic.",
    ),
) -> None:
    """Generate your Unified Morning Brief.

    Fetches context from configured sources, ranks by relevance,
    and generates an AI-powered summary of what you need to know today.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Parse sources
    source_filter = parse_sources(sources)

    # Show progress
    if not json_output:
        console.print("[dim]Generating your morning brief...[/dim]")

    try:
        # Generate brief
        generator = BriefGenerator(ai_provider_override=provider)
        brief = asyncio.run(generator.generate(sources=source_filter, refresh=refresh))

        # Display result
        if json_output:
            display_brief_json(brief)
        else:
            display_brief(brief)

    except Exception as e:
        if json_output:
            console.print_json(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error generating brief:[/red] {e}")
        raise typer.Exit(1)
