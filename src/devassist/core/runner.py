"""Background runner core logic for DevAssist.

Executes custom prompts on a scheduled interval using ClaudeClient and configuration.
"""

import asyncio
import logging
import signal
from datetime import datetime
from pathlib import Path

from devassist.ai.claude_client import ClaudeClient
from devassist.core.slack_client import SlackClient
from devassist.models.config import ClientConfig
from devassist.resources import get_dev_assistant_system_prompt

logger = logging.getLogger(__name__)


class Runner:
    """Background runner that executes prompts at intervals using ClaudeClient.

    Orchestrates:
    - Fetching context via Claude Agent SDK (through MCP servers)
    - Executing custom prompts with AI
    - Writing output to destination file
    - Interval scheduling
    """

    def __init__(
        self,
        config: ClientConfig | None = None,
        interval_minutes: int = 5,
        custom_prompt: str | None = None,
        output_file: Path | str | None = None,
        session_id: str | None = None,
        enable_slack: bool = True,
    ) -> None:
        """Initialize the background runner.

        Args:
            config: Client configuration.
            interval_minutes: Interval between executions in minutes.
            custom_prompt: Custom prompt to execute.
            output_file: Output file path.
            session_id: Existing session ID to continue conversations. If None, creates new session.
            enable_slack: Whether to send notifications via Slack (uses env vars for tokens).
        """
        self.config = config or ClientConfig()
        if not self.config.system_prompt:
            self.config.system_prompt = get_dev_assistant_system_prompt()
        self.claude_client = ClaudeClient(config=self.config)
        self.interval_minutes = interval_minutes
        self.custom_prompt = custom_prompt or "Review my recent context and summarize urgent items requiring attention."

        # Initialize Slack client if enabled
        self.enable_slack = enable_slack
        self.slack_client = None
        if enable_slack:
            try:
                self.slack_client = SlackClient()
                logger.info("Slack notifications enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Slack client: {e}")
                self.enable_slack = False

        if output_file is None:
            output_file = self.config.workspace_dir / "runner-output.md"
        self.output_file = Path(output_file)

        # Session management for conversation continuity
        if session_id:
            # Try to use existing session
            existing_session = ClaudeClient.get_session_by_id(session_id)
            if existing_session:
                self.session_id = session_id
                logger.info(f"Using existing session: {session_id}")
            else:
                logger.warning(f"Session {session_id} not found, creating new session")
                self.session_id = self.claude_client.session.session_id
        else:
            # Use the session created by claude_client
            self.session_id = self.claude_client.session.session_id

        # Ensure output directory exists
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        self._stop_requested = False

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, stopping runner...")
        self._stop_requested = True

    async def run(self) -> None:
        """Run the background runner loop.

        Executes the prompt at specified intervals until stopped.
        """
        logger.info(f"Starting background runner (interval: {self.interval_minutes}m)")
        logger.info(f"Output file: {self.output_file}")
        logger.info(f"Enabled sources: {[s.value for s in self.config.enabled_sources]}")

        execution_count = 0

        try:
            while not self._stop_requested:
                execution_count += 1
                logger.info(f"Starting execution #{execution_count}")

                try:
                    await self._execute_prompt()
                    logger.info(f"Execution #{execution_count} completed successfully")
                except Exception as e:
                    logger.error(f"Execution #{execution_count} failed: {e}")

                # Wait for next interval (with early exit on stop request)
                for _ in range(self.interval_minutes * 60):  # Convert to seconds
                    if self._stop_requested:
                        break
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Runner crashed: {e}")
            raise
        finally:
            logger.info("Background runner stopped")

    async def _execute_prompt(self) -> None:
        """Execute the custom prompt and save output."""
        try:
            # Generate timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Build the full prompt with size optimization
            full_prompt = f"""[DevAssist Background Runner - {timestamp}]

{self.custom_prompt}

    Please check my most urgent items requiring immediate attention."""
            if self.session_id:
                full_prompt = f"""
                {full_prompt}
                Please check if anything new or existing item that still needs my urgent attention
                """

            # Execute with Claude Agent SDK using session for continuity
            logger.debug(f"Executing prompt with Claude (session: {self.session_id})...")

            try:
                response = await self.claude_client.make_call(
                    user_prompt=full_prompt,
                    session_id=self.session_id
                )

                # Send Slack notification if enabled
                if self.enable_slack and self.slack_client:
                    try:
                        await self.slack_client.send_direct_message(
                            user_id="U0ABNAZCQG3",
                            text=response
                        )
                        logger.debug("Slack notification sent successfully")
                    except Exception as slack_error:
                        logger.warning(f"Failed to send Slack notification: {slack_error}")

                # Write to output file
                await self._write_output(timestamp, response)
                logger.debug("Prompt execution completed")

            except Exception as sdk_error:
                # Check if it's a buffer size error and handle gracefully
                error_msg = str(sdk_error).lower()
                if "buffer size" in error_msg or "json message exceeded" in error_msg:
                    logger.warning("Context data too large, trying with reduced scope...")

                    # Try with a more restrictive prompt
                    fallback_prompt = f"""[DevAssist Background Runner - {timestamp}]

Due to large data volume, please provide ONLY:
1. Most urgent JIRA issues assigned to me (max 3)
2. Critical emails from today (max 2)
3. Any high-priority Slack notifications

Keep response under 300 words total."""

                    try:
                        response = await self.claude_client.make_call(
                            user_prompt=fallback_prompt,
                            session_id=self.session_id
                        )

                        response = f"⚠️ **Large dataset detected - showing prioritized summary:**\n\n{response}"
                        await self._write_output(timestamp, response)
                        logger.info("Fallback execution completed with reduced scope")

                    except Exception as fallback_error:
                        # If fallback also fails, write a helpful error
                        logger.error(f"Both primary and fallback execution failed: {fallback_error}")
                        await self._write_error(
                            f"Context data too large for processing. "
                            f"Consider reducing enabled sources or contact frequency.\n\n"
                            f"Original error: {sdk_error}\n"
                            f"Fallback error: {fallback_error}"
                        )
                else:
                    # Re-raise non-buffer-related errors
                    raise sdk_error

        except Exception as e:
            logger.error(f"Failed to execute prompt: {e}")
            # Write error to output file
            await self._write_error(str(e))

    async def _write_output(self, timestamp: str, content: str) -> None:
        """Write output to the destination file.

        Args:
            timestamp: Execution timestamp.
            content: Content to write.
        """
        try:
            # Prepare output with timestamp header
            output = f"""# DevAssist Background Runner
**Last Updated:** {timestamp}

{content}

---
*Generated by DevAssist Background Runner every {self.interval_minutes} minutes*
"""

            # Append to file (preserve previous runs)
            with open(self.output_file, 'a', encoding='utf-8') as f:
                f.write(output)

            logger.debug(f"Output written to {self.output_file}")

        except Exception as e:
            logger.error(f"Failed to write output to {self.output_file}: {e}")

    async def _write_error(self, error: str) -> None:
        """Write error message to output file.

        Args:
            error: Error message.
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_output = f"""# DevAssist Background Runner - ERROR
**Last Attempted:** {timestamp}

⚠️ **Error occurred during execution:**

```
{error}
```

Please check the logs for more details.

---
*Generated by DevAssist Background Runner*
"""

            with open(self.output_file, 'a', encoding='utf-8') as f:
                f.write(error_output)

        except Exception as e:
            logger.error(f"Failed to write error to {self.output_file}: {e}")

    def stop(self) -> None:
        """Request the runner to stop."""
        logger.info("Stop requested")
        self._stop_requested = True

    def get_session_id(self) -> str:
        """Get the current session ID for this runner.

        Returns:
            Current session ID.
        """
        return self.session_id


async def main():
    """Main method for debugging Runner in IDE.

    This allows you to run the background runner directly for debugging purposes.
    Make sure to set your environment variables for source access:

    export JIRA_URL="https://your-jira-instance.com"
    export JIRA_USERNAME="your-email@company.com"
    export JIRA_PERSONAL_TOKEN="your-jira-token"
    export GITHUB_TOKEN="your-github-token"
    """
    import logging

    # Setup detailed logging for debugging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("runner-debug.log")
        ]
    )

    try:
        print("🚀 Starting DevAssist Background Runner (Debug Mode)")
        print("=" * 60)

        # Create configuration
        config = ClientConfig()
        print(f"📋 Runner Configuration:")
        print(f"   • AI Model: {config.ai_model}")
        print(f"   • Enabled Sources: {[s.value for s in config.enabled_sources]}")
        print(f"   • Workspace: {config.workspace_dir}")
        print(f"   • Timeout: {config.ai_timeout_seconds}s")
        print()

        # Create runner with debug settings
        runner = Runner(
            config=config,
            interval_minutes=2,  # Quick interval for debugging
            custom_prompt="Debug run: Please provide a brief summary of highest priority jira tickets assigned to me in the current sprint (max 3 items)",
            output_file=config.workspace_dir / "runner-debug-output.md"
        )

        print("🤖 Created Runner instance")
        print(f"📁 Debug output file: {runner.output_file}")
        print(f"🔗 Session ID: {runner.session_id}")
        print()

        # Run for a limited time in debug mode
        print("⏱️  Running for 3 executions (Ctrl+C to stop early)...")

        execution_count = 0
        max_executions = 3

        while not runner._stop_requested and execution_count < max_executions:
            execution_count += 1
            print(f"\n🔄 Starting debug execution #{execution_count}")

            try:
                await runner._execute_prompt()
                print(f"✅ Debug execution #{execution_count} completed successfully")

                # Show output snippet
                if runner.output_file.exists():
                    content = runner.output_file.read_text()[:200]
                    print(f"📄 Output preview: {content}...")

            except Exception as e:
                print(f"❌ Debug execution #{execution_count} failed: {e}")
                logger.exception("Debug execution failed")

            if execution_count < max_executions:
                print(f"⏳ Waiting 10 seconds before next execution...")
                await asyncio.sleep(10)

        print(f"\n🎉 Debug session complete! ({execution_count}/{max_executions} executions)")
        print(f"📁 Full output available at: {runner.output_file}")

        # Show final output
        if runner.output_file.exists():
            print("\n📋 Final Output:")
            print("-" * 40)
            print(runner.output_file.read_text())
            print("-" * 40)

    except KeyboardInterrupt:
        print("\n⏹️  Debug session interrupted by user")
    except Exception as e:
        print(f"❌ Error during runner debug:")
        print(f"   {type(e).__name__}: {e}")
        logger.exception("Runner debug failed")

        # Show configuration for debugging
        try:
            config = ClientConfig()
            print(f"\n🔧 Configuration Debug:")
            print(f"   • Available sources: {[s.value for s in config.get_available_sources()]}")
            print(f"   • Enabled sources: {[s.value for s in config.enabled_sources]}")
        except Exception as config_e:
            print(f"   Failed to load config: {config_e}")

        raise


if __name__ == "__main__":
    # Run the main function for debugging
    print("🐛 DevAssist Background Runner - Debug Mode")
    print("Make sure you have set the required environment variables!")
    print()

    asyncio.run(main())