"""JIRA adapter for DevAssist.

Implements API token-based JIRA integration for fetching issues.
"""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import httpx

from devassist.adapters.base import ContextSourceAdapter
from devassist.adapters.errors import AuthenticationError, SourceUnavailableError
from devassist.jira_enhanced_search import fetch_jql_search_jql_page
from devassist.models.context import ContextItem, SourceType

_JIRA_SEARCH_FIELDS = "summary,description,assignee,status,updated,priority,issuetype"


class JiraAdapter(ContextSourceAdapter):
    """Adapter for JIRA using API token authentication."""

    def __init__(self) -> None:
        """Initialize JiraAdapter."""
        self._url: str | None = None
        self._auth: tuple[str, str] | None = None

    @property
    def source_type(self) -> SourceType:
        """Get source type."""
        return SourceType.JIRA

    @property
    def display_name(self) -> str:
        """Get display name."""
        return "JIRA"

    @classmethod
    def get_required_config_fields(cls) -> list[str]:
        """Get required configuration fields."""
        return ["url", "email", "api_token"]

    async def authenticate(self, config: dict[str, Any]) -> bool:
        """Authenticate with JIRA using API token.

        Args:
            config: Must contain 'url', 'email', and 'api_token'.

        Returns:
            True if authentication succeeded.

        Raises:
            AuthenticationError: If credentials are invalid.
        """
        url = config.get("url")
        email = config.get("email")
        api_token = config.get("api_token")

        if not all([url, email, api_token]):
            raise AuthenticationError(
                "url, email, and api_token are required for JIRA authentication",
                source_type="jira",
            )

        # Normalize URL
        url = url.rstrip("/")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{url}/rest/api/3/myself",
                    auth=(email, api_token),
                )

                if response.status_code == 401:
                    raise AuthenticationError(
                        "Invalid JIRA credentials",
                        source_type="jira",
                    )

                if response.status_code != 200:
                    raise AuthenticationError(
                        f"JIRA authentication failed with status {response.status_code}",
                        source_type="jira",
                    )

                self._url = url
                self._auth = (email, api_token)
                return True

        except httpx.RequestError as e:
            raise AuthenticationError(
                f"JIRA connection failed: {e}",
                source_type="jira",
            ) from e

    async def test_connection(self) -> bool:
        """Test JIRA connection.

        Returns:
            True if connection is healthy.

        Raises:
            SourceUnavailableError: If not authenticated or connection fails.
        """
        if not self._url or not self._auth:
            raise SourceUnavailableError(
                "Not authenticated. Call authenticate() first.",
                source_type="jira",
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._url}/rest/api/3/myself",
                    auth=self._auth,
                )

                return response.status_code == 200

        except httpx.RequestError as e:
            raise SourceUnavailableError(
                f"JIRA connection test failed: {e}",
                source_type="jira",
            ) from e

    async def fetch_items(
        self,
        limit: int = 50,
        **kwargs: Any,
    ) -> AsyncIterator[ContextItem]:
        """Fetch assigned and watched issues from JIRA.

        Args:
            limit: Maximum number of issues to fetch.
            **kwargs: Additional options (e.g., jql filter).

        Yields:
            ContextItem for each issue.

        Raises:
            SourceUnavailableError: If fetch fails.
            AuthenticationError: If not authenticated.
        """
        if not self._url or not self._auth:
            raise AuthenticationError(
                "Not authenticated. Call authenticate() first.",
                source_type="jira",
            )

        try:
            # Default JQL to get assigned issues and recently updated
            jql = kwargs.get(
                "jql",
                "assignee = currentUser() OR watcher = currentUser() ORDER BY updated DESC",
            )

            async with httpx.AsyncClient() as client:
                cursor: str | None = None
                yielded = 0
                while yielded < limit:
                    page_size = min(100, limit - yielded)
                    if page_size <= 0:
                        break
                    try:
                        issues, next_cursor, page_last = await fetch_jql_search_jql_page(
                            client,
                            self._url,
                            self._auth,
                            jql=jql,
                            max_results=page_size,
                            fields=_JIRA_SEARCH_FIELDS,
                            next_page_token=cursor,
                        )
                    except httpx.HTTPStatusError as e:
                        raise SourceUnavailableError(
                            f"JIRA search failed with status {e.response.status_code}",
                            source_type="jira",
                        ) from e

                    if not issues:
                        break

                    for issue in issues:
                        if yielded >= limit:
                            break
                        key = issue["key"]
                        fields = issue.get("fields", {})

                        summary = fields.get("summary", "")
                        description = fields.get("description")
                        if isinstance(description, dict):
                            description = self._extract_text_from_adf(description)
                        elif not isinstance(description, str):
                            description = None

                        assignee = fields.get("assignee")
                        assignee_name = assignee.get("displayName") if assignee else None

                        status = fields.get("status", {}).get("name", "Unknown")
                        priority = (
                            fields.get("priority", {}).get("name") if fields.get("priority") else None
                        )
                        issue_type = fields.get("issuetype", {}).get("name", "Issue")

                        updated_str = fields.get("updated", "")
                        try:
                            timestamp = datetime.fromisoformat(
                                updated_str.replace("+0000", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            timestamp = datetime.now()

                        yielded += 1
                        yield ContextItem(
                            id=key,
                            source_id="jira",
                            source_type=SourceType.JIRA,
                            timestamp=timestamp,
                            title=f"[{key}] {summary}",
                            content=description,
                            author=assignee_name,
                            url=f"{self._url}/browse/{key}",
                            metadata={
                                "status": status,
                                "priority": priority,
                                "issue_type": issue_type,
                            },
                        )

                    if page_last or not next_cursor:
                        break
                    cursor = next_cursor

        except httpx.RequestError as e:
            raise SourceUnavailableError(
                f"Failed to fetch JIRA issues: {e}",
                source_type="jira",
            ) from e

    def _extract_text_from_adf(self, adf: dict[str, Any]) -> str:
        """Extract plain text from Atlassian Document Format.

        Args:
            adf: Atlassian Document Format dict.

        Returns:
            Extracted plain text.
        """
        if not adf or not isinstance(adf, dict):
            return ""

        content = adf.get("content", [])
        texts: list[str] = []

        for node in content:
            if node.get("type") == "paragraph":
                for text_node in node.get("content", []):
                    if text_node.get("type") == "text":
                        texts.append(text_node.get("text", ""))

        return "\n".join(texts)
