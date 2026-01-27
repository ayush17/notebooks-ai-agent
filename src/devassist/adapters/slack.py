"""Slack adapter for DevAssist.

Implements bot token-based Slack integration for fetching messages.
"""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import httpx

from devassist.adapters.base import ContextSourceAdapter
from devassist.adapters.errors import AuthenticationError, SourceUnavailableError
from devassist.models.context import ContextItem, SourceType


SLACK_API_BASE = "https://slack.com/api"


class SlackAdapter(ContextSourceAdapter):
    """Adapter for Slack using bot token authentication."""

    def __init__(self) -> None:
        """Initialize SlackAdapter."""
        self._token: str | None = None
        self._user_id: str | None = None

    @property
    def source_type(self) -> SourceType:
        """Get source type."""
        return SourceType.SLACK

    @property
    def display_name(self) -> str:
        """Get display name."""
        return "Slack"

    @classmethod
    def get_required_config_fields(cls) -> list[str]:
        """Get required configuration fields."""
        return ["bot_token"]

    async def authenticate(self, config: dict[str, Any]) -> bool:
        """Authenticate with Slack using bot token.

        Args:
            config: Must contain 'bot_token'.

        Returns:
            True if authentication succeeded.

        Raises:
            AuthenticationError: If token is invalid.
        """
        bot_token = config.get("bot_token")
        if not bot_token:
            raise AuthenticationError(
                "bot_token is required for Slack authentication",
                source_type="slack",
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SLACK_API_BASE}/auth.test",
                    headers={"Authorization": f"Bearer {bot_token}"},
                )

                data = response.json()
                if not data.get("ok"):
                    raise AuthenticationError(
                        f"Slack auth failed: {data.get('error', 'Unknown error')}",
                        source_type="slack",
                    )

                self._token = bot_token
                self._user_id = data.get("user_id")
                return True

        except httpx.RequestError as e:
            raise AuthenticationError(
                f"Slack connection failed: {e}",
                source_type="slack",
            ) from e

    async def test_connection(self) -> bool:
        """Test Slack connection.

        Returns:
            True if connection is healthy.

        Raises:
            SourceUnavailableError: If not authenticated or connection fails.
        """
        if not self._token:
            raise SourceUnavailableError(
                "Not authenticated. Call authenticate() first.",
                source_type="slack",
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SLACK_API_BASE}/auth.test",
                    headers={"Authorization": f"Bearer {self._token}"},
                )

                data = response.json()
                return data.get("ok", False)

        except httpx.RequestError as e:
            raise SourceUnavailableError(
                f"Slack connection test failed: {e}",
                source_type="slack",
            ) from e

    async def fetch_items(
        self,
        limit: int = 50,
        **kwargs: Any,
    ) -> AsyncIterator[ContextItem]:
        """Fetch recent messages from Slack channels.

        Args:
            limit: Maximum number of messages to fetch.
            **kwargs: Additional options (e.g., channel filter).

        Yields:
            ContextItem for each message.

        Raises:
            SourceUnavailableError: If fetch fails.
            AuthenticationError: If not authenticated.
        """
        if not self._token:
            raise AuthenticationError(
                "Not authenticated. Call authenticate() first.",
                source_type="slack",
            )

        try:
            async with httpx.AsyncClient() as client:
                # Get list of channels
                channels_response = await client.get(
                    f"{SLACK_API_BASE}/conversations.list",
                    headers={"Authorization": f"Bearer {self._token}"},
                    params={"types": "public_channel,private_channel", "limit": 20},
                )

                channels_data = channels_response.json()
                if not channels_data.get("ok"):
                    raise SourceUnavailableError(
                        f"Failed to list Slack channels: {channels_data.get('error')}",
                        source_type="slack",
                    )

                channels = channels_data.get("channels", [])
                items_yielded = 0

                for channel in channels:
                    if items_yielded >= limit:
                        break

                    channel_id = channel["id"]
                    channel_name = channel.get("name", "unknown")

                    # Get recent messages from channel
                    history_response = await client.get(
                        f"{SLACK_API_BASE}/conversations.history",
                        headers={"Authorization": f"Bearer {self._token}"},
                        params={"channel": channel_id, "limit": min(20, limit - items_yielded)},
                    )

                    history_data = history_response.json()
                    if not history_data.get("ok"):
                        continue  # Skip channels we can't read

                    messages = history_data.get("messages", [])

                    for msg in messages:
                        if items_yielded >= limit:
                            break

                        # Skip bot messages and system messages
                        if msg.get("subtype") in ["bot_message", "channel_join", "channel_leave"]:
                            continue

                        ts = msg.get("ts", "0")
                        try:
                            timestamp = datetime.fromtimestamp(float(ts))
                        except (ValueError, TypeError):
                            timestamp = datetime.now()

                        text = msg.get("text", "")
                        user = msg.get("user", "Unknown")

                        yield ContextItem(
                            id=f"{channel_id}-{ts}",
                            source_id="slack",
                            source_type=SourceType.SLACK,
                            timestamp=timestamp,
                            title=f"#{channel_name}: {text[:50]}..." if len(text) > 50 else f"#{channel_name}: {text}",
                            content=text,
                            author=user,
                            url=f"https://slack.com/app_redirect?channel={channel_id}&message_ts={ts}",
                            metadata={
                                "channel": channel_name,
                                "channel_id": channel_id,
                                "thread_ts": msg.get("thread_ts"),
                            },
                        )
                        items_yielded += 1

        except httpx.RequestError as e:
            raise SourceUnavailableError(
                f"Failed to fetch Slack messages: {e}",
                source_type="slack",
            ) from e
