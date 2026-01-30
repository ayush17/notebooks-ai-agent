# Data Model: Developer Assistant CLI

**Date**: 2026-01-27
**Status**: Complete

## Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐
│  ContextSource  │       │   ContextItem   │
├─────────────────┤       ├─────────────────┤
│ id: str         │──1:N──│ id: str         │
│ type: SourceType│       │ source_id: str  │
│ enabled: bool   │       │ timestamp: dt   │
│ config: dict    │       │ title: str      │
│ last_sync: dt   │       │ content: str    │
│ status: Status  │       │ metadata: dict  │
└─────────────────┘       │ relevance: float│
                          └─────────────────┘
                                  │
                                  │ N:1
                                  ▼
┌─────────────────┐       ┌─────────────────┐
│     Brief       │──1:N──│   BriefItem     │
├─────────────────┤       ├─────────────────┤
│ id: str         │       │ id: str         │
│ created_at: dt  │       │ brief_id: str   │
│ sources: list   │       │ context_item_id │
│ narrative: str  │       │ priority: int   │
│ item_count: int │       │ category: str   │
└─────────────────┘       │ summary: str    │
                          └─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│ UserPreference  │       │ SandboxInstance │
├─────────────────┤       ├─────────────────┤
│ id: str         │       │ instance_id: str│
│ category: str   │       │ name: str       │
│ keywords: list  │       │ region: str     │
│ weight: float   │       │ state: State    │
│ source: str     │       │ last_toggled: dt│
│ created_at: dt  │       └─────────────────┘
└─────────────────┘

┌─────────────────┐
│  DraftResponse  │
├─────────────────┤
│ id: str         │
│ original_msg: str│
│ source: str     │
│ draft: str      │
│ status: Status  │
│ created_at: dt  │
│ sent_at: dt?    │
└─────────────────┘
```

## Entities

### ContextSource

Represents a configured integration with an external service.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| id | str | Unique identifier | UUID, auto-generated |
| type | SourceType | Type of source | Enum: GMAIL, SLACK, JIRA, GITHUB |
| name | str | Display name | User-defined, optional |
| enabled | bool | Whether source is active | Default: true |
| config | dict | Source-specific configuration | Varies by type |
| credentials | dict | Authentication credentials | Stored in config file |
| last_sync | datetime | Last successful sync time | Nullable |
| status | ConnectionStatus | Current connection state | Enum: CONNECTED, DISCONNECTED, ERROR |
| error_message | str | Last error if status=ERROR | Nullable |

**Source-specific config fields**:

- Gmail: `scopes`, `token_file`
- Slack: `bot_token` or `user_token`, `channels` (optional filter)
- JIRA: `url`, `email`, `project_keys` (optional filter)
- GitHub: `token`, `repos` (optional filter), `include_notifications`

### ContextItem

A single piece of information retrieved from a source.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| id | str | Unique identifier | UUID, auto-generated |
| source_id | str | Reference to ContextSource | Foreign key |
| source_type | SourceType | Denormalized source type | For filtering |
| timestamp | datetime | When item was created/updated | From source |
| title | str | Brief title/subject | Max 200 chars |
| content | str | Full content/body | Nullable |
| url | str | Link to original item | Nullable |
| author | str | Who created/sent item | Nullable |
| metadata | dict | Source-specific metadata | Varies |
| relevance_score | float | Computed relevance | 0.0 to 1.0 |
| is_read | bool | Whether user has seen | Default: false |

**Source-specific metadata**:

- Gmail: `labels`, `thread_id`, `is_unread`, `attachments_count`
- Slack: `channel`, `thread_ts`, `reactions`, `is_mention`
- JIRA: `issue_key`, `status`, `priority`, `assignee`, `project`
- GitHub: `repo`, `type` (PR/issue/notification), `state`

### Brief

A generated summary aggregating multiple context items.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| id | str | Unique identifier | UUID, auto-generated |
| created_at | datetime | When brief was generated | Auto-set |
| sources_queried | list[str] | Source IDs that were queried | |
| sources_succeeded | list[str] | Source IDs that returned data | |
| sources_failed | list[str] | Source IDs that failed | |
| items | list[BriefItem] | Prioritized items | Ordered by priority |
| narrative | str | AI-generated summary text | From Gemini |
| token_count | int | Tokens used for generation | For tracking |
| generation_time_ms | int | Time to generate brief | For performance |

### BriefItem

A single item included in a brief with computed priority.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| id | str | Unique identifier | UUID |
| brief_id | str | Reference to Brief | Foreign key |
| context_item_id | str | Reference to ContextItem | Foreign key |
| priority | int | Display priority | 1 = highest |
| category | str | Categorization | e.g., "urgent", "fyi", "action" |
| summary | str | AI-generated one-liner | Max 100 chars |
| source_type | SourceType | Denormalized | For display |

### UserPreference

A learned or explicit user preference for ranking.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| id | str | Unique identifier | UUID |
| category | str | Preference category | e.g., "priority", "sender", "topic" |
| pattern | str | Matching pattern | Keyword, email, or regex |
| weight | float | Ranking weight | -1.0 to 1.0 |
| source | str | How learned | "explicit" or "inferred" |
| feedback_count | int | Times reinforced | For confidence |
| created_at | datetime | When created | |
| updated_at | datetime | Last updated | |

### SandboxInstance

An EC2 instance designation for sandbox management.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| instance_id | str | AWS EC2 instance ID | e.g., i-0abc123 |
| name | str | Friendly name | User-defined |
| region | str | AWS region | e.g., us-east-1 |
| state | InstanceState | Current state | Enum: RUNNING, STOPPED, PENDING, STOPPING |
| last_toggled | datetime | Last start/stop action | Nullable |
| auto_stop_after | int | Auto-stop after N hours | Nullable, for cost control |

### DraftResponse

A pending auto-generated response awaiting approval.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| id | str | Unique identifier | UUID |
| source_type | SourceType | Where to send | GMAIL or SLACK |
| original_message | str | The message being replied to | |
| original_context | dict | Full context for reply | Thread, channel, etc. |
| draft | str | Generated response text | |
| status | DraftStatus | Approval status | Enum: PENDING, APPROVED, REJECTED, SENT |
| created_at | datetime | When draft created | |
| reviewed_at | datetime | When user reviewed | Nullable |
| sent_at | datetime | When sent (if approved) | Nullable |
| feedback | str | User feedback if rejected | Nullable |

## Enums

```python
class SourceType(str, Enum):
    GMAIL = "gmail"
    SLACK = "slack"
    JIRA = "jira"
    GITHUB = "github"

class ConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PENDING = "pending"  # OAuth in progress

class InstanceState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    PENDING = "pending"
    STOPPING = "stopping"

class DraftStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
```

## State Transitions

### ContextSource Status

```
DISCONNECTED ──[configure]──> PENDING ──[auth success]──> CONNECTED
                                │                              │
                                └──[auth fail]──> ERROR        │
                                                               │
CONNECTED ──[token expired]──> ERROR ──[re-auth]──> CONNECTED  │
     │                                                         │
     └──[user disable]──> DISCONNECTED <──[user remove]────────┘
```

### DraftResponse Status

```
[created] ──> PENDING ──[user approves]──> APPROVED ──[send success]──> SENT
                │
                └──[user rejects]──> REJECTED
```

### SandboxInstance State

```
STOPPED ──[start command]──> PENDING ──[AWS confirms]──> RUNNING
                                                             │
RUNNING ──[stop command]──> STOPPING ──[AWS confirms]──> STOPPED
```

## Storage Format

All entities are stored as JSON in the workspace directory:

```
~/.devassist/
├── config.yaml          # User configuration
├── sources/
│   └── sources.json     # ContextSource records
├── cache/
│   ├── gmail/
│   │   └── {hash}.json  # Cached ContextItems
│   ├── slack/
│   ├── jira/
│   └── github/
├── briefs/
│   └── {date}/
│       └── {id}.json    # Historical briefs
├── preferences/
│   └── preferences.json # UserPreference records
├── drafts/
│   └── {id}.json        # DraftResponse records
└── sandboxes/
    └── instances.json   # SandboxInstance records
```
