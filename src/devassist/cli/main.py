"""Main CLI entry point for DevAssist.

Provides the primary Typer application and core commands.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from devassist import __version__

# Create main Typer app
app = typer.Typer(
    name="devassist",
    help="Developer Assistant CLI - Your AI-powered morning brief.",
    add_completion=False,
    no_args_is_help=True,
)

# Rich console for formatted output
console = Console()


def show_security_warning() -> None:
    """Display security warning about credential storage.

    Per FR-004: Show security warning on startup for dev mode.
    """
    warning_text = Text()
    warning_text.append("DEV MODE: ", style="bold yellow")
    warning_text.append(
        "Credentials are stored in plain text at ~/.devassist/config.yaml. "
        "Do not use in production without proper secret management."
    )
    console.print(Panel(warning_text, title="Security Notice", border_style="yellow"))


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"devassist version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """DevAssist - Developer Assistant CLI.

    An AI-powered CLI that aggregates context from multiple developer tools
    (Gmail, Slack, JIRA, GitHub) and generates a Unified Morning Brief.
    """
    # Security warning is shown contextually by commands that handle credentials
    pass


@app.command()
def status() -> None:
    """Show current configuration status."""
    from devassist.models.config import ClientConfig

    # Load config from CLI args and files
    config = ClientConfig()

    console.print(f"\n[bold]DevAssist v{__version__}[/bold]\n")
    console.print(f"Workspace: {config.workspace_dir}")
    console.print(f"Config: {config.workspace_dir / 'config.yaml'}")

    enabled_sources = config.enabled_sources
    if enabled_sources:
        sources_str = ", ".join([source.value for source in enabled_sources])
        console.print(f"\nEnabled sources: {sources_str}")
        console.print(f"AI Model: [cyan]{config.ai_model}[/cyan]")
    else:
        console.print("\n[dim]No sources enabled yet.[/dim]")
        console.print("Configure sources through [bold]config.yaml[/bold] or environment variables.\n")


# Import and register sub-commands
from devassist.cli.ai import app as ai_app
from devassist.cli.brief import app as brief_app
from devassist.cli.prompt import app as prompt_app

# Register subcommands
app.add_typer(ai_app, name="ai")
app.add_typer(brief_app, name="brief")
app.add_typer(prompt_app, name="prompt")


if __name__ == "__main__":
    app()
