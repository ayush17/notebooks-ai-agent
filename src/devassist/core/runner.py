"""Background runner core logic for DevAssist.

Executes custom prompts on a scheduled interval using AI and context aggregation.
"""

import asyncio
import logging
import signal
from datetime import datetime
from pathlib import Path
from typing import Any

from devassist.ai.base_client import BaseAIClient
from devassist.ai.prompts import get_runner_system_prompt
from devassist.core.aggregator import ContextAggregator
from devassist.models.context import ContextItem
from devassist.models.mcp_config import MCPConfig

logger = logging.getLogger(__name__)


class Runner:
    """Background runner that executes prompts at intervals.

    Orchestrates:
    - Fetching context from all sources
    - Executing custom prompts with AI
    - Writing output to destination file
    - Interval scheduling
    - Graceful shutdown on signals
    """

    def __init__(
        self,
        config: MCPConfig,
        workspace_dir: Path | str | None = None,
        ai_client: BaseAIClient | None = None,
        aggregator: ContextAggregator | None = None,
    ) -> None:
        """Initialize Runner.

        Args:
            config: MCP configuration.
            workspace_dir: Path to workspace directory.
            ai_client: AI client for prompt execution.
            aggregator: Context aggregator for fetching items.
        """
        if workspace_dir is None:
            workspace_dir = Path.home() / ".devassist"
        self.workspace_dir = Path(workspace_dir)
        self.config = config
        self.ai_client = ai_client
        self.aggregator = aggregator

        # Runner configuration
        self.interval_minutes = config.runner.interval_minutes
        self.prompt = config.runner.prompt
        self.output_destination = Path(config.runner.output_destination).expanduser()

        # State
        self.running = False
        self.last_run: datetime | None = None
        self.last_result: str | None = None  # Store previous result for comparison

        # Ensure output directory exists
        self.output_destination.parent.mkdir(parents=True, exist_ok=True)

    async def execute_once(self) -> str | None:
        """Execute the runner task once.

        Fetches context, executes prompt with AI, and writes output.

        Returns:
            Generated output string, or None if execution failed.
        """
        try:
            logger.info("Executing runner task")

            # Fetch context from all sources
            items: list[ContextItem] = []
            if self.aggregator:
                try:
                    items = await self.aggregator.fetch_all()
                    logger.info(f"Fetched {len(items)} context items")
                except Exception as e:
                    logger.error(f"Error fetching context: {e}")

            # Format context for AI (includes previous result for comparison)
            context = self._format_context(items)

            # Execute prompt with AI using runner-specific system prompt
            if not self.ai_client:
                logger.warning("No AI client configured")
                return None

            result = await self.ai_client.execute_prompt(
                self.prompt,
                context,
                system_prompt=get_runner_system_prompt(),
            )

            # Write output
            self._write_output(result)

            # Update state
            self.last_run = datetime.now()
            self.last_result = result

            logger.info("Runner task completed successfully")
            return result

        except Exception as e:
            logger.error(f"Error executing runner task: {e}", exc_info=True)
            return None

    async def run(self) -> None:
        """Run the background task loop.

        Executes the task at configured intervals until stop() is called.
        """
        self.running = True
        logger.info(
            f"Starting runner loop (interval: {self.interval_minutes} minutes)"
        )

        # Setup signal handlers
        self._setup_signal_handlers()

        try:
            while self.running:
                # Execute task
                if self.running:  # Check before execution
                    await self.execute_once()

                # Wait for next interval (check every 100ms for stop signal)
                if self.running:
                    interval_seconds = self.interval_minutes * 60
                    elapsed = 0.0
                    sleep_interval = 0.1  # Check every 100ms

                    while elapsed < interval_seconds and self.running:
                        await asyncio.sleep(sleep_interval)
                        elapsed += sleep_interval

        except asyncio.CancelledError:
            logger.info("Runner loop cancelled")
        except Exception as e:
            logger.error(f"Error in runner loop: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("Runner loop stopped")

    def stop(self) -> None:
        """Stop the runner loop gracefully."""
        logger.info("Stopping runner")
        self.running = False

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        try:
            loop = asyncio.get_event_loop()

            def signal_handler(signum: int) -> None:
                logger.info(f"Received signal {signum}, stopping runner")
                self.stop()

            # Register signal handlers
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

        except NotImplementedError:
            # Signal handlers not supported on this platform (e.g., Windows)
            logger.warning("Signal handlers not supported on this platform")

    def _format_context(self, items: list[ContextItem]) -> dict[str, Any]:
        """Format context items for AI prompt.

        Args:
            items: List of context items.

        Returns:
            Dictionary with formatted context data including previous result.
        """
        return {
            "items": [
                {
                    "source": item.source_type.value,
                    "title": item.title,
                    "content": item.content,
                    "author": item.author,
                    "timestamp": item.timestamp.isoformat(),
                    "relevance_score": item.relevance_score,
                    "url": item.url,
                }
                for item in items
            ],
            "count": len(items),
            "timestamp": datetime.now().isoformat(),
            "previous_result": self.last_result,
            "last_run": self.last_run.isoformat() if self.last_run else None,
        }

    def _write_output(self, output: str) -> None:
        """Write output to destination file.

        Args:
            output: Generated output string.
        """
        try:
            # Append timestamp header
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content = f"# Runner Output - {timestamp}\n\n{output}\n\n---\n\n"

            # Append to file
            with open(self.output_destination, "a") as f:
                f.write(content)

            logger.info(f"Wrote output to {self.output_destination}")

        except Exception as e:
            logger.error(f"Error writing output: {e}")
