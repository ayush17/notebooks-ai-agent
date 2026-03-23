"""Slack client for DevAssist notifications and messaging.

Provides functionality to send direct messages and notifications via Slack API.
"""

import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class SlackClient:
    """Client for Slack API operations."""

    def __init__(self):
        """Initialize Slack client using environment variables.

        Environment variables:
            SLACK_BOT_TOKEN: Slack bot token (xoxb-...)
            SLACK_USER_TOKEN: Slack user token (xoxp-...)
        """
        self.bot_token = os.getenv('SLACK_BOT_TOKEN', "")
        self.user_token = os.getenv('SLACK_USER_TOKEN', "")

        if not self.bot_token and not self.user_token:
            raise ValueError(
                "No Slack token provided. Set SLACK_BOT_TOKEN or SLACK_USER_TOKEN environment variable."
            )

        # Use bot token by default, fall back to user token
        self.token = self.bot_token or self.user_token
        self._client = None

    def _get_client(self):
        """Get or create Slack WebClient instance."""
        if self._client is None:
            try:
                from slack_sdk import WebClient
                self._client = WebClient(token=self.token)
                logger.debug("Initialized Slack WebClient")
            except ImportError:
                raise ImportError(
                    "slack_sdk is required for Slack functionality. "
                    "Install with: pip install slack_sdk"
                )
        return self._client

    async def send_direct_message(self, user_id: str, text: str, blocks: list[dict] | None = None) -> dict[str, Any]:
        """Send a direct message to a user.

        Args:
            user_id: Slack user ID (e.g., U1234567890) or @username
            text: Plain text message content
            blocks: Optional Slack Block Kit blocks for rich formatting

        Returns:
            Slack API response

        Raises:
            Exception: If message sending fails
        """
        client = self._get_client()

        try:
            # Open DM channel with user
            dm_response = client.conversations_open(users=user_id)
            channel_id = dm_response["channel"]["id"]

            # Send message
            response = client.chat_postMessage(
                channel=channel_id,
                text=text,
                blocks=blocks
            )

            logger.info(f"Sent DM to {user_id}: {text[:50]}...")
            return response.data

        except Exception as e:
            logger.error(f"Failed to send DM to {user_id}: {e}")
            raise

    async def send_to_self(self, text: str, blocks: list[dict] | None = None) -> dict[str, Any]:
        """Send a direct message to yourself.

        Args:
            text: Plain text message content
            blocks: Optional Slack Block Kit blocks for rich formatting

        Returns:
            Slack API response
        """
        client = self._get_client()

        try:
            # Get current user info to send to self
            auth_response = client.auth_test()
            user_id = auth_response["user_id"]

            return await self.send_direct_message(user_id, text, blocks)

        except Exception as e:
            logger.error(f"Failed to send DM to self: {e}")
            raise

    async def send_devassist_notification(self, content: str, title: str = "DevAssist Update") -> dict[str, Any]:
        """Send a formatted DevAssist notification to yourself.

        Args:
            content: The main notification content
            title: Notification title
            user_id: Id of the user you want to sent the message to

        Returns:
            Slack API response
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Create rich blocks for better formatting
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🤖 {title}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Generated at:* {timestamp}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": content
                }
            }
        ]

        # Fallback text for notifications
        fallback_text = f"{title}: {content[:100]}..." if len(content) > 100 else content
        if self.user_token:
            logger.info("Sending message to self")
            return await self.send_to_self(fallback_text, blocks)
        else:
            user_id = os.getenv("SLACK_USER_ID")
            if not user_id:
                raise RuntimeError("Please set 'SLACK_USER_ID' environment variable")
            return await self.send_direct_message(user_id=user_id, text=fallback_text, blocks=blocks)


    def get_user_id_by_name(self, user_name: str):
        try:
            # Call the users.list API method
            response = self._get_client().users_list()
            if response["ok"]:
                users = response["members"]
                for user in users:
                    # Check display name or real name
                    if user.get("profile", {}).get("display_name") == user_name or user.get("real_name") == user_name:
                        return user["id"]
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None

    def get_user_id(self) -> str:
        """Get current user's Slack ID.

        Returns:
            Current user's Slack user ID
        """
        client = self._get_client()

        try:
            auth_response = client.auth_test()
            return auth_response["user_id"]
        except Exception as e:
            logger.error(f"Failed to get user ID: {e}")
            raise

    def test_connection(self) -> bool:
        """Test Slack connection and authentication.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            client = self._get_client()
            auth_response = client.auth_test()
            user = auth_response.get("user", "Unknown")
            team = auth_response.get("team", "Unknown")
            logger.info(f"Slack connection successful - User: {user}, Team: {team}")
            return True
        except Exception as e:
            logger.error(f"Slack connection failed: {e}")
            return False