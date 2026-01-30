# Contract: Context Source Adapter

**Version**: 1.0.0
**Date**: 2026-01-27

## Overview

All context source adapters must implement this contract to ensure consistent behavior across Gmail, Slack, JIRA, and GitHub integrations.

## Abstract Base Class

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
from datetime import datetime

class ContextSourceAdapter(ABC):
    """
    Abstract base class for all context source adapters.

    Each adapter is responsible for:
    1. Authentication with the external service
    2. Fetching relevant items for the user
    3. Transforming items to ContextItem format
    4. Handling errors gracefully
    """

    @property
    @abstractmethod
    def source_type(self) -> SourceType:
        """Return the source type enum value."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for CLI output."""
        pass

    @abstractmethod
    async def authenticate(self, config: dict) -> bool:
        """
        Authenticate with the external service.

        Args:
            config: Source-specific configuration dict

        Returns:
            True if authentication successful, False otherwise

        Raises:
            AuthenticationError: If auth fails with recoverable error
        """
        pass

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """
        Test that the connection is working.

        Returns:
            ConnectionTestResult with success status and message
        """
        pass

    @abstractmethod
    async def fetch_items(
        self,
        since: datetime | None = None,
        limit: int = 50
    ) -> AsyncIterator[ContextItem]:
        """
        Fetch context items from the source.

        Args:
            since: Only fetch items after this timestamp (optional)
            limit: Maximum number of items to fetch

        Yields:
            ContextItem objects

        Raises:
            SourceUnavailableError: If service is down
            RateLimitError: If rate limited (includes retry_after)
            AuthenticationError: If credentials expired
        """
        pass

    @abstractmethod
    def get_required_config_fields(self) -> list[ConfigField]:
        """
        Return list of required configuration fields.

        Used by CLI to prompt user during setup.
        """
        pass

    async def refresh_auth(self) -> bool:
        """
        Refresh authentication tokens if supported.

        Default implementation returns False (no refresh needed).
        Override for OAuth2 sources.
        """
        return False
```

## Data Types

### ConnectionTestResult

```python
@dataclass
class ConnectionTestResult:
    success: bool
    message: str
    latency_ms: int | None = None
    user_info: str | None = None  # e.g., email for Gmail
```

### ConfigField

```python
@dataclass
class ConfigField:
    name: str
    display_name: str
    field_type: Literal["string", "secret", "oauth", "boolean", "list"]
    required: bool = True
    description: str = ""
    default: Any = None
```

### Errors

```python
class ContextSourceError(Exception):
    """Base exception for context source errors."""
    pass

class AuthenticationError(ContextSourceError):
    """Authentication failed or credentials expired."""
    recoverable: bool = True

class SourceUnavailableError(ContextSourceError):
    """External service is unavailable."""
    retry_after: int | None = None

class RateLimitError(ContextSourceError):
    """Rate limit exceeded."""
    retry_after: int  # seconds
```

## Behavior Requirements

### Authentication

1. `authenticate()` MUST NOT block for more than 30 seconds
2. `authenticate()` MUST store credentials in the provided config location
3. OAuth2 flows MUST open browser for user consent
4. OAuth2 flows MUST handle localhost redirect callback
5. `refresh_auth()` MUST be called before `fetch_items()` if tokens may be expired

### Fetching

1. `fetch_items()` MUST yield items in reverse chronological order (newest first)
2. `fetch_items()` MUST respect the `limit` parameter
3. `fetch_items()` MUST filter by `since` if provided
4. `fetch_items()` MUST set `relevance_score` between 0.0 and 1.0
5. `fetch_items()` MUST populate all required ContextItem fields
6. `fetch_items()` SHOULD complete within 30 seconds for typical workloads

### Error Handling

1. Transient errors MUST be retried up to 3 times with exponential backoff
2. Rate limits MUST raise `RateLimitError` with `retry_after`
3. Auth errors MUST raise `AuthenticationError` (caller will attempt refresh)
4. Network errors MUST raise `SourceUnavailableError`

## Implementation Checklist

For each adapter implementation:

- [ ] Implements all abstract methods
- [ ] Has unit tests with mocked API responses
- [ ] Has integration test with real API (skipped in CI)
- [ ] Handles rate limiting gracefully
- [ ] Handles token refresh (if OAuth2)
- [ ] Populates source-specific metadata
- [ ] Documents required scopes/permissions

## Source-Specific Notes

### Gmail Adapter

- Uses `google-auth-oauthlib` for OAuth2
- Fetches from `INBOX` label by default
- Filters to unread + last 24 hours for morning brief
- Relevance based on: sender, labels, thread length

### Slack Adapter

- Supports both bot token and user OAuth
- Fetches from channels user is member of
- Filters to mentions + DMs + threads user is in
- Relevance based on: @mentions, reactions, recency

### JIRA Adapter

- Uses basic auth (email + API token)
- Fetches assigned issues + watched issues
- Filters to updated in last 24 hours
- Relevance based on: priority, status change, due date

### GitHub Adapter

- Uses PAT authentication
- Fetches notifications + PRs user is involved in
- Filters to unread notifications + open PRs
- Relevance based on: @mentions, review requests, CI status
