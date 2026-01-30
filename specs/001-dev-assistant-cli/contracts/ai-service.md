# Contract: AI Service

**Version**: 1.0.0
**Date**: 2026-01-27

## Overview

The AI service contract defines how the application interacts with GCP Vertex AI (Gemini) for summarization and inference tasks.

## Interface

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class AIService(ABC):
    """
    Abstract interface for AI model interactions.

    Primary implementation: VertexAIService (Gemini)
    """

    @abstractmethod
    async def summarize_items(
        self,
        items: list[ContextItem],
        preferences: list[UserPreference] | None = None,
        max_tokens: int = 1000
    ) -> BriefSummary:
        """
        Generate a unified summary from multiple context items.

        Args:
            items: List of context items to summarize
            preferences: User preferences for prioritization
            max_tokens: Maximum tokens in response

        Returns:
            BriefSummary with narrative and categorized items
        """
        pass

    @abstractmethod
    async def generate_response(
        self,
        original_message: str,
        context: dict,
        tone: str = "professional"
    ) -> str:
        """
        Generate a draft response to a message.

        Args:
            original_message: The message to respond to
            context: Additional context (sender, thread, etc.)
            tone: Desired tone (professional, casual, brief)

        Returns:
            Generated response text
        """
        pass

    @abstractmethod
    async def extract_entities(
        self,
        text: str,
        entity_types: list[str]
    ) -> list[ExtractedEntity]:
        """
        Extract structured entities from text.

        Args:
            text: Text to analyze
            entity_types: Types to extract (person, date, task, etc.)

        Returns:
            List of extracted entities with positions
        """
        pass

    @abstractmethod
    async def health_check(self) -> AIHealthStatus:
        """
        Check if the AI service is available.

        Returns:
            Health status with latency and model info
        """
        pass
```

## Data Types

### BriefSummary

```python
@dataclass
class BriefSummary:
    narrative: str  # Main summary paragraph
    highlights: list[str]  # Top 3-5 bullet points
    action_items: list[ActionItem]  # Extracted action items
    categories: dict[str, list[str]]  # Items grouped by category
    token_usage: TokenUsage
```

### ActionItem

```python
@dataclass
class ActionItem:
    description: str
    source: str  # Which context item it came from
    due_date: datetime | None
    priority: Literal["high", "medium", "low"]
```

### TokenUsage

```python
@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

### ExtractedEntity

```python
@dataclass
class ExtractedEntity:
    text: str
    entity_type: str
    confidence: float
    start_pos: int
    end_pos: int
```

### AIHealthStatus

```python
@dataclass
class AIHealthStatus:
    available: bool
    model: str
    latency_ms: int | None
    error: str | None
```

## Vertex AI Implementation

### Configuration

```python
@dataclass
class VertexAIConfig:
    project_id: str
    location: str = "us-central1"
    model: str = "gemini-1.5-flash"  # or gemini-1.5-pro
    max_retries: int = 3
    timeout_seconds: int = 60
```

### Authentication

Uses Application Default Credentials (ADC):
1. Check for `GOOGLE_APPLICATION_CREDENTIALS` env var
2. Fall back to user credentials from `gcloud auth application-default login`
3. If running on GCP, use metadata server

### Model Selection

| Use Case | Model | Rationale |
|----------|-------|-----------|
| Morning Brief | gemini-1.5-flash | Fast, cost-effective for summarization |
| Complex Analysis | gemini-1.5-pro | Better reasoning for nuanced tasks |
| Response Draft | gemini-1.5-flash | Speed for interactive use |

### Prompt Templates

#### Morning Brief Prompt

```text
You are a helpful assistant summarizing a developer's daily context.

Given the following items from various sources (email, Slack, JIRA, GitHub),
create a concise morning brief that:

1. Highlights the 3-5 most important items requiring attention
2. Groups remaining items by category (urgent, follow-up, FYI)
3. Extracts any action items with deadlines
4. Uses a professional but friendly tone

User preferences:
{preferences}

Context items:
{items_json}

Respond in JSON format:
{
  "narrative": "...",
  "highlights": ["...", "..."],
  "action_items": [{"description": "...", "source": "...", "priority": "..."}],
  "categories": {"urgent": [...], "follow_up": [...], "fyi": [...]}
}
```

#### Response Draft Prompt

```text
Draft a response to the following message.

Original message:
{original_message}

Context:
- Sender: {sender}
- Platform: {platform}
- Thread context: {thread_context}

Tone: {tone}

Requirements:
- Be concise but complete
- Address all points raised
- Professional language
- No placeholder text like [YOUR NAME]

Draft:
```

## Error Handling

### Errors

```python
class AIServiceError(Exception):
    """Base exception for AI service errors."""
    pass

class ModelUnavailableError(AIServiceError):
    """Model endpoint is unavailable."""
    pass

class QuotaExceededError(AIServiceError):
    """API quota exceeded."""
    retry_after: int | None = None

class InvalidResponseError(AIServiceError):
    """Model returned invalid/unparseable response."""
    pass

class ContextTooLongError(AIServiceError):
    """Input context exceeds model limits."""
    token_count: int
    max_tokens: int
```

### Retry Strategy

1. Retry transient errors (5xx) up to 3 times
2. Exponential backoff: 1s, 2s, 4s
3. No retry for quota exceeded (propagate to caller)
4. No retry for invalid response (log and return partial result)

## Context Optimization

To stay within token limits:

1. **Pre-filter**: Only include items with relevance_score > 0.3
2. **Truncate**: Limit each item's content to 500 chars
3. **Prioritize**: Include high-relevance items first
4. **Budget**: Reserve 2000 tokens for response, rest for context
5. **Fallback**: If still over limit, summarize each source separately first

### Token Budget

| Component | Budget |
|-----------|--------|
| System prompt | 200 tokens |
| Preferences | 100 tokens |
| Context items | 3500 tokens |
| Response | 2000 tokens |
| **Total** | ~6000 tokens |

## Testing

### Unit Tests

- Mock Vertex AI responses
- Test prompt formatting
- Test response parsing
- Test error handling

### Integration Tests

- Real API calls (requires credentials)
- Marked as `@pytest.mark.integration`
- Skipped in CI unless explicitly enabled
