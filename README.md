# DevAssist - AI-Powered Developer Morning Brief

> Modern Python CLI that aggregates context from your developer tools and uses **Claude Agent SDK** to generate intelligent morning briefs.

## 🚀 What is DevAssist?

DevAssist connects to your daily tools (Gmail, Slack, JIRA, GitHub) through **Model Context Protocol (MCP) servers** and uses **Claude** to create personalized morning briefs that help you start each day focused and informed.

## ✨ Key Features

- **🔮 AI-Powered Briefs**: Claude Agent SDK generates intelligent summaries
- **🤖 Background AI Runner**: Automated periodic brief generation
- **🔌 MCP Integration**: Industry-standard context servers (no custom adapters needed)
- **⚙️ Unified Configuration**: Single `ClientConfig` handles all settings
- **💾 Smart Sessions**: Persistent conversations that survive across CLI calls
- **🎯 User-Friendly**: Natural language configuration ("Sonnet 4", "fast", "best")
- **🏗️ Self-Contained**: Minimal dependencies, maximum reliability

## 🎯 Current Status

**✅ Implemented:**
- Unified ClientConfig with smart deserialization
- ClaudeClient with Claude Agent SDK integration and static session management
- BriefGenerator with MCP server integration
- CLI commands for brief generation and session management
- Background AI runner with process management
- AI commands for runner control and monitoring

**🚧 Planned:**
- Live MCP server deployments
- Preference learning system
- Auto-response drafting
- Quarterly contribution summaries
- EC2 sandbox management

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/singlarity-seekers/singlarity.git
cd singlarity

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install in development mode
pip install -e ".[dev]"
```

## ⚡ Quick Start

### 1. Basic Setup
```bash
# Check status
devassist status

# The workspace ~/.devassist/ is created automatically
# Shows available sources and current configuration
```

### 2. Configure Sources via Config File
Create `~/.devassist/config.yaml`:

```yaml
# User-friendly configuration
ai_model: "Sonnet 4"           # Maps to claude-sonnet-4-5@20250929
sources: ["jira", "github"]    # Based on available MCP servers
output_format: "markdown"

# Source-specific settings
source_configs:
  jira:
    enabled: true
    url: "https://yourcompany.atlassian.net"
    username: "your-email@company.com"
  github:
    enabled: true
    token: "your-github-token"
```

### 3. Set Environment Variables
```bash
# Source credentials (recommended for production)
export JIRA_URL="https://yourcompany.atlassian.net"
export JIRA_USERNAME="you@company.com"
export JIRA_PERSONAL_TOKEN="your-jira-token"
export GITHUB_TOKEN="your-github-token"

# Claude AI authentication is handled automatically by Agent SDK
```

### 4. Generate Your First Brief
```bash
# Generate morning brief
devassist brief

# Use specific sources
devassist brief --sources gmail,jira

# Continue previous conversation
devassist brief --resume

# Ask follow-up questions
devassist brief --prompt "What are my highest priority items today?"
```

## 🔧 Usage Examples

### Morning Brief Workflow
```bash
# Start your day
devassist brief

# Continue the conversation
devassist brief --prompt "Show me just the urgent items"
devassist brief --prompt "What meetings do I have today?"

# List recent sessions
devassist brief sessions

# Resume specific session
devassist brief --session-id session-abc123
```

### Configuration Management
```bash
# Check current status
devassist status

# Configuration via CLI args
devassist brief \
  --sources gmail,slack \
  --model "Opus 4" \
  --output json

# Environment variable overrides
export DEVASSIST_AI_MODEL="fast"
export DEVASSIST_SOURCES="gmail,jira"
devassist brief
```

### Session Management
```bash
# List all sessions
devassist brief sessions

# Clear old sessions (older than 7 days)
devassist brief clean --days 7

# Clear specific session
devassist brief clear session-abc123
```

### Background AI Runner
```bash
# Start background runner (runs every 5 minutes by default)
devassist ai run

# Start with custom interval and prompt
devassist ai run --interval 10 --prompt "Summarize urgent tasks requiring immediate attention"

# Run in foreground for testing
devassist ai run --foreground --interval 2

# Check runner status
devassist ai status

# View runner logs
devassist ai logs

# View latest runner output
devassist ai output

# Stop background runner
devassist ai kill
```

## 🏗️ Architecture Overview

### Modern Design Principles
- **Self-Contained Components**: Each component manages its own state
- **Unified Configuration**: Single ClientConfig class for all settings
- **Static Sessions**: Shared across all component instances
- **MCP Integration**: Industry-standard context protocol
- **Background Processing**: Automated AI runner with process management

### Core Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CLI Commands  │───▶│   ClientConfig   │───▶│  BriefGenerator │
│ (brief, ai)     │    │   (Unified)      │    │ (Orchestrator)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MCP Servers   │◀───│  ClaudeClient    │◀───│ Static Sessions │
│ (JIRA, GitHub)  │    │ (Agent SDK)      │    │    Store        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                 ▲                       ▲
                                 │                       │
                    ┌─────────────────┐    ┌─────────────────┐
                    │ Background      │    │   Runner        │
                    │ Runner          │    │   Manager       │
                    └─────────────────┘    └─────────────────┘
```

### Data Flow
```
CLI Input → ClientConfig → BriefGenerator → ClaudeClient → MCP Servers → Claude Agent SDK → Response
Background Runner → ClientConfig → ClaudeClient → MCP Servers → Output File
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed technical documentation.

## ⚙️ Configuration Options

### AI Models (User-Friendly Names)
```yaml
ai_model: "Sonnet 4"     # claude-sonnet-4-5@20250929 (default)
ai_model: "Opus 4"       # claude-opus-4-1@20250805
ai_model: "fast"         # claude-sonnet-4-5@20250929
ai_model: "best"         # claude-opus-4-5@20251101
```

### Sources
```yaml
sources: ["jira", "github"]
# Based on available MCP servers in resources/mcp-servers.json
```

### Session Management
```yaml
session_auto_resume: true    # Resume latest session automatically
# OR
session_id: "session-123"    # Use specific session

# Cannot use both simultaneously
```

### Output Formats
```yaml
output_format: "markdown"   # Rich formatted output
output_format: "json"       # Structured data
```

## 🧪 Development

### Testing
```bash
# Run all tests
pytest

# Test with coverage (minimum 80% required)
pytest --cov=devassist

# Run specific test suites
pytest tests/unit/test_config_unified.py -v
pytest tests/unit/test_claude_client_static_sessions.py -v
```

### Code Quality
```bash
# Type checking (strict mode)
mypy src/

# Linting
ruff check src/

# Format code
ruff format src/
```

### Adding New Context Sources
1. Add MCP server configuration to `src/devassist/resources/mcp_servers.yaml`
2. Update `SourceType` enum in `src/devassist/models/context.py`
3. Configure environment variable mapping in AppConfig
4. No additional code changes needed!

## 📁 Project Structure

```
src/devassist/
├── ai/                    # Claude Agent SDK integration
│   ├── claude_client.py   # Self-contained Claude client with sessions
│   └── prompts.py         # AI prompt templates
├── cli/                   # Command-line interface (Typer)
│   ├── main.py           # Entry point and status command
│   ├── brief.py          # Brief generation commands
│   ├── ai.py             # Background runner commands
│   └── prompt.py         # Prompt management commands
├── core/                  # Business logic
│   ├── brief_generator.py # Orchestrates brief generation
│   ├── runner.py         # Background AI runner
│   └── runner_manager.py # Process lifecycle management
├── models/                # Data models (Pydantic)
│   ├── config.py         # Unified configuration model (ClientConfig)
│   ├── mcp_config.py     # MCP server configuration models
│   ├── brief.py          # Brief data structures
│   └── context.py        # Context types and enums
├── resources/             # Static resources
│   ├── mcp-servers.json  # MCP server configurations
│   └── personal-assistant.md # System prompt
└── utils/                 # Utility functions
    └── process.py        # Process management utilities
```

## 🔐 Security & Credentials

### Recommended Approach (Production)
```bash
# Use environment variables for source credentials
export JIRA_URL="https://yourcompany.atlassian.net"
export JIRA_USERNAME="your-email@company.com"
export JIRA_PERSONAL_TOKEN="secure-jira-token"
export GITHUB_TOKEN="secure-github-token"
# Claude AI authentication is handled automatically by Agent SDK
```

### Development Convenience
```yaml
# ~/.devassist/config.yaml
source_configs:
  jira:
    url: "https://yourcompany.atlassian.net"
    username: "your-email@company.com"
    token: "dev-jira-token"
  github:
    token: "dev-github-token"
```

**⚠️ Never commit credentials to version control**

## 🚀 Migration from Legacy Versions

If you're upgrading from the old adapter-based architecture:

### What Changed
- ❌ `devassist config add` → ✅ Configure via `config.yaml` or env vars
- ❌ Custom adapters → ✅ MCP servers (industry standard)
- ❌ ConfigManager → ✅ Unified ClientConfig
- ❌ SessionManager → ✅ ClaudeClient static sessions
- ❌ Manual Claude API keys → ✅ Claude Agent SDK automatic authentication
- ✅ **NEW**: Background AI runner (`devassist ai` commands)

### Migration Steps
1. Create `~/.devassist/config.yaml` with your sources
2. Set environment variables for source credentials (JIRA, GitHub)
3. Use new CLI commands: `devassist brief`, `devassist ai`
4. No Claude API key setup required

## 📋 Requirements

- **Python**: 3.11+ (uses modern syntax with `|` unions)
- **Claude Agent SDK**: Handles AI authentication automatically
- **MCP Servers**: Configured for desired integrations (JIRA, GitHub)
- **Source Credentials**: For each context source (JIRA, GitHub tokens)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Follow TDD: Write tests first, then implementation
4. Ensure 80% test coverage: `pytest --cov=devassist`
5. Run quality checks: `mypy src/` and `ruff check src/`
6. Submit a pull request

## 📄 License

MIT License - see [LICENSE](./LICENSE) file for details.

## 🔗 Links

- **Architecture Documentation**: [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Project Instructions for Claude**: [CLAUDE.md](./CLAUDE.md)
- **Issues & Discussions**: [GitHub Issues](https://github.com/singlarity-seekers/singlarity/issues)

---

*Built with ❤️ for developer productivity using Claude Agent SDK and modern Python patterns.*