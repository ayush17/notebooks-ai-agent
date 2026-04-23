"""Interactive setup command for DevAssist.

Guides new users through configuring MCP connections and syncs ``~/.devassist/config.yaml``.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from devassist.core.config_manager import ConfigManager
from devassist.core.env_store import (
    get_env_file_path,
    load_devassist_env_into_os,
    read_devassist_env_dict,
    write_devassist_env_from_dict,
)
from devassist.models.config import sanitize_gcp_field

console = Console()
app = typer.Typer(help="Setup and configure DevAssist.")

load_existing_config = read_devassist_env_dict
save_config = write_devassist_env_from_dict


def _configure_claude_vertex(config: dict[str, str]) -> None:
    console.print("\n[bold cyan]1. Claude AI (Vertex AI)[/bold cyan]")
    console.print("   Configure GCP project for Claude on Vertex.\n")
    config["CLAUDE_CODE_USE_VERTEX"] = "1"
    config["CLOUD_ML_REGION"] = "us-east5"
    current_project = config.get("ANTHROPIC_VERTEX_PROJECT_ID", "")
    project_id = Prompt.ask(
        "   Enter your GCP Project ID",
        default=current_project or "itpc-gcp-ai-eng-claude",
    )
    config["ANTHROPIC_VERTEX_PROJECT_ID"] = sanitize_gcp_field(project_id)
    console.print("   [green]✓[/green] Claude AI configured via Vertex AI")
    console.print("   [dim]Note: Run 'gcloud auth application-default login' if not already done.[/dim]")


def _configure_claude_direct(config: dict[str, str]) -> None:
    console.print("\n[bold cyan]1. Claude AI (Anthropic API)[/bold cyan]\n")
    api_key = Prompt.ask(
        "   Enter your Anthropic API key",
        password=True,
        default=config.get("ANTHROPIC_API_KEY", ""),
    )
    if api_key:
        config["ANTHROPIC_API_KEY"] = api_key
        config["CLAUDE_CODE_USE_VERTEX"] = "0"
        console.print("   [green]✓[/green] Claude AI configured via direct API")


def _configure_github(config: dict[str, str]) -> None:
    console.print("\n[bold cyan]2. GitHub Configuration[/bold cyan]")
    console.print("   Create a token at: https://github.com/settings/tokens")
    console.print("   Required scopes: repo, notifications, read:user\n")
    current_github = config.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
    if current_github:
        console.print(f"   [dim]Current token: {current_github[:10]}...{current_github[-4:]}[/dim]")
    if not Confirm.ask("   Configure GitHub?", default=True):
        return
    github_token = Prompt.ask(
        "   Enter your GitHub Personal Access Token",
        password=True,
        default="",
    )
    if github_token:
        config["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token
        console.print("   [green]✓[/green] GitHub configured")
    elif current_github:
        console.print("   [green]✓[/green] Keeping existing GitHub token")


def _configure_jira(config: dict[str, str]) -> None:
    console.print("\n[bold cyan]3. Atlassian Jira (REST API)[/bold cyan]")
    console.print(
        "   Uses your Atlassian account email and an API token (no browser login).\n"
        "   Create a token: https://id.atlassian.com/manage-profile/security/api-tokens\n"
    )
    current_base = config.get("ATLASSIAN_BASE_URL", "")
    current_email = config.get("ATLASSIAN_EMAIL", "")
    if not Confirm.ask("   Configure Jira (API token + email)?", default=True):
        return
    base_url = Prompt.ask(
        "   Jira site base URL (e.g. https://yourcompany.atlassian.net)",
        default=current_base or "https://yourcompany.atlassian.net",
    ).rstrip("/")
    email = Prompt.ask("   Atlassian account email", default=current_email or "")
    api_token = Prompt.ask(
        "   Jira API token (leave blank to keep existing)",
        password=True,
        default="",
    )
    if not api_token.strip():
        api_token = config.get("ATLASSIAN_API_TOKEN", "")
    if base_url and email and api_token:
        config["ATLASSIAN_BASE_URL"] = base_url
        config["ATLASSIAN_EMAIL"] = email
        config["ATLASSIAN_API_TOKEN"] = api_token
        config["ATLASSIAN_SITE_URL"] = base_url + "/"
        console.print("   [green]✓[/green] Jira configured (email + API token)")
    elif current_base and current_email and config.get("ATLASSIAN_API_TOKEN"):
        console.print("   [green]✓[/green] Keeping existing Jira API credentials")
    else:
        console.print("   [yellow]Skipped: need base URL, email, and API token to save Jira config.[/yellow]")


@app.command()
def init():
    """Interactive setup: write ``~/.devassist/env``, mirror ``.env``, sync ``config.yaml``."""
    console.print(
        Panel.fit(
            "[bold blue]🚀 DevAssist Setup Wizard[/bold blue]\n\n"
            "This will help you configure DevAssist to connect to your developer tools.",
            border_style="blue",
        )
    )
    config = load_existing_config()

    console.print("\n[bold cyan]Claude AI[/bold cyan]")
    if Confirm.ask("   Use Claude via Vertex AI (GCP)?", default=True):
        _configure_claude_vertex(config)
    else:
        _configure_claude_direct(config)

    _configure_github(config)
    _configure_jira(config)

    console.print("\n[bold cyan]Saving configuration...[/bold cyan]")
    save_config(config)
    load_devassist_env_into_os(prefer_file=True)

    cm = ConfigManager()
    cm.sync_ai_yaml_from_env_store()

    env_file = get_env_file_path()
    console.print(f"   [green]✓[/green] Environment file: {env_file}")
    console.print(f"   [green]✓[/green] YAML config: {cm.config_path}")

    env_hint = (
        "The DevAssist CLI loads the env file on every run (it overrides conflicting shell "
        f"variables). Optional: [cyan]source {env_file}[/cyan] for other tools in the same shell."
    )
    console.print(
        Panel.fit(
            "[bold green]Setup Complete![/bold green]\n\n"
            f"{env_hint}\n\n"
            "Try:\n"
            '  [cyan]devassist ask "Give me a morning brief" -s atlassian,github[/cyan]\n'
            "Or:\n"
            "  [cyan]devassist chat -s atlassian,github[/cyan]",
            border_style="green",
        )
    )


@app.command()
def status():
    """Show credential and YAML configuration status."""
    env_data = load_existing_config()
    cm = ConfigManager()
    app_cfg = cm.load_config()

    console.print(Panel.fit("[bold blue]DevAssist Configuration Status[/bold blue]", border_style="blue"))

    checks = [
        ("Claude AI (Vertex)", env_data.get("CLAUDE_CODE_USE_VERTEX") == "1" and env_data.get("ANTHROPIC_VERTEX_PROJECT_ID")),
        ("Claude AI (Direct)", env_data.get("ANTHROPIC_API_KEY")),
        ("GitHub", env_data.get("GITHUB_PERSONAL_ACCESS_TOKEN")),
        (
            "Atlassian",
            env_data.get("ATLASSIAN_BASE_URL") and env_data.get("ATLASSIAN_EMAIL") and env_data.get("ATLASSIAN_API_TOKEN"),
        ),
    ]
    for name, configured in checks:
        line = "[green]✓ Configured[/green]" if configured else "[red]✗ Not configured[/red]"
        console.print(f"  {name}: {line}")

    console.print("\n  [bold]Paths[/bold]")
    console.print(f"  Env:   {get_env_file_path()}")
    console.print(f"  YAML:  {cm.config_path}")
    console.print(
        f"  Brief AI: provider [cyan]{app_cfg.ai.provider}[/cyan]"
        + (f", model [cyan]{app_cfg.ai.model}[/cyan]" if app_cfg.ai.provider == "gemini" else "")
    )

    if not any(c[1] for c in checks):
        console.print("\n  [yellow]Run 'devassist setup init' to configure.[/yellow]")


def check_and_prompt_setup() -> bool:
    """Return True if minimum credentials exist; otherwise print setup hint."""
    config = load_existing_config()
    has_claude = (
        (config.get("CLAUDE_CODE_USE_VERTEX") == "1" and config.get("ANTHROPIC_VERTEX_PROJECT_ID"))
        or config.get("ANTHROPIC_API_KEY")
    )
    has_source = config.get("GITHUB_PERSONAL_ACCESS_TOKEN") or (
        config.get("ATLASSIAN_BASE_URL") and config.get("ATLASSIAN_EMAIL") and config.get("ATLASSIAN_API_TOKEN")
    )
    if has_claude and has_source:
        return True
    console.print(
        Panel.fit(
            "[yellow]⚠️  DevAssist is not configured yet.[/yellow]\n\n"
            "Run the setup wizard to configure your connections:\n"
            "  [cyan]devassist setup init[/cyan]",
            border_style="yellow",
        )
    )
    return False
