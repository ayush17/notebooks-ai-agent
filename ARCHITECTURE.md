# Singlarity (DevAssist) - Architecture Documentation

## Overview

Singlarity is a Python CLI application that aggregates context from multiple developer tools and uses Claude Agent SDK to generate unified morning briefs. The architecture follows a modern, self-contained design with minimal dependencies and clear separation of concerns.

## Architecture Principles

### 🎯 **Self-Contained Components**
- Each component manages its own configuration and state
- Minimal external dependencies between components
- Clear, explicit interfaces

### 🔧 **Unified Configuration**
- Single `ClientConfig` class handles all configuration needs
- Smart deserialization from CLI inputs, environment variables, and files
- User-friendly parameter mapping

### 📦 **Static Session Management**
- Sessions persist for the entire Python process lifetime
- Shared across all component instances
- No external storage dependencies

### 🔌 **MCP-Based Context Sources**
- Uses Model Context Protocol (MCP) servers instead of custom adapters
- Configured through ClientConfig with environment variable substitution
- Currently supports JIRA and GitHub with extensible architecture

## Core Components

### 1. Configuration Layer

#### **ClientConfig** (`src/devassist/models/config.py`)
*The heart of the unified architecture*

```python
config = ClientConfig(
    sources=['jira', 'github'],
    ai_model='Sonnet 4',           # User-friendly names
    ai_timeout_seconds=120,
    output_format='markdown'
)
```

**Key Features:**
- **Smart Deserialization**: Converts strings to proper types automatically
- **User-Friendly AI Models**: Maps "Sonnet 4" → "claude-sonnet-4-5@20250929"
- **Auto-Discovery**: Finds available sources from MCP configuration
- **Environment Integration**: Supports env vars with `DEVASSIST_*` prefix
- **File Integration**: Loads from `~/.devassist/config.yaml`
- **Validation**: Ensures valid combinations and clamped values

### 2. AI Integration Layer

#### **ClaudeClient** (`src/devassist/ai/claude_client.py`)
*Self-contained Claude Agent SDK wrapper*

```python
client = ClaudeClient(config)
response = await client.make_call("Generate my brief", session_id="session-123")
```

**Key Features:**
- **Static Session Store**: `_session_store` persists across all instances
- **MCP Server Integration**: Configures servers from ClientConfig
- **Session Management**: Create, resume, list, and clear sessions
- **SDK Abstraction**: Wraps Claude Agent SDK complexity
- **Automatic Authentication**: No manual API key setup required

**Session Management:**
```python
# List all sessions across any client instance
sessions = client.list_sessions()
session_count = ClaudeClient.get_session_count()

# Get specific session by ID
session = ClaudeClient.get_session_by_id("session-123")

# Sessions persist until Python process ends
client1 = ClaudeClient(config)
client2 = ClaudeClient(config)
# Both see the same sessions!
```

### 3. Business Logic Layer

#### **BriefGenerator** (`src/devassist/core/brief_generator.py`)
*Orchestrates brief generation workflow*

```python
generator = BriefGenerator(config=config)
brief = await generator.generate(sources=['jira', 'github'])
```

**Simplified Dependencies:**
- Takes `ClientConfig` directly (no manager classes)
- Uses ClaudeClient for AI calls
- Leverages static session store for continuity

### 3.5. Background Runner Layer

#### **Runner** (`src/devassist/core/runner.py`)
*Automated background AI execution*

```python
runner = Runner(config=config, interval_minutes=5)
await runner.run()  # Runs until stopped
```

**Key Features:**
- **Scheduled Execution**: Configurable interval-based processing
- **ClaudeClient Integration**: Uses same AI infrastructure as briefs
- **Signal Handling**: Graceful shutdown on SIGTERM/SIGINT
- **File Output**: Writes results to configured destination
- **Error Recovery**: Continues running even if individual executions fail

#### **RunnerManager** (`src/devassist/core/runner_manager.py`)
*Process lifecycle management*

```python
manager = RunnerManager()
manager.start(interval=10, prompt="Custom prompt")
status = manager.get_status()
manager.stop()
```

**Key Features:**
- **PID Management**: Tracks background process lifecycle
- **Process Monitoring**: Checks if runner is alive
- **Graceful Shutdown**: SIGTERM with SIGKILL fallback
- **Lock Files**: Prevents multiple runners

### 4. Presentation Layer

#### **CLI Commands** (`src/devassist/cli/`)
*Typer-based command interface*

```bash
# Modern workflow
devassist status                    # Shows ClientConfig status
devassist brief --sources jira,github
devassist brief --session-id session-123
devassist brief clean --days 7     # Uses ClaudeClient directly

# Background AI runner
devassist ai run --interval 10     # Start background runner
devassist ai status                 # Check runner status
devassist ai output                 # View latest output
devassist ai kill                   # Stop runner
```

## Data Flow

### Morning Brief Generation
```
User CLI Command
    ↓
ClientConfig (unified configuration)
    ↓
BriefGenerator (orchestration)
    ↓
ClaudeClient (AI calls via Claude Agent SDK)
    ↓
MCP Servers (JIRA, GitHub)
    ↓
Claude Agent SDK (AI processing)
    ↓
Brief Model (structured response)
    ↓
Rich Console (formatted output)
```

### Background Runner Flow
```
devassist ai run
    ↓
RunnerManager (process lifecycle)
    ↓
Background Process (detached)
    ↓
Runner (scheduled execution)
    ↓
ClientConfig → ClaudeClient → MCP Servers
    ↓
File Output (~/.devassist/runner-output.md)
```

### Session Management Flow
```
ClaudeClient.create_session()
    ↓
Static Session Store (shared across instances)
    ↓
make_call(session_id=...)
    ↓
Claude Agent SDK (with session context)
    ↓
Response + Updated Session State
```

## Configuration Management

### Priority Order (Highest to Lowest)
1. **CLI Arguments**: `--sources gmail,slack`
2. **Environment Variables**: `DEVASSIST_AI_MODEL=fast`
3. **Configuration Files**: `~/.devassist/config.yaml`
4. **Defaults**: Sensible fallbacks

### Configuration Examples

#### CLI Arguments
```bash
devassist brief \
  --sources jira,github \
  --model "Opus 4" \
  --timeout 180 \
  --output json
```

#### Environment Variables
```bash
export DEVASSIST_AI_MODEL="fast"
export DEVASSIST_SOURCES="jira,github"
export DEVASSIST_AI_TIMEOUT_SECONDS=120
```

#### Configuration File (`~/.devassist/config.yaml`)
```yaml
ai_model: "Sonnet 4"
sources: ["jira", "github"]
ai_timeout_seconds: 120
output_format: "markdown"
source_configs:
  jira:
    enabled: true
    url: "https://yourcompany.atlassian.net"
    username: "your-email@company.com"
  github:
    enabled: true
    token: "your-github-token"
```

## MCP Server Integration

### Server Configuration
MCP servers are configured through the resources module and ClientConfig:

```json
# resources/mcp-servers.json
{
  "jira": {
    "type": "stdio",
    "command": "docker",
    "args": [
      "run", "-i", "--rm",
      "-e", "JIRA_URL",
      "-e", "JIRA_USERNAME",
      "-e", "JIRA_PERSONAL_TOKEN",
      "ghcr.io/sooperset/mcp-atlassian:latest"
    ],
    "env": {
      "JIRA_URL": "",
      "JIRA_USERNAME": "",
      "JIRA_PERSONAL_TOKEN": ""
    }
  },
  "github": {
    "type": "stdio",
    "command": "docker",
    "args": [
      "run", "-i", "--rm",
      "-e", "GITHUB_TOKEN",
      "quay.io/nsingla/mcp-github-readonly:latest"
    ],
    "env": {
      "GITHUB_TOKEN": ""
    }
  }
}
```

### Environment Variable Substitution
ClientConfig automatically maps environment variables to MCP configs:
- `${JIRA_URL}` → JIRA instance URL
- `${JIRA_USERNAME}` → JIRA username
- `${JIRA_PERSONAL_TOKEN}` → JIRA API token
- `${GITHUB_TOKEN}` → GitHub personal access token

## Storage & Persistence

### Session Storage
- **Location**: In-memory static dictionary
- **Lifetime**: Entire Python process
- **Sharing**: Across all ClaudeClient instances
- **Persistence**: No disk storage (sessions don't survive restarts)

### Configuration Storage
- **Location**: `~/.devassist/config.yaml`
- **Format**: YAML with validation
- **Merging**: CLI args > env vars > files > defaults

### Cache Storage (Legacy)
The old cache system has been deprecated. MCP servers handle their own caching as needed.

## Error Handling & Resilience

### Graceful Degradation
- **Source Failures**: Continue with available sources, report failures
- **AI Unavailable**: Fallback to raw data presentation
- **Rate Limiting**: Exponential backoff with user notification
- **Token Expiration**: Clear error messages with re-authentication guidance

### Exception Hierarchy
- `AuthenticationError`: Invalid credentials
- `SourceUnavailableError`: Service outages
- `RateLimitError`: API limits exceeded
- `ConfigurationError`: Invalid settings

## Performance Characteristics

### Targets
- **Brief Generation**: < 60 seconds for 4 sources
- **Session Startup**: < 2 seconds
- **Memory Usage**: < 100MB typical

### Optimization Strategies
- **Parallel Fetching**: MCP servers run concurrently
- **Session Reuse**: Avoid recreation overhead
- **Smart Defaults**: Minimal configuration required

## Security Considerations

### Credential Management
- **Environment Variables**: Preferred for production
- **File Storage**: Development convenience only
- **No Hardcoding**: Never embed secrets in code
- **MCP Isolation**: Each server handles its own auth

### Permission Model
- **Claude SDK**: Configurable permission modes
- **MCP Servers**: Sandboxed execution
- **Local Files**: Standard filesystem permissions

## Migration from Legacy Architecture

### What Changed
- ❌ **ConfigManager** → ✅ **ClientConfig**
- ❌ **SessionManager** → ✅ **ClaudeClient static sessions**
- ❌ **CacheManager** → ✅ **MCP server caching**
- ❌ **Custom Adapters** → ✅ **MCP servers**
- ❌ **Multiple Config Classes** → ✅ **Single ClientConfig**
- ❌ **Manual Claude API keys** → ✅ **Claude Agent SDK automatic auth**
- ✅ **NEW**: Background AI runner with process management

### Migration Benefits
- **50% fewer classes**: Simpler architecture
- **Zero external dependencies**: For session/config management
- **Better testing**: Easier to mock and test
- **User experience**: More intuitive configuration

## Development Workflow

### Testing Strategy
- **Unit Tests**: 45+ passing tests with comprehensive coverage
- **Integration Tests**: Real MCP server connections
- **Contract Tests**: Validate interfaces
- **Performance Tests**: Brief generation timing

### Code Organization
```
src/devassist/
├── ai/                    # Claude Agent SDK integration
│   ├── claude_client.py   # ClaudeClient with session management
│   └── prompts.py         # AI prompt templates
├── cli/                   # Command-line interface
│   ├── main.py           # Entry point and status
│   ├── brief.py          # Brief generation commands
│   ├── ai.py             # Background runner commands
│   └── prompt.py         # Prompt management
├── core/                  # Business logic
│   ├── brief_generator.py # BriefGenerator
│   ├── runner.py         # Background AI runner
│   └── runner_manager.py # Process management
├── models/                # Data models
│   ├── config.py         # ClientConfig (unified)
│   ├── mcp_config.py     # MCP server configs
│   ├── brief.py          # Brief structures
│   └── context.py        # Context types and enums
├── resources/             # Static resources
│   ├── mcp-servers.json  # MCP server configs
│   └── personal-assistant.md # System prompt
└── utils/                 # Utility functions
    └── process.py        # Process management
```

## Future Extensibility

### Adding New Sources
1. Add MCP server configuration to resources
2. Update SourceType enum in context.py
3. Configure environment variable mapping
4. No code changes required!

### Custom AI Models
1. Add model mapping to AppConfig.MODEL_MAPPING
2. Users can immediately use friendly names
3. Technical IDs handled automatically

### Session Persistence
If needed, can extend ClaudeClient to save/restore sessions from disk while maintaining the static store pattern.

## Detailed Technical Architecture

### Brief Generation Technical Flow

```mermaid
flowchart TD
    A[User runs: devassist brief] --> B[CLI brief.py]
    B --> C[ClientConfig]
    C --> D[BriefGenerator]
    D --> E[ClaudeClient]
    E --> F[Claude Session Management]

    F --> G{Session Exists?}
    G -->|Yes| H[Resume Session]
    G -->|No| I[Create New Session]

    H --> J[ClaudeSession Object]
    I --> J
    J --> K[Initialize Claude SDK Client]
    K --> L[Configure MCP Servers]

    L --> M[JIRA MCP Server]
    L --> N[GitHub MCP Server]
    L --> O[Future: Gmail MCP Server]

    M --> P[Claude Agent SDK]
    N --> P
    O --> P

    P --> Q[Claude API Call]
    Q --> R[AI Processing]
    R --> S[Generated Response]
    S --> T[Parse to Brief Model]
    T --> U[Rich Console Output]

    style A fill:#e1f5fe
    style E fill:#fff3e0
    style P fill:#f3e5f5
    style U fill:#e8f5e8
```

### Background AI Runner Technical Flow

```mermaid
flowchart TD
    A[User runs: devassist ai run] --> B[CLI ai.py]
    B --> C[RunnerManager]
    C --> D{Background Mode?}

    D -->|Yes| E[Create Subprocess]
    D -->|No| F[Run in Foreground]

    E --> G[Environment Variables]
    G --> H[DEVASSIST_RUNNER_INTERVAL]
    G --> I[DEVASSIST_RUNNER_PROMPT]
    G --> J[DEVASSIST_RUNNER_SESSION_ID]
    G --> K[DEVASSIST_RUNNER_ENABLE_SLACK]

    E --> L[Subprocess: run_background_runner]
    F --> M[Direct Runner Creation]

    L --> N[Read Env Variables]
    N --> O[ClientConfig]
    O --> P[Runner Object]
    M --> P

    P --> Q[Session Management]
    Q --> R{Session ID Provided?}
    R -->|Yes| S[Read from runner-session.txt]
    R -->|No| T[Create New Session]

    S --> U[Runner Execution Loop]
    T --> U
    U --> V[ClaudeClient.make_call]
    V --> W[Claude SDK Integration]
    W --> X[MCP Servers]
    X --> Y[Response Processing]
    Y --> Z[Write to Output File]
    Z --> AA[Optional: Slack Notification]

    style A fill:#e1f5fe
    style C fill:#fff3e0
    style P fill:#f3e5f5
    style Z fill:#e8f5e8
```

### Claude Client Session Management

```mermaid
flowchart TD
    A[ClaudeClient.make_call] --> B{session_id provided?}

    B -->|Yes| C{session_id in _session_store?}
    B -->|No| D[Use client.session]

    C -->|Yes| E[Use Existing Session]
    C -->|No| F[Subprocess Context]

    F --> G[Create Session Object]
    G --> H[session_id from parameter]
    H --> I[Initialize SDK Client]
    I --> J[Configure MCP Servers]
    J --> K[Store in _session_store]

    E --> L[Get SDK Client from session.metadata]
    D --> L
    K --> L

    L --> M[Check SDK Connection]
    M --> N{Connected?}
    N -->|No| O[sdk_client.connect]
    N -->|Yes| P[sdk_client.query]
    O --> P

    P --> Q[sdk_client.receive_response]
    Q --> R[Process Messages]
    R --> S{Messages Received?}
    S -->|Yes| T[Join Response Parts]
    S -->|No| U[Return Validation Message]

    T --> V[Update Session Stats]
    U --> W[Log Warning]
    V --> X[Return Response]
    W --> X

    style A fill:#e1f5fe
    style F fill:#fff3e0
    style I fill:#f3e5f5
    style X fill:#e8f5e8
```

### MCP Server Integration Sequence

```mermaid
sequenceDiagram
    participant CLI as CLI Command
    participant Config as ClientConfig
    participant Client as ClaudeClient
    participant SDK as Claude Agent SDK
    participant MCP_J as JIRA MCP Server
    participant MCP_G as GitHub MCP Server
    participant Claude as Claude API

    CLI->>Config: Load configuration
    Config->>Client: Initialize with MCP servers
    Client->>SDK: Create SDK client with MCP config

    SDK->>MCP_J: Connect to JIRA server
    MCP_J-->>SDK: Connection established
    SDK->>MCP_G: Connect to GitHub server
    MCP_G-->>SDK: Connection established

    Client->>SDK: send query with user prompt
    SDK->>Claude: Forward prompt with MCP context

    Claude->>MCP_J: Fetch JIRA issues
    MCP_J-->>Claude: Return JIRA data
    Claude->>MCP_G: Fetch GitHub PRs
    MCP_G-->>Claude: Return GitHub data

    Claude-->>SDK: Generate response with context
    SDK-->>Client: Return formatted response
    Client-->>CLI: Display to user
```

### Session Persistence Across Processes

```mermaid
flowchart LR
    A[Parent Process] --> B[ClaudeClient._session_store]
    B --> C[session-abc123]

    A --> D[Start Background Runner]
    D --> E[Subprocess Created]
    E --> F[Environment Variables]
    F --> G[DEVASSIST_RUNNER_SESSION_ID=session-abc123]

    E --> H[New Python Process]
    H --> I[Empty _session_store]
    I --> J[Read session_id from env]
    J --> K[Create Session Object]
    K --> L[session_id = session-abc123]
    L --> M[New SDK Client with MCP]
    M --> N[Store in _session_store]
    N --> O[Session Continuity Achieved]

    C --> P[Save to runner-session.txt]
    P --> Q[File-based Persistence]
    Q --> R[Next Process Startup]
    R --> S[Read from File]
    S --> K

    style A fill:#e1f5fe
    style H fill:#fff3e0
    style O fill:#e8f5e8
```

## Conclusion

The new architecture represents a significant simplification while maintaining all functionality:
- **Unified Configuration**: Single source of truth
- **Self-Contained Components**: Minimal dependencies
- **Modern Patterns**: Static sessions, smart deserialization
- **MCP Integration**: Industry-standard context servers
- **Developer Experience**: Intuitive and maintainable

This architecture scales from simple single-source usage to complex multi-source enterprise deployments while remaining easy to understand and extend.