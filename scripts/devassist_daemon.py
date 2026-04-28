#!/usr/bin/env python3
"""DevAssist Background Daemon.

Runs periodic morning briefs and monitors for updates.
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, time
from pathlib import Path

# Add project to path
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from devassist.mcp.client import MCPClient
from devassist.mcp.registry import MCPRegistry, MCPServerConfig
from devassist.orchestrator.agent import OrchestrationAgent
from devassist.core.env_store import load_devassist_env_into_os
from devassist.orchestrator.llm_client import AnthropicLLMClient, VertexAILLMClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path.home() / ".devassist" / "daemon.log"),
    ],
)
logger = logging.getLogger("devassist.daemon")

# Configuration
BRIEF_TIMES = [
    time(8, 0),   # 8 AM
    time(13, 0),  # 1 PM
    time(17, 0),  # 5 PM
]
CHECK_INTERVAL = 60  # seconds between checks


class DevAssistDaemon:
    """Background daemon for DevAssist."""

    def __init__(self):
        self.running = True
        self.last_brief_date = None
        self.briefs_generated_today = set()

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def _load_env(self):
        """Load ``~/.devassist/env`` (and legacy ``.env``) into the process environment."""
        load_devassist_env_into_os(prefer_file=True)
        logger.info("Loaded DevAssist env file(s)")

    def _get_llm_client(self):
        """Get configured LLM client."""
        provider = os.environ.get("LLM_PROVIDER", "anthropic")
        if provider == "anthropic":
            return AnthropicLLMClient()
        else:
            return VertexAILLMClient(
                project_id=os.environ.get("GOOGLE_CLOUD_PROJECT")
            )

    def _get_configured_servers(self) -> list[MCPServerConfig]:
        """Get list of configured MCP servers."""
        registry = MCPRegistry()
        servers = []

        # Check GitHub
        if os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN"):
            config = registry.get("github")
            if config:
                config.env["GITHUB_PERSONAL_ACCESS_TOKEN"] = os.environ[
                    "GITHUB_PERSONAL_ACCESS_TOKEN"
                ]
                servers.append(config)
                logger.info("GitHub MCP server configured")

        # Atlassian: remote MCP via mcp-remote (auth handled by connector, not API tokens here)
        atlassian = registry.get("atlassian")
        if atlassian:
            servers.append(atlassian)
            logger.info("Atlassian MCP server configured (remote)")

        return servers

    async def generate_brief(self, prompt: str = None) -> str:
        """Generate a brief using the orchestration agent."""
        if prompt is None:
            prompt = """Give me a morning brief. Summarize:
1. Any important GitHub notifications, PR reviews needed, or issues assigned to me
2. My open Jira issues and Confluence updates that need attention (via Atlassian)
3. Any urgent items I should prioritize

Be concise and actionable."""

        servers = self._get_configured_servers()
        if not servers:
            return "No MCP servers configured. Run setup_credentials.sh first."

        llm_client = self._get_llm_client()
        mcp_client = MCPClient()
        registry = MCPRegistry()

        agent = OrchestrationAgent(
            llm_client=llm_client,
            mcp_client=mcp_client,
            registry=registry,
        )

        try:
            async with mcp_client.connect_all(servers):
                response = await agent.process(prompt)
                return response.content
        except Exception as e:
            logger.error(f"Error generating brief: {e}")
            return f"Error generating brief: {e}"

    def _should_generate_brief(self) -> bool:
        """Check if we should generate a brief now."""
        now = datetime.now()
        current_time = now.time()

        # Reset daily tracking
        if self.last_brief_date != now.date():
            self.last_brief_date = now.date()
            self.briefs_generated_today = set()

        # Check if current time matches a brief time (within 1 minute)
        for brief_time in BRIEF_TIMES:
            if brief_time in self.briefs_generated_today:
                continue

            # Check if within 1 minute of brief time
            brief_minutes = brief_time.hour * 60 + brief_time.minute
            current_minutes = current_time.hour * 60 + current_time.minute

            if abs(brief_minutes - current_minutes) <= 1:
                self.briefs_generated_today.add(brief_time)
                return True

        return False

    def _save_brief(self, content: str):
        """Save brief to file."""
        briefs_dir = Path.home() / ".devassist" / "briefs"
        briefs_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        brief_file = briefs_dir / f"brief_{timestamp}.md"

        with open(brief_file, "w") as f:
            f.write(f"# DevAssist Brief - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(content)

        logger.info(f"Brief saved to {brief_file}")

        # Also save as latest
        latest_file = briefs_dir / "latest.md"
        with open(latest_file, "w") as f:
            f.write(f"# DevAssist Brief - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(content)

    async def run(self):
        """Main daemon loop."""
        logger.info("DevAssist daemon starting...")
        self._load_env()

        # Generate initial brief on startup
        logger.info("Generating startup brief...")
        content = await self.generate_brief()
        self._save_brief(content)
        print("\n" + "=" * 50)
        print("DEVASSIST BRIEF")
        print("=" * 50)
        print(content)
        print("=" * 50 + "\n")

        logger.info(f"Daemon running. Briefs scheduled at: {BRIEF_TIMES}")

        while self.running:
            try:
                if self._should_generate_brief():
                    logger.info("Scheduled brief time - generating...")
                    content = await self.generate_brief()
                    self._save_brief(content)

                    # Print to console
                    print("\n" + "=" * 50)
                    print("DEVASSIST BRIEF")
                    print("=" * 50)
                    print(content)
                    print("=" * 50 + "\n")

                await asyncio.sleep(CHECK_INTERVAL)

            except Exception as e:
                logger.error(f"Error in daemon loop: {e}")
                await asyncio.sleep(CHECK_INTERVAL)

        logger.info("Daemon stopped")


def main():
    """Entry point."""
    daemon = DevAssistDaemon()
    asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
