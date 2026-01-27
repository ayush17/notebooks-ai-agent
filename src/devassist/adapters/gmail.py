"""Gmail adapter for DevAssist.

Implements OAuth2-based Gmail integration for fetching emails.
"""

import base64
from collections.abc import AsyncIterator
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from devassist.adapters.base import ContextSourceAdapter
from devassist.adapters.errors import AuthenticationError, SourceUnavailableError
from devassist.models.context import ContextItem, SourceType

# Google API imports - these are optional and checked at runtime
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    InstalledAppFlow = None  # type: ignore
    build = None  # type: ignore
    Credentials = None  # type: ignore
    Request = None  # type: ignore


# Gmail API scopes
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailAdapter(ContextSourceAdapter):
    """Adapter for Gmail using OAuth2 authentication."""

    def __init__(self) -> None:
        """Initialize GmailAdapter."""
        self._creds: Any = None
        self._service: Any = None
        self._token_path: Path | None = None

    @property
    def source_type(self) -> SourceType:
        """Get source type."""
        return SourceType.GMAIL

    @property
    def display_name(self) -> str:
        """Get display name."""
        return "Gmail"

    @classmethod
    def get_required_config_fields(cls) -> list[str]:
        """Get required configuration fields."""
        return ["credentials_file"]

    async def authenticate(self, config: dict[str, Any]) -> bool:
        """Authenticate with Gmail using OAuth2.

        Args:
            config: Must contain 'credentials_file' path to OAuth client secrets.

        Returns:
            True if authentication succeeded.

        Raises:
            AuthenticationError: If OAuth flow fails.
        """
        if not GOOGLE_API_AVAILABLE:
            raise AuthenticationError(
                "Google API libraries not installed. Run: pip install google-auth-oauthlib google-api-python-client",
                source_type="gmail",
            )

        credentials_file = config.get("credentials_file")
        if not credentials_file:
            raise AuthenticationError(
                "credentials_file is required for Gmail OAuth",
                source_type="gmail",
            )

        credentials_path = Path(credentials_file)
        token_path = credentials_path.parent / "gmail_token.json"
        self._token_path = token_path

        creds = None

        # Try to load existing token
        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)
            except Exception:
                pass

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    raise AuthenticationError(
                        f"Failed to refresh Gmail token: {e}",
                        source_type="gmail",
                    ) from e
            else:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(credentials_path), GMAIL_SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    raise AuthenticationError(
                        f"Gmail OAuth flow failed: {e}",
                        source_type="gmail",
                    ) from e

            # Save credentials for next run
            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())

        self._creds = creds
        self._service = build("gmail", "v1", credentials=creds)
        return True

    async def test_connection(self) -> bool:
        """Test Gmail connection.

        Returns:
            True if connection is healthy.

        Raises:
            SourceUnavailableError: If not authenticated or connection fails.
        """
        if not self._creds:
            raise SourceUnavailableError(
                "Not authenticated. Call authenticate() first.",
                source_type="gmail",
            )

        try:
            if not self._service:
                self._service = build("gmail", "v1", credentials=self._creds)

            profile = self._service.users().getProfile(userId="me").execute()
            return "emailAddress" in profile
        except Exception as e:
            raise SourceUnavailableError(
                f"Gmail connection test failed: {e}",
                source_type="gmail",
            ) from e

    async def fetch_items(
        self,
        limit: int = 50,
        **kwargs: Any,
    ) -> AsyncIterator[ContextItem]:
        """Fetch recent emails from Gmail.

        Args:
            limit: Maximum number of emails to fetch.
            **kwargs: Additional options (e.g., query filter).

        Yields:
            ContextItem for each email.

        Raises:
            SourceUnavailableError: If fetch fails.
            AuthenticationError: If not authenticated.
        """
        if not self._creds or not self._service:
            raise AuthenticationError(
                "Not authenticated. Call authenticate() first.",
                source_type="gmail",
            )

        try:
            # Get message list
            query = kwargs.get("query", "is:unread OR newer_than:1d")
            results = (
                self._service.users()
                .messages()
                .list(userId="me", q=query, maxResults=limit)
                .execute()
            )

            messages = results.get("messages", [])

            for msg_meta in messages[:limit]:
                msg = (
                    self._service.users()
                    .messages()
                    .get(userId="me", id=msg_meta["id"], format="full")
                    .execute()
                )

                # Parse headers
                headers = {
                    h["name"].lower(): h["value"]
                    for h in msg.get("payload", {}).get("headers", [])
                }

                subject = headers.get("subject", "(No Subject)")
                sender = headers.get("from", "Unknown")
                date_str = headers.get("date", "")

                # Parse timestamp
                try:
                    timestamp = parsedate_to_datetime(date_str)
                except Exception:
                    timestamp = datetime.now()

                # Get snippet as content
                content = msg.get("snippet", "")

                yield ContextItem(
                    id=msg["id"],
                    source_id="gmail",
                    source_type=SourceType.GMAIL,
                    timestamp=timestamp,
                    title=subject,
                    content=content,
                    author=sender,
                    url=f"https://mail.google.com/mail/u/0/#inbox/{msg['id']}",
                    metadata={
                        "labels": msg.get("labelIds", []),
                        "thread_id": msg.get("threadId"),
                    },
                    is_read="UNREAD" not in msg.get("labelIds", []),
                )

        except Exception as e:
            raise SourceUnavailableError(
                f"Failed to fetch Gmail messages: {e}",
                source_type="gmail",
            ) from e
