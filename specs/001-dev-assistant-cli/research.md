# Research: Developer Assistant CLI

**Date**: 2026-01-27
**Status**: Complete

## Python CLI Framework

**Decision**: Typer with Rich for terminal output

**Rationale**:
- Typer is built on Click but provides better type hints and automatic help generation
- Rich provides beautiful, readable terminal output with tables, panels, and progress indicators
- Both are actively maintained and well-documented
- Typer's decorator-based approach aligns with the command/subcommand structure in FR-001

**Alternatives Considered**:
- Click: More verbose, requires manual type annotations
- argparse: Standard library but less ergonomic for complex CLIs
- Fire: Too magical, less control over help text

## GCP Vertex AI Integration

**Decision**: google-cloud-aiplatform SDK with Gemini 1.5 Flash (default), Gemini 1.5 Pro (configurable)

**Rationale**:
- Official Google SDK with good async support
- Gemini 1.5 Flash offers good balance of speed and capability for summarization
- Gemini 1.5 Pro available for more complex reasoning tasks
- SDK handles authentication via Application Default Credentials (ADC)

**Alternatives Considered**:
- REST API directly: More boilerplate, SDK handles retries/auth better
- LangChain: Adds unnecessary abstraction layer for this use case
- Anthropic Claude: User specified Vertex AI in clarifications

## Context Source Authentication

### Gmail (OAuth2)

**Decision**: Use google-auth-oauthlib for OAuth2 flow with local redirect

**Rationale**:
- Standard Google OAuth2 flow with browser redirect to localhost
- Tokens stored in local config file (per clarification: unencrypted for dev)
- Refresh tokens handled automatically by google-auth

**Scopes Required**:
- `https://www.googleapis.com/auth/gmail.readonly` - Read emails
- `https://www.googleapis.com/auth/gmail.labels` - Read labels for filtering

### Slack (OAuth2 or Bot Token)

**Decision**: Support both OAuth2 (user token) and Bot Token (simpler)

**Rationale**:
- Bot tokens are simpler for personal use (just paste token)
- OAuth2 needed for full user context (DMs, all channels)
- Start with bot token for MVP, add OAuth2 flow later

**Scopes Required (Bot)**:
- `channels:history` - Read public channel messages
- `groups:history` - Read private channel messages
- `im:history` - Read DMs
- `users:read` - Get user info for @mentions

### JIRA (API Token)

**Decision**: Basic auth with email + API token

**Rationale**:
- Simplest authentication method for Atlassian Cloud
- API tokens are long-lived and user-controlled
- Works with both Cloud and Server/Data Center

**API Endpoints**:
- `/rest/api/3/search` - JQL search for assigned issues
- `/rest/api/3/issue/{key}` - Get issue details

### GitHub (Personal Access Token)

**Decision**: PAT with fine-grained or classic tokens

**Rationale**:
- PATs are the standard for API access
- Fine-grained tokens offer better security (repo-scoped)
- Classic tokens simpler for broad access

**Scopes Required**:
- `repo` - Access to repositories
- `notifications` - Access to notifications

## Caching Strategy

**Decision**: Local JSON files with 15-minute TTL, LRU eviction

**Rationale**:
- Simple file-based cache avoids external dependencies
- 15-minute TTL (per clarification) balances freshness and API efficiency
- LRU eviction prevents unbounded cache growth
- Cache keyed by source type + query parameters

**Implementation**:
```python
cache/
├── gmail/
│   └── {hash}.json
├── slack/
│   └── {hash}.json
├── jira/
│   └── {hash}.json
└── github/
    └── {hash}.json
```

Each cache file contains:
- `data`: Cached response
- `expires_at`: Unix timestamp (now + 900 seconds)
- `created_at`: Unix timestamp

## Context Optimization for AI

**Decision**: Use structured summarization before sending to Gemini

**Rationale**:
- Raw context from 4 sources can exceed token limits
- Pre-summarize each source to ~500 tokens before aggregation
- Use Gemini's native JSON mode for structured output
- Total context budget: ~4000 tokens for combined brief

**Approach**:
1. Fetch raw items from each source
2. Score by recency, sender importance, keyword matches
3. Select top N items per source (configurable, default 10)
4. Format as structured input for Gemini
5. Generate unified narrative brief

## Error Handling Strategy

**Decision**: Graceful degradation with detailed error reporting

**Rationale**:
- Per spec edge cases: source failures shouldn't crash the system
- Show partial results with clear indication of what failed
- Retry with exponential backoff for transient failures

**Error Categories**:
- Auth errors: Prompt for re-authentication
- Rate limits: Backoff and inform user
- Network errors: Retry up to 3 times
- Service unavailable: Skip source, note in output

## Async vs Sync Architecture

**Decision**: Async with asyncio for I/O-bound operations

**Rationale**:
- Fetching from 4 sources benefits from concurrent I/O
- httpx provides async HTTP client
- Typer supports async commands
- Vertex AI SDK supports async

**Pattern**:
```python
async def generate_brief():
    results = await asyncio.gather(
        gmail_adapter.fetch(),
        slack_adapter.fetch(),
        jira_adapter.fetch(),
        github_adapter.fetch(),
        return_exceptions=True
    )
    # Filter out exceptions, proceed with successful results
```

## Configuration File Format

**Decision**: YAML for human-readable config, JSON for cache

**Rationale**:
- YAML is easier for users to read and edit
- JSON is faster for cache serialization
- Both supported by standard Python libraries

**Config Structure**:
```yaml
# ~/.devassist/config.yaml
workspace_dir: ~/.devassist

sources:
  gmail:
    enabled: true
    credentials_file: gmail_token.json
  slack:
    enabled: true
    bot_token: xoxb-...
  jira:
    enabled: true
    url: https://company.atlassian.net
    email: user@company.com
    api_token: ...
  github:
    enabled: true
    token: ghp_...

ai:
  project_id: my-gcp-project
  location: us-central1
  model: gemini-1.5-flash

preferences:
  priority_keywords:
    - security
    - urgent
    - blocked
```

## Dependencies Summary

| Package | Purpose | Version |
|---------|---------|---------|
| typer | CLI framework | ^0.9.0 |
| rich | Terminal formatting | ^13.0.0 |
| httpx | Async HTTP client | ^0.25.0 |
| google-cloud-aiplatform | Vertex AI SDK | ^1.38.0 |
| google-auth-oauthlib | OAuth2 for Google | ^1.2.0 |
| pydantic | Data validation | ^2.5.0 |
| pyyaml | YAML config | ^6.0.0 |
| pytest | Testing | ^7.4.0 |
| pytest-asyncio | Async test support | ^0.21.0 |
