"""Main CLI entry point for DevAssist.

Provides the primary Typer application and core commands.
"""

from typing import Optional

import typer
from rich.console import Console

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
    from devassist.core.env_store import load_devassist_env_into_os

    # Canonical credentials: ~/.devassist/env (legacy ~/.devassist/.env merged in).
    load_devassist_env_into_os(prefer_file=True)


@app.command()
def status() -> None:
    """Show current configuration status."""
    from devassist.core.config_manager import ConfigManager
    from devassist.core.env_store import get_env_file_path

    manager = ConfigManager()
    cfg = manager.load_config()
    sources = manager.list_sources()

    console.print(f"\n[bold]DevAssist v{__version__}[/bold]\n")
    console.print(f"Workspace: {manager.workspace_dir}")
    console.print(f"Env file: {get_env_file_path()}")
    console.print(f"Config: {manager.config_path}")
    console.print(f"Brief AI: provider {cfg.ai.provider}")

    if sources:
        console.print(f"\nConfigured sources: {', '.join(sources)}")
    else:
        console.print("\n[dim]No sources configured yet.[/dim]")
        console.print("Run [bold]devassist config add <source>[/bold] to get started.\n")


# Import and register sub-commands
from devassist.cli.brief import app as brief_app
from devassist.cli.config import app as config_app
from devassist.cli.ask import ask as ask_command
from devassist.cli.chat import chat as chat_command
from devassist.cli.setup import app as setup_app

# Register subcommands
app.add_typer(config_app, name="config")
app.add_typer(brief_app, name="brief")
app.add_typer(setup_app, name="setup", help="Configure DevAssist connections")
app.command(name="ask")(ask_command)
app.command(name="chat")(chat_command)


if __name__ == "__main__":
    app()
