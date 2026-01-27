"""Error classes for context source adapters.

Defines standard exceptions for adapter operations.
"""


class AdapterError(Exception):
    """Base exception for all adapter errors."""

    def __init__(self, message: str, source_type: str | None = None) -> None:
        """Initialize adapter error.

        Args:
            message: Error message.
            source_type: Optional source type that raised the error.
        """
        super().__init__(message)
        self.source_type = source_type


class AuthenticationError(AdapterError):
    """Raised when authentication with a source fails.

    Examples:
        - Invalid credentials
        - Expired tokens
        - OAuth flow failures
    """

    pass


class SourceUnavailableError(AdapterError):
    """Raised when a source cannot be reached.

    Examples:
        - Network errors
        - Service downtime
        - API endpoint changes
    """

    pass


class RateLimitError(AdapterError):
    """Raised when rate limits are exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying, if provided by API.
    """

    def __init__(
        self,
        message: str,
        source_type: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        """Initialize rate limit error.

        Args:
            message: Error message.
            source_type: Optional source type.
            retry_after: Optional seconds to wait before retry.
        """
        super().__init__(message, source_type)
        self.retry_after = retry_after
