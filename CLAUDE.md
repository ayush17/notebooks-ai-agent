# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Singlarity** (DevAssist) is a Python CLI application that aggregates context from multiple developer tools (Gmail, Slack, JIRA, GitHub) and uses **Claude Agent SDK** to generate intelligent morning briefs. The project uses **Model Context Protocol (MCP) servers** for context sources and features a **unified AppConfig architecture** with **static session management**.

## Development Commands

### Setup

Use [uv](https://docs.astral.sh/uv/) for reproducible installs (`uv.lock`, `.python-version`).

```bash
# Install uv: https://docs.astral.sh/uv/getting-started/installation/
uv sync --extra dev

# Optional: activate the managed venv
source .venv/bin/activate   # Linux/macOS (uv creates .venv by default)

# Run tools without activating
uv run devassist --version
```

Without uv: `python -m venv .venv`, activate it, then `pip install -e ".[dev]"`.

### Container Engine Setup (Docker/Podman)

DevAssist MCP servers run in containers. The default configuration uses Docker, but **Podman is fully supported**.

**For Podman-only systems (without Docker):**
```bash
# Create a symlink to allow MCP servers to work with Podman
sudo ln -s $(which podman) /usr/local/bin/docker
```

**Alternative approach:** Modify `src/devassist/resources/mcp-servers.json` to use `"command": "podman"` instead of `"command": "docker"`.

### Testing

```bash
# Run all tests
uv run pytest

# Run with coverage (minimum 80% required)
uv run pytest --cov=devassist

# Run unit tests only
uv run pytest tests/unit/

# Run integration tests (requires real API credentials, skipped in CI)
uv run pytest tests/integration/ -m integration

# Run contract tests (validate adapter implementations)
uv run pytest tests/contract/

# Run specific test file
uv run pytest tests/unit/test_brief_generator.py -v

# Skip slow/integration tests
uv run pytest -m "not integration and not slow"
```

### Code Quality

```bash
# Type checking (strict mode enabled)
uv run mypy src/

# Linting
uv run ruff check src/

# Format code
uv run ruff format src/
```

**Code Quality Policy**: Linter and type checker warnings should be ignored unless they are breaking functionality. The project prioritizes working features over perfect code quality metrics. Fix errors that prevent the code from running, but warnings from ruff and mypy can be addressed later during refactoring phases.

### Running the CLI

```bash
# Show version and current configuration
devassist --version
devassist status

# Configure through config files and environment variables
# Workspace directory (~/.devassist/) is created automatically
# Configure source credentials as needed:
export JIRA_URL="https://yourcompany.atlassian.net"
export JIRA_API_TOKEN="your-token"
export GITHUB_TOKEN="your-github-token"

# Claude AI authentication is handled automatically by the Agent SDK

# Generate morning brief
devassist brief
devassist brief --sources gmail,slack     # specific sources
devassist brief --model "Opus 4"         # user-friendly AI model names
devassist brief --resume                 # continue previous conversation
devassist brief --session-id session-123 # use specific session
devassist brief --refresh  # bypass cache
devassist brief --json     # JSON output

# Session management
devassist brief sessions                 # list recent sessions
devassist brief clean --days 7          # clean old sessions
devassist brief clear session-123       # clear specific session

# Background AI runner
devassist ai run                     # Start background runner (default: 5 min interval)
devassist ai run --interval 10       # Custom interval in minutes
devassist ai run --prompt "Custom prompt"  # Custom prompt
devassist ai run --foreground        # Run in foreground (Ctrl+C to stop)
devassist ai status                  # Show runner status
devassist ai logs                    # Show last 50 log lines
devassist ai logs --follow           # Follow logs (like tail -f)
devassist ai logs --lines 100        # Show last 100 lines
devassist ai kill                    # Stop runner gracefully
devassist ai kill --force            # Force kill
```

## Architecture

### Modern Unified Structure

```
src/devassist/
├── ai/          # Claude Agent SDK integration and AI clients (claude_client, vertex_client, base_client)
├── cli/         # Typer CLI commands (main, config, brief, ai) - presentation layer
├── core/        # Business logic (aggregator, ranker, brief_generator, runner)
├── adapters/    # Context source adapters (gmail, slack, jira, github)
├── models/      # Pydantic data models (config_unified, brief, context, mcp_config)
├── resources/   # System prompts, MCP server configurations
├── preferences/ # Preference learning system
└── utils/       # Utilities (process management, logging)
```

### Key Architectural Principles

The architecture follows modern patterns for maintainability and extensibility:

1. **Unified Configuration**: Single `ClientConfig` class handles all configuration needs
2. **Self-Contained Components**: Each component manages its own state and dependencies
3. **Static Session Management**: Sessions persist across component instances
4. **MCP Integration**: Uses industry-standard Model Context Protocol servers
5. **CLI Layer** (`cli/`): Typer commands, Rich output formatting, user interaction
6. **Core Services** (`core/`):
   - `aggregator.py` - Fetches context from all sources (SRP: fetch only)
   - `ranker.py` - Scores and sorts items by relevance (SRP: ranking only)
   - `brief_generator.py` - Orchestrates the full brief generation flow (SRP: coordination)
   - `cache_manager.py` - 15-minute TTL caching
   - `runner.py` - Background runner with asyncio event loop
   - `runner_manager.py` - Process lifecycle management (PID files, signals)
7. **Adapters** (`adapters/`): All implement `ContextSourceAdapter` contract (OCP: extend without modifying)
8. **AI Layer** (`ai/`): AI client implementations (Claude SDK, Vertex AI) and prompt templates

### Core Components

1. **ClientConfig** (`models/config.py`): Unified configuration with smart deserialization
2. **ClaudeClient** (`ai/claude_client.py`): Claude Agent SDK wrapper with static session management
3. **BriefGenerator** (`core/brief_generator.py`): Orchestrates brief generation workflow

### MCP Integration

Context sources are accessed through **Model Context Protocol (MCP) servers** configured in `resources/mcp_servers.yaml`:

- **Gmail**: OAuth2-based email access
- **Slack**: Bot/user token integration
- **JIRA**: API token authentication
- **GitHub**: Personal access token

Each MCP server handles its own authentication and data fetching.

### Data Flow: Morning Brief Generation

```
User runs `devassist brief`
    ↓
CLI (brief.py) → AppConfig (unified configuration)
    ↓
BriefGenerator (orchestrator) → ClaudeClient (AI integration)
    ↓
Claude Agent SDK → MCP Servers (context fetching)
    ↓
Claude API → AI processing and summarization
    ↓
Brief model → structured response
    ↓
Rich Console → formatted terminal output
```

### Configuration Precedence

The system uses a multi-tier configuration:
1. CLI flags (highest priority)
2. Environment variables
3. `.mcp.json` in current working directory
4. `~/.devassist/.mcp.json`
5. `~/.devassist/config.yaml` (legacy, deprecated)

### .mcp.json Configuration

The `.mcp.json` file is the primary configuration format supporting MCP servers, AI providers, and the background runner:

```json
{
  "version": "1.0",
  "mcp_servers": {
    "devassist": {
      "command": "devassist",
      "args": ["--config", "${workspace}/.mcp.json"],
      "env": {}
    }
  },
  "ai": {
    "provider": "claude",
    "model": "claude-sonnet-4-5@20250929",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  "runner": {
    "enabled": false,
    "interval_minutes": 5,
    "prompt": "Review my context and summarize urgent items.",
    "output_destination": "~/.devassist/runner-output.md",
    "notify_on_completion": false,
    "sources": []
  },
  "sources": {
    "gmail": { "enabled": true },
    "slack": { "bot_token": "${SLACK_BOT_TOKEN}" }
  },
  "preferences": {
    "priority_keywords": ["urgent", "critical"]
  }
}
```

**Environment Variable Expansion**: Use `${VAR_NAME}` syntax to reference environment variables for source configuration (like `${SLACK_BOT_TOKEN}`). Undefined variables expand to empty string.

**Authentication**: Claude Agent SDK handles AI authentication automatically - no manual API key configuration required.

**Migration**: Run `devassist config migrate` to convert `config.yaml` to `.mcp.json` format.

### Storage Model

All data is stored locally in `~/.devassist/`:

```
~/.devassist/
├── config.yaml          # User configuration (YAML format)
├── .mcp.json            # Primary MCP configuration (servers, AI, runner)
├── runner.pid           # Background runner PID file
├── runner.lock          # Runner lock file (single-instance enforcement)
├── runner-output.md     # Runner output destination
├── logs/
│   └── runner.log       # Background runner logs
├── cache/               # Source-specific caches (15-min TTL)
│   ├── gmail/
│   ├── slack/
│   ├── jira/
│   └── github/
├── briefs/              # Historical briefs
└── preferences.json     # Learned user preferences (planned)
```

**Key Changes from Legacy:**
- **No cache directory**: MCP servers handle their own caching
- **No session persistence**: Sessions are in-memory only (static store)
- **Simplified structure**: Only configuration and optional brief history

**Workspace Creation**: The `~/.devassist/` directory is created automatically by `AppConfig` when first accessed. No separate `init` command needed.

**Security**: Use environment variables for credentials in production. Configuration files should only contain non-sensitive settings.

## Development Workflow

### Test-Driven Development (Mandatory)

This project follows strict TDD (Red-Green-Refactor):

1. **Red**: Write failing test first
2. **Green**: Implement minimal code to pass
3. **Refactor**: Improve code while keeping tests green

All new features require:
- Unit tests in `tests/unit/` (mock external dependencies)
- Integration tests in `tests/integration/` (test real API interactions, marked with `@pytest.mark.integration`)
- Minimum 80% code coverage for `src/devassist/`

### Adding a New Context Source (MCP-Based)

1. **Create MCP Server**: Implement or find an existing MCP server for your source
2. **Add MCP Configuration**: Update `src/devassist/resources/mcp_servers.yaml`:
   ```yaml
   newsource:
     command: "mcp-server-newsource"
     env:
       NEWSOURCE_API_TOKEN: "${NEWSOURCE_API_TOKEN}"
   ```
3. **Update SourceType**: Add to enum in `src/devassist/models/context.py`
4. **Configure Environment Mapping**: Add to `AppConfig._get_mcp_servers_config()` for env var substitution
5. **Test Integration**: Write integration tests for the new source

**No custom adapter code needed!** MCP servers handle all the integration complexity.
5. Register in CLI config commands

### Error Handling Requirements

The spec (FR-005) requires graceful degradation:

- **Source failures**: Don't crash - show partial results and note which sources failed
- **AI unavailable**: Fall back to raw data presentation with clear messaging
- **Rate limiting**: Exponential backoff with user notification
- **Token expiration**: Detect, notify user, guide re-authentication
- **Transient errors**: Retry up to 3 times before failing

## Key Technical Decisions

### Python 3.11+ Required

The codebase uses modern Python features:
- Type hints with `|` union syntax (not `Union`)
- `str | None` instead of `Optional[str]`
- Strict mypy checking enabled

### Claude Agent SDK Integration

The project uses **Claude Agent SDK** for AI interactions:
- **Brief summarization**: Generate intelligent morning briefs
- **Conversation continuity**: Session-based interactions
- **MCP server coordination**: Automatic context aggregation

ClaudeClient handles all SDK complexity and provides a simple interface:
```python
client = ClaudeClient(config)
response = await client.make_call("Generate my morning brief")
```

### Pydantic for Data Validation

All data models use Pydantic v2 for:
- Configuration validation and smart deserialization
- Data model validation
- Environment variable handling

### Rich for Terminal Output

Use Rich library for all CLI output:
- Tables for session listings
- Panels for brief summaries
- Styled text for status and errors
- Markdown rendering for AI responses

### Asynchronous Operations

Key async operations:
- `ClaudeClient.make_call()` - AI interactions
- `ClaudeClient.create_session()` - Session initialization
- `BriefGenerator.generate()` - Brief orchestration

### AI Integration

The project uses **Claude Agent SDK** for AI operations:

**Features:**
- Background prompt execution via background runner
- Context summarization through morning briefs
- Custom task automation
- Session-based conversations
- MCP server integration for context aggregation

**Authentication:** The Claude Agent SDK handles authentication automatically - no manual API key setup required.

Configure provider in `.mcp.json`:
```json
{
  "ai": {
    "provider": "claude",  // or "vertex"
    ...
  }
}
```

## Specification-First Workflow

This project follows a specification-first approach. All specs live in `specs/[feature-id]/`:

- `spec.md` - Technology-agnostic feature specification
- `plan.md` - Technical implementation plan
- `data-model.md` - Entity models and relationships
- `contracts/` - Interface contracts (e.g., `context-source.md`)
- `tasks.md` - Granular implementation tasks
- `checklists/requirements.md` - Quality validation checklist

When implementing features:
1. Read the spec first to understand user value and acceptance criteria
2. Follow the plan for technical approach and structure decisions
3. Refer to contracts for interface requirements
4. Use tasks.md for step-by-step implementation guide

## Important Constraints

- **Performance**: Morning brief generation must complete in < 60 seconds for 4 sources
- **Sessions**: In-memory only (don't survive process restarts)
- **Coverage**: Minimum 80% test coverage for core modules
- **Token Limits**: AI prompts must stay within Claude model token limits
- **Single User**: Designed for single-user local execution (no multi-user support)
- **MCP Dependency**: Requires properly configured MCP servers for context sources

## Project Status

**Current Architecture: Unified & Modernized**

- ✅ **Phase 1**: Unified ClientConfig with smart deserialization
- ✅ **Phase 2**: Self-contained ClaudeClient with static session management
- ✅ **Phase 3**: Deprecated manager classes removed
- ✅ **Core Infrastructure**: Claude Agent SDK integration
- ✅ **Configuration**: User-friendly model names and auto-discovery
- ✅ **Brief Generation**: Full workflow with Claude Agent SDK
- ✅ **Session Management**: Persistent conversations across CLI calls
- ✅ **MCP Integration**: Industry-standard context server protocol
- ✅ **Testing**: 45+ comprehensive tests covering new architecture
- ✅ **Background AI Runner**: Claude SDK integration with background processing
- ✅ **MCP Configuration**: .mcp.json format with environment variable expansion
- 🚧 **Context Source Adapters**: Gmail, Slack, JIRA, GitHub implementations
- ⏳ **MCP Server Deployment**: Actual server implementations (planned)
- ⏳ **Preference Learning**: User priority learning (planned)
- ⏳ **Advanced Features**: EC2 management, auto-responses (planned)

## Current Implementation Status

### ✅ **Fully Implemented**
- `devassist status` - Show unified configuration status
- `devassist brief` - Generate morning brief with Claude
- `devassist brief sessions` - List and manage conversation sessions
- `devassist brief clean/clear` - Session cleanup
- Session resumption and conversation continuity
- User-friendly AI model configuration
- Environment variable and file-based configuration

### ✅ **Additional Features Implemented**
- `devassist config add/list/remove/test` - Manage context sources (interactive setup)
- `devassist config migrate` - Migrate config.yaml to .mcp.json format
- `devassist ai run` - Start background AI runner process
- `devassist ai kill` - Stop background runner
- `devassist ai status` - Show runner status
- `devassist ai logs` - View runner logs

### 🚧 **Partially Implemented**
- MCP server configurations (defined but servers need deployment)
- Legacy config commands (show deprecation notices)
- Context source adapter implementations (Gmail, Slack, JIRA, GitHub)

### ⏳ **Planned Features**
- Live MCP server deployments
- Preference learning system
- `devassist prefs` - Preference management
- `devassist sandbox` - EC2 instance management
- Quarterly contribution summaries
- Auto-response drafting

**Architecture is complete and ready for MCP server integration!**
