"""AI CLI commands for DevAssist.

Provides commands for managing the background AI runner using Claude Agent SDK.
Updated to use the working execution approach that provides rich JIRA responses.
"""

import asyncio
import os
import typer
from rich.console import Console
from rich.table import Table
from datetime import datetime
from typing import Optional

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
    Uses direct execution approach (same as working runner.py main()) instead of subprocess.
    """
    import asyncio
    import logging

    # Setup logging for background process - USE DEBUG LEVEL (key to working approach!)
    logging.basicConfig(
        level=logging.DEBUG,  # DEBUG is critical for Claude SDK communication!
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(ClientConfig().workspace_dir / "logs" / "runner.log"),
            # No StreamHandler to prevent duplication in subprocess
        ]
    )

    # Read configuration from environment variables (set by CLI)
    interval_minutes = int(os.environ.get("DEVASSIST_RUNNER_INTERVAL", "5"))
    custom_prompt = os.environ.get("DEVASSIST_RUNNER_PROMPT")
    session_id = os.environ.get("DEVASSIST_RUNNER_SESSION_ID")
    enable_slack = os.environ.get("DEVASSIST_RUNNER_ENABLE_SLACK", "true").lower() == "true"

    # ✅ If no session_id from env, try to read from file (session continuity)
    if not session_id:
        try:
            config = ClientConfig()
            session_file = config.workspace_dir / "runner-session.txt"
            if session_file.exists():
                session_id = session_file.read_text().strip()
                logger = logging.getLogger(__name__)
                logger.info(f"Found existing session in file: {session_id}")
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to read session from file: {e}")

    # Use exact same pattern as working runner.py main()
    config = ClientConfig()

    # Use EXACT same initialization as working direct test
    runner = Runner(
        config=config,
        interval_minutes=interval_minutes,
        custom_prompt=custom_prompt,
        output_file=config.workspace_dir / "runner-output.md", # Explicit output file like working test
        enable_slack=enable_slack,
        session_id = session_id
    )

    # Use EXACT same execution pattern as working runner.py main()
    async def run_direct():
        execution_count = 0
        logger = logging.getLogger(__name__)
        # Use same stop checking pattern as working runner.py
        while not runner._stop_requested:
            execution_count += 1
            logger.info(f"Starting execution #{execution_count}")

            try:
                await runner._execute_prompt()
                logger.info(f"Execution #{execution_count} completed successfully")
            except Exception as e:
                logger.error(f"Execution #{execution_count} failed: {e}")

            # Only wait if we're continuing (same pattern as working runner.py)
            if not runner._stop_requested:
                wait_seconds = interval_minutes * 60
                await asyncio.sleep(wait_seconds)

    # Run the direct execution loop
    asyncio.run(run_direct())


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
        console.print(f"   • Timeout: {config.ai_timeout_seconds}s")
        console.print(f"   • Enabled sources: {[s.value for s in config.enabled_sources]}")

        # Test actual Claude call
        async def test_call():
            response = await client.make_call(
                user_prompt="Test: Please respond with a brief confirmation that you can access my context sources.",
            )
            return response

        console.print("[blue]Testing Claude API call...[/blue]")
        response = asyncio.run(test_call())

        if response and response.strip():
            console.print(f"[green]✓[/green] Claude API test successful")
            console.print(f"Response: {response[:100]}...")
        else:
            console.print(f"[yellow]⚠[/yellow] Claude API responded but with empty content")
            console.print("This might indicate MCP server issues or configuration problems")

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
        console.print(f"Timeout: [cyan]{config.ai_timeout_seconds}s[/cyan]")
        console.print(f"Enabled sources: {', '.join([s.value for s in config.enabled_sources])}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command("run")
def run(
    interval: int = typer.Option(5, "--interval", "-i", help="Run interval in minutes"),
    prompt: Optional[str] = typer.Option(
        None,
        "--prompt",
        "-p",
        help="Custom prompt for AI runner",
    ),
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        "-s",
        help="Session ID to continue conversation",
    ),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground"),
    enable_slack: bool = typer.Option(True, "--enable-slack/--disable-slack", help="Enable Slack notifications"),
) -> None:
    """Start the background AI runner."""
    runner_manager = RunnerManager()

    # Check if already running
    if runner_manager.is_running():
        console.print("[yellow]Runner is already running.[/yellow]")
        console.print("Use [bold]devassist ai status[/bold] to check status or [bold]devassist ai kill[/bold] to stop")
        return

    if foreground:
        # Run in foreground using direct execution (same as working runner.py main())
        console.print(f"[blue]Starting AI runner in foreground (interval: {interval}m, Ctrl+C to stop)[/blue]")
        if session_id:
            console.print(f"[dim]Using session: {session_id}[/dim]")
        console.print(f"[dim]Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}[/dim]")

        try:
            # Setup DEBUG logging for foreground (critical!)
            import logging
            logging.basicConfig(
                level=logging.DEBUG,  # DEBUG is critical!
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                handlers=[logging.StreamHandler()]
            )

            # Use exact same pattern as working runner.py main()
            config = ClientConfig()

            # Use EXACT same initialization as working direct test
            runner = Runner(
                config=config,
                interval_minutes=interval,
                custom_prompt=prompt,
                output_file=config.workspace_dir / "runner-output.md",  # Explicit output file like working test
                session_id=session_id,  # ✅ Pass session_id for continuity
                enable_slack=enable_slack,  # ✅ Pass enable_slack from CLI
            )

            console.print(f"[green]✓[/green] Runner created (Session: {runner.session_id})")
            console.print("[blue]Running in foreground using direct execution...[/blue]")

            # Use EXACT same execution pattern as working runner.py main()
            async def run_direct():
                execution_count = 0
                # Run indefinitely but with proper stop checking (same as working runner.py)
                while not runner._stop_requested:
                    execution_count += 1
                    console.print(f"\n[blue]🔄 Starting execution #{execution_count}[/blue]")

                    try:
                        await runner._execute_prompt()
                        console.print(f"[green]✅ Execution #{execution_count} completed successfully[/green]")

                        # Show output snippet
                        if runner.output_file.exists():
                            content = runner.output_file.read_text()[:200]
                            console.print(f"[dim]📄 Output preview: {content}...[/dim]")

                    except Exception as e:
                        console.print(f"[red]❌ Execution #{execution_count} failed: {e}[/red]")

                    # Only wait if we're continuing (same pattern as working runner.py)
                    if not runner._stop_requested:
                        wait_seconds = interval * 60
                        console.print(f"[dim]⏳ Waiting {interval} minutes before next execution...[/dim]")
                        await asyncio.sleep(wait_seconds)

            asyncio.run(run_direct())
        except KeyboardInterrupt:
            console.print("\n[yellow]Runner stopped by user.[/yellow]")
    else:
        # Start as background process
        try:
            runner_manager.start(interval=interval, prompt=prompt, session_id=session_id, enable_slack=enable_slack)
            status = runner_manager.get_status()
            console.print(f"[green]✓[/green] AI runner started successfully")
            console.print(f"[dim]PID: {status.pid}[/dim]")
            console.print(f"[dim]Interval: {interval} minutes[/dim]")
            if session_id:
                console.print(f"[dim]Session: {session_id}[/dim]")
            console.print(f"[dim]Prompt: {prompt[:50] + '...' if prompt and len(prompt) > 50 else prompt or 'Default'}[/dim]")

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
    clear_sessions()

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
    runner_manager = RunnerManager()
    runner_session = runner_manager.get_runner_session_id()

    if count == 0 and not runner_session:
        console.print("[yellow]No sessions to clear[/yellow]")
        return

    ClaudeClient.clear_all_sessions()

    # Also delete the runner session file
    try:
        config = ClientConfig()
        session_file = config.workspace_dir / "runner-session.txt"
        if session_file.exists():
            session_file.unlink()
            console.print(f"[green]✓[/green] Cleared {runner_session} session and runner session file")
        else:
            console.print(f"[green]✓[/green] Cleared {runner_session} session")
    except Exception as e:
        console.print(f"[green]✓[/green] Cleared {runner_session} session")
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
        console.print("Start the runner first with: [bold]devassist ai run[/bold]")


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