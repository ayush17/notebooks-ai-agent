"""GitHub adapter for DevAssist.

Implements PAT-based GitHub integration for fetching notifications and activity.
"""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import httpx

from devassist.adapters.base import ContextSourceAdapter
from devassist.adapters.errors import AuthenticationError, SourceUnavailableError
from devassist.models.context import ContextItem, SourceType


GITHUB_API_BASE = "https://api.github.com"


class GitHubAdapter(ContextSourceAdapter):
    """Adapter for GitHub using Personal Access Token authentication."""

    def __init__(self) -> None:
        """Initialize GitHubAdapter."""
        self._token: str | None = None
        self._username: str | None = None

    @property
    def source_type(self) -> SourceType:
        """Get source type."""
        return SourceType.GITHUB

    @property
    def display_name(self) -> str:
        """Get display name."""
        return "GitHub"

    @classmethod
    def get_required_config_fields(cls) -> list[str]:
        """Get required configuration fields."""
        return ["personal_access_token"]

    async def authenticate(self, config: dict[str, Any]) -> bool:
        """Authenticate with GitHub using PAT.

        Args:
            config: Must contain 'personal_access_token'.

        Returns:
            True if authentication succeeded.

        Raises:
            AuthenticationError: If token is invalid.
        """
        token = config.get("personal_access_token")
        if not token:
            raise AuthenticationError(
                "personal_access_token is required for GitHub authentication",
                source_type="github",
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GITHUB_API_BASE}/user",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )

                if response.status_code == 401:
                    raise AuthenticationError(
                        "Invalid GitHub token",
                        source_type="github",
                    )

                if response.status_code != 200:
                    raise AuthenticationError(
                        f"GitHub authentication failed with status {response.status_code}",
                        source_type="github",
                    )

                data = response.json()
                self._token = token
                self._username = data.get("login")
                return True

        except httpx.RequestError as e:
            raise AuthenticationError(
                f"GitHub connection failed: {e}",
                source_type="github",
            ) from e

    async def test_connection(self) -> bool:
        """Test GitHub connection.

        Returns:
            True if connection is healthy.

        Raises:
            SourceUnavailableError: If not authenticated or connection fails.
        """
        if not self._token:
            raise SourceUnavailableError(
                "Not authenticated. Call authenticate() first.",
                source_type="github",
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GITHUB_API_BASE}/user",
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )

                return response.status_code == 200

        except httpx.RequestError as e:
            raise SourceUnavailableError(
                f"GitHub connection test failed: {e}",
                source_type="github",
            ) from e

    async def fetch_items(
        self,
        limit: int = 50,
        **kwargs: Any,
    ) -> AsyncIterator[ContextItem]:
        """Fetch notifications and activity from GitHub.

        Args:
            limit: Maximum number of items to fetch.
            **kwargs: Additional options.

        Yields:
            ContextItem for each notification.

        Raises:
            SourceUnavailableError: If fetch fails.
            AuthenticationError: If not authenticated.
        """
        if not self._token:
            raise AuthenticationError(
                "Not authenticated. Call authenticate() first.",
                source_type="github",
            )

        try:
            async with httpx.AsyncClient() as client:
                # Fetch notifications
                response = await client.get(
                    f"{GITHUB_API_BASE}/notifications",
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={"per_page": limit},
                )

                if response.status_code != 200:
                    raise SourceUnavailableError(
                        f"GitHub notifications fetch failed with status {response.status_code}",
                        source_type="github",
                    )

                notifications = response.json()

                for notif in notifications[:limit]:
                    subject = notif.get("subject", {})
                    repo = notif.get("repository", {})

                    title = subject.get("title", "")
                    subject_type = subject.get("type", "Unknown")
                    repo_name = repo.get("full_name", "")
                    reason = notif.get("reason", "")

                    updated_str = notif.get("updated_at", "")
                    try:
                        timestamp = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        timestamp = datetime.now()

                    # Build URL based on subject type
                    subject_url = subject.get("url", "")
                    html_url = self._api_url_to_html(subject_url, repo_name, subject_type)

                    yield ContextItem(
                        id=notif.get("id", ""),
                        source_id="github",
                        source_type=SourceType.GITHUB,
                        timestamp=timestamp,
                        title=f"[{subject_type}] {repo_name}: {title}",
                        content=f"Reason: {reason}",
                        author=repo_name,
                        url=html_url,
                        metadata={
                            "type": subject_type,
                            "reason": reason,
                            "repository": repo_name,
                            "unread": notif.get("unread", False),
                        },
                        is_read=not notif.get("unread", True),
                    )

        except httpx.RequestError as e:
            raise SourceUnavailableError(
                f"Failed to fetch GitHub notifications: {e}",
                source_type="github",
            ) from e

    def _api_url_to_html(self, api_url: str, repo_name: str, subject_type: str) -> str:
        """Convert GitHub API URL to web URL.

        Args:
            api_url: GitHub API URL.
            repo_name: Full repository name.
            subject_type: Type of subject (Issue, PullRequest, etc.).

        Returns:
            HTML URL for the resource.
        """
        if not api_url:
            return f"https://github.com/{repo_name}"

        # Extract issue/PR number from API URL
        # API URL format: https://api.github.com/repos/owner/repo/issues/123
        parts = api_url.split("/")
        if len(parts) >= 2:
            number = parts[-1]
            if subject_type == "PullRequest":
                return f"https://github.com/{repo_name}/pull/{number}"
            elif subject_type == "Issue":
                return f"https://github.com/{repo_name}/issues/{number}"

        return f"https://github.com/{repo_name}"
