# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Singlarity** (DevAssist) is a Python CLI application that aggregates context from multiple developer tools (Gmail, Slack, JIRA, GitHub) and uses GCP Vertex AI (Gemini) to generate a Unified Morning Brief and productivity features. The project is in active development with implementation in the `python-cli` branch.

## Development Commands

### Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install in development mode
pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage (minimum 80% required)
pytest --cov=devassist

# Run unit tests only
pytest tests/unit/

# Run integration tests (requires real API credentials, skipped in CI)
pytest tests/integration/ -m integration

# Run contract tests (validate adapter implementations)
pytest tests/contract/

# Run specific test file
pytest tests/unit/test_brief_generator.py -v

# Skip slow/integration tests
pytest -m "not integration and not slow"
```

### Code Quality

```bash
# Type checking (strict mode enabled)
mypy src/

# Linting
ruff check src/

# Format code
ruff format src/
```

### Running the CLI

```bash
# Show version
devassist --version

# Initialize workspace (~/.devassist/)
devassist init

# Configure context sources
devassist config add gmail
devassist config add slack --token xoxb-token
devassist config test

# Generate morning brief
devassist brief
devassist brief --refresh  # bypass cache
devassist brief --json     # JSON output
```

## Architecture

### High-Level Structure

```
src/devassist/
├── cli/         # Typer CLI commands (presentation layer)
├── core/        # Business logic (aggregator, ranker, brief_generator)
├── adapters/    # Context source adapters (gmail, slack, jira, github)
├── ai/          # Vertex AI integration for summarization
├── preferences/ # Preference learning system
└── models/      # Pydantic data models
```

### Separation of Concerns (SOLID Principles)

The architecture follows strict separation to enable future UI extensions (web app, Slack bot) without duplicating business logic:

1. **CLI Layer** (`cli/`): Typer commands, Rich output formatting, user interaction
2. **Core Services** (`core/`):
   - `aggregator.py` - Fetches context from all sources (SRP: fetch only)
   - `ranker.py` - Scores and sorts items by relevance (SRP: ranking only)
   - `brief_generator.py` - Orchestrates the full brief generation flow (SRP: coordination)
   - `config_manager.py` - Configuration and workspace management
   - `cache_manager.py` - 15-minute TTL caching
3. **Adapters** (`adapters/`): All implement `ContextSourceAdapter` contract (OCP: extend without modifying)
4. **AI Layer** (`ai/`): Vertex AI client and prompt templates

### Plugin Architecture for Context Sources

All adapters implement the `ContextSourceAdapter` abstract base class defined in `src/devassist/adapters/base.py`. The contract specifies:

- `authenticate(config)` - OAuth2 or API token authentication
- `test_connection()` - Health check
- `fetch_items(limit, **kwargs)` - Yields `ContextItem` objects
- `get_required_config_fields()` - Returns configuration requirements

See `specs/001-dev-assistant-cli/contracts/context-source.md` for the full contract specification.

### Data Flow: Morning Brief Generation

```
User runs `devassist brief`
    ↓
CLI (brief.py) → BriefGenerator (orchestrator)
    ↓
ContextAggregator → fetches from all adapters in parallel
    ↓
RelevanceRanker → scores items (preferences + recency + metadata)
    ↓
VertexAIClient → generates summary with Gemini
    ↓
Brief model → sections grouped by source
    ↓
Rich Console → formatted terminal output
```

### Configuration Precedence

The system uses three-tier configuration:
1. CLI flags (highest priority)
2. Environment variables
3. Config files: `~/.devassist/config.yaml` (lowest priority)

### Storage Model

All data is stored locally in `~/.devassist/`:

```
~/.devassist/
├── config.yaml          # User configuration (includes credentials in dev mode)
├── cache/               # Source-specific caches (15-min TTL)
│   ├── gmail/
│   ├── slack/
│   ├── jira/
│   └── github/
├── briefs/              # Historical briefs
└── preferences.json     # Learned user preferences
```

**Security Note**: In dev mode, credentials are stored in plain text. Production deployments should use OS-native credential storage.

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

### Implementing a New Context Source Adapter

1. Write failing contract test in `tests/contract/test_context_source_contract.py`
2. Write failing integration test in `tests/integration/test_<source>_adapter.py`
3. Implement adapter in `src/devassist/adapters/<source>.py`:
   - Inherit from `ContextSourceAdapter`
   - Implement all abstract methods
   - Handle authentication (OAuth2 or API tokens)
   - Transform source data to `ContextItem` format
   - Set relevance scores (0.0-1.0)
   - Handle errors: `AuthenticationError`, `SourceUnavailableError`, `RateLimitError`
4. Add to `SourceType` enum in `src/devassist/models/context.py`
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

### Asynchronous I/O

All adapter fetch operations are async (`async def fetch_items()`) to enable parallel fetching from multiple sources. Use `httpx` for HTTP clients (not `requests`).

### Pydantic for Data Validation

All data models use Pydantic v2 for validation, serialization, and configuration management.

### Rich for Terminal Output

Use Rich library for all CLI output:
- Tables for structured data
- Panels for summaries
- Progress bars for multi-source fetching
- Styled text for errors/warnings

### GCP Vertex AI Integration

The project uses GCP Vertex AI (Gemini model) for:
- Brief summarization
- Item categorization
- Draft response generation

Authentication via Application Default Credentials:
```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
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
- **Cache TTL**: 15 minutes for all context data
- **Coverage**: Minimum 80% test coverage for core and adapter modules
- **Token Limits**: AI prompts must stay within model token limits
- **Single User**: This version is designed for single-user local execution (no multi-user support)

## Project Status

Current development is in the `python-cli` branch. The main branch contains only specifications. Active work includes:

- ✅ Project structure and foundational infrastructure
- ✅ Core models and configuration management
- ✅ Base adapter contract
- 🚧 Context source adapter implementations (Gmail, Slack, JIRA, GitHub)
- 🚧 Brief generation orchestration
- 🚧 AI integration with Vertex AI
- ⏳ Preference learning system
- ⏳ EC2 sandbox management
- ⏳ Auto-response drafting

See `specs/001-dev-assistant-cli/tasks.md` for detailed task tracking.
