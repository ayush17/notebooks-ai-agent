"""AI CLI commands for DevAssist.

Provides commands for managing the background AI runner using Claude Agent SDK.
"""

import os
import typer
from rich.console import Console
from rich.table import Table
from datetime import datetime

from devassist.ai.claude_client import ClaudeClient
from devassist.core.runner import Runner
from devassist.core.runner_manager import RunnerManager
from devassist.models.config import ClientConfig

# Create router for AI commands
app = typer.Typer(
    name="ai",
    help="Manage background AI runner using Claude Agent SDK.",
    no_args_is_help=True,
)

console = Console()


def run_background_runner() -> None:
    """Entry point for background runner process.

    This function is called in a separate process and runs the runner loop.
    Reads CLI options from environment variables.
    """
    import asyncio
    import logging

    # Setup logging for background process
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(ClientConfig().workspace_dir / "logs" / "runner.log"),
            logging.StreamHandler(),
        ]
    )

    # Read configuration from environment variables (set by CLI)
    interval_minutes = int(os.environ.get("DEVASSIST_RUNNER_INTERVAL", "5"))
    custom_prompt = os.environ.get("DEVASSIST_RUNNER_PROMPT")
    session_id = os.environ.get("DEVASSIST_RUNNER_SESSION_ID")
    enable_slack = os.environ.get("DEVASSIST_RUNNER_ENABLE_SLACK", "true").lower() == "true"

    # Create configuration and runner
    config = ClientConfig()
    runner = Runner(
        config=config,
        interval_minutes=interval_minutes,
        custom_prompt=custom_prompt,
        session_id=session_id,
        enable_slack=enable_slack,
    )

    # Run the background runner
    asyncio.run(runner.run())


@app.command("test")
def test_connection() -> None:
    """Test connection to Claude AI."""
    try:
        # Create client with current config
        config = ClientConfig()
        client = ClaudeClient(config=config)

        console.print("[blue]Testing Claude Agent SDK connection...[/blue]")
        console.print(f"[green]✓[/green] Claude client initialized successfully")
        console.print(f"   • Model: {config.ai_model}")
        console.print(f"   • Enabled sources: {[s.value for s in config.enabled_sources]}")

    except Exception as e:
        console.print(f"[red]✗ Connection failed:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command("status")
def status() -> None:
    """Show AI runner status."""
    try:
        # Create status table
        table = Table(title="DevAssist AI Background Runner")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        # Get runner status
        runner_manager = RunnerManager()
        runner_status = runner_manager.get_status()

        if runner_status.status == "running":
            table.add_row("Status", "🟢 Running")
            table.add_row("PID", str(runner_status.pid))

            # Get process uptime if possible
            if runner_status.pid:
                try:
                    import psutil
                    process = psutil.Process(runner_status.pid)
                    start_time = datetime.fromtimestamp(process.create_time())
                    uptime = datetime.now() - start_time
                    table.add_row("Uptime", f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m")
                except Exception:
                    table.add_row("Uptime", "Unknown")

            # Show output file
            config = ClientConfig()
            output_file = config.workspace_dir / "runner-output.md"
            table.add_row("Output File", str(output_file))

            if output_file.exists():
                modified_time = datetime.fromtimestamp(output_file.stat().st_mtime)
                table.add_row("Last Output", modified_time.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                table.add_row("Last Output", "No output yet")

        else:
            table.add_row("Status", "🔴 Not Running")

        console.print(table)

        # Show AI configuration
        config = ClientConfig()
        console.print(f"\n[bold]AI Configuration:[/bold]")
        console.print(f"Model: [cyan]{config.ai_model}[/cyan]")
        console.print(f"Enabled sources: {', '.join([s.value for s in config.enabled_sources])}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command("run")
def run(
    interval: int = typer.Option(5, "--interval", "-i", help="Run interval in minutes"),
    prompt: str = typer.Option(
        None,
        "--prompt",
        "-p",
        help="Custom prompt for AI runner",
    ),
    session_id: str = typer.Option(
        None,
        "--session-id",
        "-s",
        help="Session ID to continue conversation",
    ),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground"),
    enable_slack: bool = typer.Option(False, "--enable-slack", help="Enable Slack notifications"),
    slack_name: str = typer.Option(None, "--slack-name", help="Slack user name for notifications"),
) -> None:
    """Start the background AI runner."""
    runner_manager = RunnerManager()

    # Check if already running
    if runner_manager.is_running():
        console.print("[yellow]Runner is already running.[/yellow]")
        console.print("Use [bold]devassist ai status[/bold] to check status or [bold]devassist ai kill[/bold] to stop")
        return

    if foreground:
        # Run in foreground
        console.print(f"[blue]Starting AI runner in foreground (interval: {interval}m, Ctrl+C to stop)[/blue]")
        if session_id:
            console.print(f"[dim]Using session: {session_id}[/dim]")
        try:
            import asyncio
            config = ClientConfig()
            runner = Runner(
                config=config,
                interval_minutes=interval,
                custom_prompt=prompt,
                session_id=session_id,
            )
            asyncio.run(runner.run())
        except KeyboardInterrupt:
            console.print("\n[yellow]Runner stopped by user.[/yellow]")
    else:
        # Start as background process
        try:
            runner_manager.start(interval=interval, prompt=prompt, session_id=session_id)
            status = runner_manager.get_status()
            console.print(f"[green]✓[/green] AI runner started successfully")
            console.print(f"[dim]PID: {status.pid}[/dim]")
            console.print(f"[dim]Interval: {interval} minutes[/dim]")
            if session_id:
                console.print(f"[dim]Session: {session_id}[/dim]")
            if prompt:
                console.print(f"[dim]Custom prompt: {prompt[:50]}{'...' if len(prompt) > 50 else ''}[/dim]")

            # Show output location
            config = ClientConfig()
            output_file = config.workspace_dir / "runner-output.md"
            console.print(f"[dim]Output: {output_file}[/dim]")

        except Exception as e:
            console.print(f"[red]✗ Failed to start runner:[/red] {str(e)}")
            raise typer.Exit(1)


@app.command("kill")
def kill(
    force: bool = typer.Option(False, "--force", help="Force kill the runner"),
) -> None:
    """Stop the background runner."""
    runner_manager = RunnerManager()

    if not runner_manager.is_running():
        console.print("[yellow]Runner is not running[/yellow]")
        return

    console.print("[blue]Stopping runner...[/blue]")

    try:
        success = runner_manager.stop(force=force)
        if success:
            console.print("[green]✓[/green] Runner stopped successfully")
        else:
            console.print("[red]✗[/red] Failed to stop runner")
            if not force:
                console.print("Use [bold]--force[/bold] to force kill")
                raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error stopping runner:[/red] {str(e)}")
        raise typer.Exit(1)
    clear_sessions()


@app.command("logs")
def logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of log lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow logs (like tail -f)"),
) -> None:
    """Show runner logs."""
    config = ClientConfig()
    log_file = config.workspace_dir / "logs" / "runner.log"

    if not log_file.exists():
        console.print("[yellow]No log file found[/yellow]")
        console.print(f"Expected log file: {log_file}")
        return

    if follow:
        # Follow logs (like tail -f)
        console.print(f"[blue]Following logs (Ctrl+C to stop):[/blue] {log_file}")
        import subprocess
        try:
            subprocess.run(["tail", "-f", str(log_file)])
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped following logs[/yellow]")
        except FileNotFoundError:
            console.print("[red]'tail' command not found. Showing last lines instead:[/red]")
            # Fallback to showing last N lines
            try:
                with open(log_file, 'r') as f:
                    lines_content = f.readlines()
                    for line in lines_content[-lines:]:
                        console.print(line.rstrip())
            except Exception as e:
                console.print(f"[red]Error reading log file:[/red] {e}")
    else:
        # Show last N lines
        try:
            with open(log_file, 'r') as f:
                lines_content = f.readlines()
                console.print(f"[blue]Last {lines} lines from {log_file}:[/blue]")
                for line in lines_content[-lines:]:
                    console.print(line.rstrip())
        except Exception as e:
            console.print(f"[red]Error reading log file:[/red] {e}")


@app.command("sessions")
def list_sessions() -> None:
    """List all Claude AI sessions."""
    sessions = ClaudeClient._session_store

    if not sessions:
        console.print("[yellow]No active sessions[/yellow]")
        return

    console.print(f"[bold]Active Claude Sessions ({len(sessions)})[/bold]")
    for session_id, session in sessions.items():
        console.print(f"  • {session_id}")
        console.print(f"    Created: {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"    Last used: {session.last_used.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"    Turns: {session.turns}")
        console.print(f"    Resources: {', '.join(session.resources)}")
        console.print()


@app.command("clear")
def clear_sessions() -> None:
    """Clear all Claude AI sessions."""
    count = ClaudeClient.get_session_count()

    if count == 0:
        console.print("[yellow]No sessions to clear[/yellow]")
        return

    ClaudeClient.clear_all_sessions()

    # Also delete the runner session file
    try:
        config = ClientConfig()
        session_file = config.workspace_dir / "runner-session.txt"
        if session_file.exists():
            session_file.unlink()
            console.print(f"[green]✓[/green] Cleared {count} sessions and runner session file")
        else:
            console.print(f"[green]✓[/green] Cleared {count} sessions")
    except Exception as e:
        console.print(f"[green]✓[/green] Cleared {count} sessions")
        console.print(f"[yellow]Warning:[/yellow] Failed to delete runner session file: {e}")


@app.command("prompt")
async def add_prompt_to_session(
        prompt: str = typer.Option(
            None,
            "--prompt",
            "-p",
            help="Add custom instruction to your AI runner session",
        ),
) -> None:
    """Send a prompt to Claude using the latest session."""
    import asyncio

    if not prompt:
        console.print("[red]Error:[/red] Please provide a prompt using --prompt or -p")
        raise typer.Exit(1)

    # First try to get the runner's session ID
    runner_manager = RunnerManager()
    runner_session_id = runner_manager.get_runner_session_id()

    if runner_session_id:
        session_id = runner_session_id
        console.print(f"[blue]Using runner session: {session_id}[/blue]")
        try:
            # Create configuration and Claude client
            config = ClientConfig()
            claude_client = ClaudeClient(config=config)

            console.print(f"[blue]Sending prompt to Claude...[/blue]")
            console.print(f"[dim]Prompt: {prompt}[/dim]")

            # Make async call to Claude
            async def make_call():
                return await claude_client.make_call(
                    user_prompt=prompt,
                    session_id=session_id
                )

            response = asyncio.run(make_call())

            # Display response
            console.print("\n[green]Claude Response:[/green]")
            console.print(response)

        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to send prompt to Claude: {str(e)}")
            raise typer.Exit(1)
    else:
        console.print("[yellow]No running session found[/yellow]")
        session_id = None


@app.command("output")
def show_output() -> None:
    """Show the latest runner output."""
    config = ClientConfig()
    output_file = config.workspace_dir / "runner-output.md"

    if not output_file.exists():
        console.print("[yellow]No runner output found[/yellow]")
        console.print(f"Expected output file: {output_file}")
        console.print("The runner may not have executed yet, or may have encountered an error.")
        return

    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()

        console.print(f"[blue]Runner output from {output_file}:[/blue]")
        console.print()
        console.print(content)

    except Exception as e:
        console.print(f"[red]Error reading output file:[/red] {e}")