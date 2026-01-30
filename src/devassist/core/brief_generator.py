"""Brief generator for DevAssist (refactored for Claude Agent SDK).

Uses ClaudeClient to generate morning briefs via MCP servers.
"""

import asyncio
import logging
from datetime import datetime

from devassist.ai.claude_client import ClaudeClient
from devassist.models.brief import Brief, BriefSection
from devassist.models.config import ClientConfig
from devassist.models.context import SourceType

logger = logging.getLogger(__name__)


class BriefGenerator:
    """Generates Unified Morning Briefs using Claude Agent SDK.

    Now uses unified ClientConfig and self-contained ClaudeClient for session management.
    """

    def __init__(
        self,
        config: ClientConfig | None = None,
        claude_client: ClaudeClient | None = None,
    ) -> None:
        """Initialize BriefGenerator.

        Args:
            config: Application configuration (uses defaults if None).
            claude_client: Claude client for API calls (creates new if None).
        """
        self._config = config or ClientConfig()
        self._claude_client = claude_client or ClaudeClient(config=self._config)

    async def generate(
        self,
        sources: list[SourceType] | None = None,
        refresh: bool = False,
        user_prompt: str | None = None,
        session_id: str | None = None,
    ) -> Brief:
        """Generate a morning brief.

        Args:
            sources: Optional list of sources to include.
            refresh: If True, start a new session instead of resuming.
            session_id: Specific session ID to resume.

        Returns:
            Generated Brief object.
        """
        # Determine which resources to use
        if sources:
            resources = [s.value for s in sources]
        else:
            # Use all enabled sources from unified config
            resources = [source.value for source in self._config.enabled_sources]

        # Build the prompt for Claude
        if user_prompt:
            # Append custom prompt to default brief prompt
            prompt = self._build_brief_prompt(resources, additional_prompt=user_prompt)
        else:
            # Use default prompt only
            prompt = self._build_brief_prompt(resources)

        # Make the call to Claude
        try:
            # Determine session handling
            if refresh or not session_id:
                # Use current session (auto-created)
                response = await self._claude_client.make_call(user_prompt=prompt)
            else:
                # Resume existing session
                response = await self._claude_client.make_call(
                    user_prompt=prompt, session_id=session_id
                )

            # Get the active session for metadata
            latest_session = self._claude_client.get_latest_session()

            # Parse response into Brief object
            brief = self._parse_response_to_brief(response, resources)

            # Store session_id in brief metadata if needed
            if latest_session:
                brief.metadata = {"session_id": latest_session.session_id}

            return brief

        except Exception as e:
            logger.error(f"Failed to generate brief: {e}")

            # Return error brief
            return Brief(
                summary=f"Failed to generate brief: {str(e)}",
                sections=[],
                generated_at=datetime.now(),
                total_items=0,
                sources_queried=[],
                sources_failed=resources,
            )

    def _build_brief_prompt(self, resources: list[str], additional_prompt: str | None = None) -> str:
        """Build the prompt for morning brief generation.

        Args:
            resources: List of resource names.
            additional_prompt: Optional additional prompt to append.

        Returns:
            Prompt string.
        """
        resources_str = ", ".join(resources)

        base_prompt = f"""Generate my daily morning brief by aggregating information from {resources_str}.

Please organize the brief with these sections:

1. **Top Priorities**: Items requiring immediate attention today
2. **Action Items**: Explicit next steps across all sources
3. **Blockers & Urgent**: Issues preventing progress or time-sensitive matters
4. **Code Reviews**: PRs awaiting my review or feedback on my PRs
5. **Communications**: Important emails, messages, or meeting requests
6. **Context & FYI**: Relevant updates that don't require immediate action

For each section, include:
- Clear, concise summaries
- Relevant links
- Priority indicators where appropriate

Focus on items from the last 24-48 hours unless they are ongoing priorities."""

        if additional_prompt:
            return f"{base_prompt}\n\nAdditional requirements:\n{additional_prompt}"

        return base_prompt

    def _parse_response_to_brief(self, response: str, resources: list[str]) -> Brief:
        """Parse Claude's response into a Brief object.

        Args:
            response: Claude's markdown response.
            resources: List of resources queried.

        Returns:
            Brief object.
        """
        # For now, we'll create a simple brief with the response as summary
        # In a full implementation, we could parse the markdown sections

        # Create sections (placeholder - could be parsed from response)
        sections = []

        # Try to map resources to SourceType
        source_types = []
        for resource in resources:
            try:
                source_types.append(SourceType(resource))
            except ValueError:
                logger.warning(f"Unknown source type: {resource}")

        # Create brief
        brief = Brief(
            summary=response,
            sections=sections,
            generated_at=datetime.now(),
            total_items=0,  # We don't have individual items anymore
            sources_queried=source_types,
            sources_failed=[],
        )

        return brief

    async def resume_brief_session(self, session_id: str, follow_up: str) -> str:
        """Resume a brief session with a follow-up question.

        Args:
            session_id: Session ID to resume.
            follow_up: Follow-up question or request.

        Returns:
            Claude's response.
        """
        try:
            response = await self._claude_client.make_call(
                user_prompt=follow_up, session_id=session_id
            )
            return response
        except ValueError as e:
            logger.error(f"Failed to resume session: {e}")
            raise

    def list_recent_sessions(self, limit: int = 10) -> list:
        """List recent brief sessions.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of session metadata dicts.
        """
        # Get all sessions from ClaudeClient and sort by last_used
        all_sessions = self._claude_client.list_sessions()
        sorted_sessions = sorted(all_sessions, key=lambda s: s.last_used, reverse=True)

        # Apply limit
        recent_sessions = sorted_sessions[:limit] if limit else sorted_sessions

        return [
            {
                "session_id": s.session_id,
                "created_at": s.created_at.isoformat(),
                "last_used": s.last_used.isoformat(),
                "resources": s.resources,
                "turns": s.turns,
            }
            for s in recent_sessions
        ]


async def main():
    """Main method for debugging BriefGenerator in IDE.

    This allows you to run the brief generator directly for debugging purposes.
    Make sure to set your environment variables for JIRA and GitHub access:

    export JIRA_URL="https://your-jira-instance.com"
    export JIRA_USERNAME="your-email@company.com"
    export JIRA_PERSONAL_TOKEN="your-jira-token"
    export GITHUB_TOKEN="your-github-token"
    """
    try:
        print("🚀 Starting DevAssist Brief Generator (Debug Mode)")
        print("=" * 60)

        # Create configuration
        config = ClientConfig()
        print(f"📋 Configuration:")
        print(f"   • AI Model: {config.ai_model}")
        print(f"   • Enabled Sources: {[s.value for s in config.enabled_sources]}")
        print(f"   • Workspace: {config.workspace_dir}")
        print()

        # Create brief generator
        generator = BriefGenerator(config)
        print("🤖 Created BriefGenerator instance")

        # Generate brief
        print("📊 Generating morning brief...")
        brief = await generator.generate(
            sources=config.enabled_sources,
            user_prompt=None,  # Use default prompt
            session_id=None  # Create new session
        )

        print("✅ Brief generated successfully!")
        print("=" * 60)

        # Display brief details
        print(f"📄 Brief Summary:")
        print(f"   • Generated at: {brief.generated_at}")
        print(f"   • Total items: {brief.total_items}")
        print(f"   • Sources queried: {[s.value for s in brief.sources_queried]}")
        print(f"   • Sources failed: {brief.sources_failed}")
        print(f"   • Session ID: {brief.metadata.get('session_id', 'None')}")
        print()

        # Display brief content
        print("📝 Brief Content:")
        print("-" * 40)
        print(brief.summary)
        print("-" * 40)

        # Display sections
        if brief.sections:
            print(f"📂 Sections ({len(brief.sections)}):")
            for section in brief.sections:
                print(f"   • {section.display_name}: {section.item_count} items")

        print("\n🎉 Debug session complete!")

    except Exception as e:
        print(f"❌ Error during brief generation:")
        print(f"   {type(e).__name__}: {e}")
        logger.exception("Brief generation failed in debug mode")

        # Show configuration for debugging
        try:
            config = ClientConfig()
            print(f"\n🔧 Configuration Debug:")
            print(f"   • Enabled sources: {[s.value for s in config.enabled_sources]}")
            print(f"   • AI model: {config.ai_model}")
        except Exception as config_e:
            print(f"   Failed to load config: {config_e}")

        raise


if __name__ == "__main__":
    # Run the main function for debugging
    print("🐛 DevAssist Brief Generator - Debug Mode")
    print("Make sure you have set the required environment variables!")
    print()

    asyncio.run(main())
