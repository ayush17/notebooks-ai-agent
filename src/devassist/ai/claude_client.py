"""Claude Agent SDK client for DevAssist.

Manages Claude sessions and API calls using the Claude Agent SDK.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar
from devassist.resources import get_mcp_servers_config

from devassist.models import McpServerConfig
from devassist.models.config import ClientConfig

logger = logging.getLogger(__name__)



@dataclass
class ClaudeSession:
    """Represents a Claude conversation session."""

    session_id: str
    created_at: datetime
    last_used: datetime
    resources: list[str]
    turns: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dictionary.

        Returns:
            Dictionary representation of session.
        """
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "resources": self.resources,
            "turns": self.turns,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClaudeSession":
        """Deserialize session from dictionary.

        Args:
            data: Dictionary containing session data.

        Returns:
            ClaudeSession instance.
        """
        return cls(
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_used=datetime.fromisoformat(data["last_used"]),
            resources=data["resources"],
            turns=data.get("turns", 0),
            metadata=data.get("metadata", {}),
        )


class ClaudeClient:
    """Client for interacting with Claude via the Agent SDK.

    Manages sessions, MCP server configuration, and API calls.

    Session Management:
    - Uses a static session store shared across ALL ClaudeClient instances
    - Sessions persist for the entire Python session duration
    - New sessions are appended to the store (never cleared automatically)
    - All instances can access and use any session from the static store
    """

    # Static session store shared across all ClaudeClient instances
    # Persists for the entire Python session duration
    _session_store: ClassVar[dict[str, ClaudeSession]] = {}

    def __init__(self, config: ClientConfig | None = None) -> None:
        """Initialize ClaudeClient and create a session.

        Args:
            config: Application configuration.
        """
        self.config = config or ClientConfig()

        # Create session automatically using config
        self.session = self.create_session()


    def _get_mcp_servers_config(self, resources: list[str] | None = None) -> dict[str, Any]:
        """Get MCP servers configuration for specified resources.

        Args:
            resources: List of resource names (gmail, slack, jira, github).
                      If None, returns all configured sources.

        Returns:
            Dictionary of MCP server configurations with environment variables resolved.
        """
        # Load raw MCP config from JSON
        raw_mcp_config = get_mcp_servers_config()

        # Determine which sources to include
        enabled_sources = {source.value for source in self.config.enabled_sources}
        if resources:
            target_sources = enabled_sources.intersection(set(resources))
        else:
            target_sources = enabled_sources

        # Build resolved configuration using McpServerConfig
        resolved_config = {}
        for server_name in target_sources:
            if server_name not in raw_mcp_config:
                logger.warning(f"MCP config not found for server: {server_name}")
                continue

            # Create McpServerConfig directly from JSON - field validator will resolve env vars
            raw_config = raw_mcp_config[server_name]
            server_config = McpServerConfig(**raw_config)

            # Convert back to dict for Claude SDK
            resolved_config[server_name] = server_config.model_dump()

        logger.debug(f"Resolved MCP config for {len(resolved_config)} servers: {list(resolved_config.keys())}")
        return resolved_config

    def _init_sdk_client(self) -> Any:
        """Initialize and connect Claude SDK client using config.

        Returns:
            Connected Claude SDK client instance.
        """
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

        # Get MCP servers config from enabled sources
        mcp_servers = self._get_mcp_servers_config()

        # Get system prompt from config
        system_prompt = self.config.resolved_system_prompt

        # Configure options using config values
        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            mcp_servers=mcp_servers,
            permission_mode=self.config.permission_mode,
            max_thinking_tokens=10_000,
            max_buffer_size=10_000_000
        )

        # Initialize SDK client
        sdk_client = ClaudeSDKClient(options=options)

        # Connect the SDK client immediately
        import asyncio
        try:
            # Try to connect in the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we'll connect on first use
                logger.debug(f"Deferring SDK client connection for async context")
            else:
                # If no event loop is running, create one to connect
                asyncio.run(sdk_client.connect())
                logger.info(f"Connected Claude SDK client with {len(mcp_servers)} MCP servers")
        except RuntimeError:
            # Event loop is running, we'll connect on first use
            logger.debug(f"Deferring SDK client connection due to running event loop")
        except Exception as e:
            logger.warning(f"Failed to connect SDK client during initialization: {e}")

        return sdk_client

    def create_session(self) -> ClaudeSession:
        """Create a new Claude session using config.

        Returns:
            ClaudeSession object with session ID.
        """
        # Generate session ID
        session_id = f"session-{uuid.uuid4().hex[:12]}"

        # Initialize SDK client using config
        sdk_client = self._init_sdk_client()

        # Create session object using config
        session = ClaudeSession(
            session_id=session_id,
            created_at=datetime.now(),
            last_used=datetime.now(),
            resources=[source.value for source in self.config.enabled_sources],
            metadata={"sdk_client": sdk_client, "output_format": self.config.output_format},
        )

        # Store session
        ClaudeClient._session_store[session_id] = session

        logger.info(f"Created Claude session: {session_id}")
        return session

    async def make_call(
        self,
        user_prompt: str,
        session_id: str | None = None,
    ) -> str:
        """Make a call to Claude with configurable timeout.

        Args:
            user_prompt: User's prompt/question.
            session_id: Existing session ID to continue. If None, uses current session.

        Returns:
            Claude's response as a string.

        Raises:
            asyncio.TimeoutError: If the request exceeds the configured timeout.
        """
        from claude_agent_sdk import AssistantMessage, TextBlock, ThinkingBlock

        # Get session - use provided session_id or current client session
        if session_id and session_id in ClaudeClient._session_store:
            session = ClaudeClient._session_store[session_id]
        elif session_id:
            # ✅ Session ID provided but not in store (subprocess context)
            # Create a minimal session object with the provided session_id
            logger.info(f"Creating session object for subprocess session_id: {session_id}")
            session = ClaudeSession(
                session_id=session_id,
                created_at=datetime.now(),
                last_used=datetime.now(),
                resources=[source.value for source in self.config.enabled_sources],
                metadata={"sdk_client": self._init_sdk_client(), "output_format": self.config.output_format},
            )
            # Store for future use in this process
            ClaudeClient._session_store[session_id] = session
        else:
            # Use the current client's session or create a new one if needed
            session = self.session

        # Get SDK client from session metadata
        sdk_client = session.metadata.get("sdk_client")
        if not sdk_client:
            raise ValueError(f"No SDK client found for session {session.session_id}")

        # Apply timeout from configuration
        timeout_seconds = self.config.ai_timeout_seconds
        logger.debug(f"Using AI timeout: {timeout_seconds}s for session {session.session_id}")

        try:
            # Wrap the entire Claude interaction with timeout
            async with asyncio.timeout(timeout_seconds):
                # ✅ Add explicit connection check if the SDK supports it
                try:
                    # Try to determine if we're connected (SDK may not expose this method)
                    if hasattr(sdk_client, 'is_connected') and not sdk_client.is_connected():
                        logger.info(f"SDK client not connected - connecting for session {session.session_id}")
                        await sdk_client.connect()
                except AttributeError:
                    # SDK doesn't have is_connected method, proceed with error-based detection
                    pass

                # Ensure SDK client is connected before first use
                try:
                    logger.info(f"Prompt: {user_prompt}")
                    await sdk_client.query(user_prompt, session_id=session.session_id)
                except Exception as e:
                    # If not connected, try to connect and retry
                    if "Not connected" in str(e) or "connect" in str(e).lower():
                        logger.info(f"Connecting SDK client for session {session.session_id}")
                        await sdk_client.connect()
                        await sdk_client.query(user_prompt, session_id=session.session_id)
                    else:
                        raise

                # Collect response
                response_parts = []
                message_count = 0
                async for message in sdk_client.receive_response():
                    message_count += 1
                    logger.debug(f"Received message #{message_count}: {type(message).__name__}")

                    if isinstance(message, AssistantMessage):
                        logger.debug(f"AssistantMessage with {len(message.content)} blocks")
                        for i, block in enumerate(message.content):
                            logger.debug(f"Block {i}: {type(block).__name__}")
                            if isinstance(block, TextBlock):
                                logger.debug(f"TextBlock content length: {len(block.text)}")
                                response_parts.append(block.text)
                            elif isinstance(block, ThinkingBlock):
                                # Optionally include thinking blocks
                                logger.debug(f"ThinkingBlock content length: {len(block.thinking)}")
                                logger.debug(f"Claude thinking: {block.thinking[:100]}...")
                    else:
                        logger.debug(f"Non-AssistantMessage: {message}")

                logger.debug(f"Total messages: {message_count}, response_parts: {len(response_parts)}")

        except asyncio.TimeoutError:
            logger.error(f"Claude API call timed out after {timeout_seconds}s for session {session.session_id}")
            raise asyncio.TimeoutError(
                f"Claude API call timed out after {timeout_seconds}s. "
                f"You can increase the timeout with --timeout <seconds> or in your config."
            )

        # Update session
        session.last_used = datetime.now()
        session.turns += 1

        response = "\n".join(response_parts)

        # ✅ Add response validation
        if not response.strip():
            logger.warning("Claude SDK returned empty response - check MCP server configuration")
            # Don't return empty string, return a helpful message
            return "No response received from Claude SDK. This may indicate MCP server connection issues or configuration problems."

        logger.info(f"Claude response received (session: {session.session_id}, turns: {session.turns})")
        logger.debug(f"Response parts count: {len(response_parts)}, total length: {len(response)}")
        logger.debug(f"Response content preview: {repr(response[:200])}")

        return response

    async def resume_session(self, session_id: str) -> ClaudeSession:
        """Resume an existing session.

        Args:
            session_id: Session ID to resume.

        Returns:
            ClaudeSession object.

        Raises:
            ValueError: If session not found.
        """
        if session_id not in ClaudeClient._session_store:
            raise ValueError(f"Session {session_id} not found")

        session = ClaudeClient._session_store[session_id]
        session.last_used = datetime.now()

        logger.info(f"Resumed session: {session_id}")
        return session

    async def compact_conversation(self, session_id: str) -> None:
        """Compact conversation history for a session.

        Args:
            session_id: Session ID to compact.

        Note:
            This is a placeholder. Claude Agent SDK doesn't expose
            conversation compacting in the Python SDK currently.
        """
        if session_id not in ClaudeClient._session_store:
            raise ValueError(f"Session {session_id} not found")

        # Note: Compacting would be done via CLI or future SDK API
        logger.info(f"Compact requested for session: {session_id}")

    def clear_session(self, session_id: str) -> None:
        """Clear a session and its history.

        Args:
            session_id: Session ID to clear.
        """
        if session_id in ClaudeClient._session_store:
            del ClaudeClient._session_store[session_id]
            logger.info(f"Cleared session: {session_id}")

    def list_sessions(self) -> list[ClaudeSession]:
        """List all active sessions.

        Returns:
            List of ClaudeSession objects.
        """
        return list(ClaudeClient._session_store.values())

    def get_latest_session(self) -> ClaudeSession | None:
        """Get the most recently used session.

        Returns:
            ClaudeSession object or None if no sessions exist.
        """
        if not ClaudeClient._session_store:
            return None

        return max(ClaudeClient._session_store.values(), key=lambda s: s.last_used)

    @classmethod
    def get_session_count(cls) -> int:
        """Get total number of sessions in the store.

        Returns:
            Number of sessions currently stored.
        """
        return len(cls._session_store)

    @classmethod
    def get_session_by_id(cls, session_id: str) -> ClaudeSession | None:
        """Get a session by ID from the static store.

        Args:
            session_id: Session ID to retrieve.

        Returns:
            ClaudeSession object or None if not found.
        """
        return cls._session_store.get(session_id)

    @classmethod
    def clear_all_sessions(cls) -> None:
        """Clear all sessions from the static store.

        WARNING: This removes all sessions for all ClaudeClient instances.
        """
        count = len(cls._session_store)
        cls._session_store.clear()
        logger.info(f"Cleared all {count} sessions from static store")

    @classmethod
    def get_session_ids(cls) -> list[str]:
        """Get all session IDs from the static store.

        Returns:
            List of session IDs.
        """
        return list(cls._session_store.keys())
