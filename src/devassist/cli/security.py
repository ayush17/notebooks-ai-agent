"""Security notices shared across CLI commands."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def show_security_warning(console: Console | None = None) -> None:
    """Display security warning about credential storage (FR-004 dev mode)."""
    from devassist.core.env_store import get_env_file_path, get_legacy_env_file_path

    c = console or Console()
    env_path = get_env_file_path()
    legacy_path = get_legacy_env_file_path()
    warning_text = Text()
    warning_text.append("DEV MODE: ", style="bold yellow")
    warning_text.append(
        f"Credentials are stored in plain text under {env_path.parent} ({env_path.name}; "
        f"a copy is kept at {legacy_path.name}). "
        "Do not use in production without proper secret management."
    )
    c.print(Panel(warning_text, title="Security Notice", border_style="yellow"))
