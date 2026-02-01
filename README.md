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

### Container Engine Setup

DevAssist uses MCP servers that run in containers. The configuration defaults to using Docker, but **Podman is fully supported** as a drop-in replacement.

#### For Podman Users (Without Docker)

If you have Podman installed but not Docker, create a symlink to allow MCP servers to work seamlessly:

```bash
# Verify podman is installed
which podman

# Create symlink (requires sudo)
sudo ln -s $(which podman) /usr/local/bin/docker

# Verify the symlink
docker --version  # Should show Podman version
```

**Alternative:** If you prefer not to create a symlink, you can modify the MCP server configuration at `src/devassist/resources/mcp-servers.json` to use `podman` instead of `docker` for the `command` field.

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

#### Required Environment Variables

```bash
# JIRA Integration (Required for JIRA source)
export JIRA_URL="https://yourcompany.atlassian.net"
export JIRA_USERNAME="your-email@company.com"
export JIRA_PERSONAL_TOKEN="your-jira-api-token"

# GitHub Integration (Required for GitHub source)
export GITHUB_TOKEN="your-github-personal-access-token"

# Claude AI authentication is handled automatically by Agent SDK
```

#### Optional Environment Variables

```bash
# JIRA Configuration (Optional)
export JIRA_SSL_VERIFY="true"  # Set to "false" for self-signed certs (default: true)

# Slack Notifications (Optional - for background runner notifications)
export SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
export SLACK_USER_ID="U1234567890"  # Your Slack user ID for DM notifications

# Gmail Integration (Future - when MCP server available)
export GMAIL_CLIENT_ID="your-gmail-oauth-client-id"
export GMAIL_CLIENT_SECRET="your-gmail-oauth-secret"

# Override Default Settings (Optional)
export DEVASSIST_AI_MODEL="Sonnet 4"  # Override default AI model
export DEVASSIST_SOURCES="jira,github"  # Override default sources
export DEVASSIST_TIMEOUT="180"  # AI timeout in seconds (default: 180)
```

#### Internal Environment Variables (Set Automatically)

These are set automatically by the system and should not be configured manually:

```bash
# Background Runner Internal Variables (Set by RunnerManager)
DEVASSIST_RUNNER_INTERVAL="5"  # Runner interval in minutes
DEVASSIST_RUNNER_PROMPT="..."  # Custom prompt for runner
DEVASSIST_RUNNER_SESSION_ID="session-123"  # Session continuity
DEVASSIST_RUNNER_ENABLE_SLACK="true"  # Slack notification setting
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

# Control Slack notifications
devassist ai run --disable-slack  # Disable Slack notifications
devassist ai run --enable-slack   # Enable Slack notifications (default)

# Run in foreground for testing
devassist ai run --foreground --interval 2

# Continue with specific session
devassist ai run --session-id session-abc123

# Management commands
devassist ai status    # Check runner status and uptime
devassist ai logs      # View runner logs (last 50 lines)
devassist ai logs --follow    # Follow logs in real-time
devassist ai logs --lines 100 # Show more log lines
devassist ai output    # View latest runner output
devassist ai kill      # Stop background runner gracefully
devassist ai kill --force     # Force kill runner

# Testing and debugging
devassist ai test      # Test Claude SDK connectivity
devassist ai sessions  # List active Claude sessions
devassist ai clear     # Clear all Claude sessions
devassist ai prompt --prompt "Custom instruction"  # Send prompt to runner session
```

## 🏗️ Architecture Overview

### Modern Design Principles
- **Self-Contained Components**: Each component manages its own state
- **Unified Configuration**: Single ClientConfig class for all settings
- **Static Sessions**: Shared across all component instances
- **MCP Integration**: Industry-standard context protocol
- **Background Processing**: Automated AI runner with process management

### High-Level System Architecture

```mermaid
flowchart TB
    subgraph "👤 User Experience"
        A1[🌅 Morning Brief<br/>devassist brief]
        A2[🤖 Background Monitoring<br/>devassist ai run]
        A3[💬 Follow-up Questions<br/>devassist brief --prompt]
    end

    subgraph "📊 Developer Data Sources"
        B1[📋 JIRA Issues<br/>• Assigned tasks<br/>• Urgent tickets<br/>• Project updates]
        B2[⚡ GitHub Activity<br/>• PR reviews<br/>• Code changes<br/>• Repository updates]
        B3[📧 Gmail Integration<br/>• Important emails<br/>• Meeting invites<br/>• Action items]
        B4[💬 Slack Communications<br/>• Team messages<br/>• Notifications<br/>• Mentions]
    end

    subgraph "🧠 AI Intelligence Layer"
        C1[🔮 Claude AI Processing]
        C2[⚙️ Context Integration]
        C3[🎯 Priority Analysis]
        C4[📝 Natural Language Generation]
    end

    subgraph "✨ Business Outcomes"
        D1[📈 Prioritized Daily Brief<br/>• Top priorities<br/>• Action items<br/>• Code reviews]
        D2[⏰ Automated Monitoring<br/>• Background analysis<br/>• Continuous updates<br/>• Proactive alerts]
        D3[🎯 Focus & Productivity<br/>• Reduced context switching<br/>• Clear priorities<br/>• Informed decisions]
        D4[🔄 Continuous Learning<br/>• Session continuity<br/>• Context awareness<br/>• Personalized insights]
    end

    %% User to Data Sources
    A1 -.-> B1
    A1 -.-> B2
    A1 -.-> B3
    A1 -.-> B4

    A2 -.-> B1
    A2 -.-> B2

    %% Data Sources to AI
    B1 --> C1
    B2 --> C1
    B3 --> C1
    B4 --> C1

    C1 --> C2
    C2 --> C3
    C3 --> C4

    %% AI to Outcomes
    C4 --> D1
    C4 --> D2

    %% Outcomes to User Value
    D1 --> D3
    D2 --> D3
    D1 --> D4
    D2 --> D4

    %% Follow-up loop
    A3 -.-> C1
    D4 -.-> A3

    style A1 fill:#e3f2fd
    style A2 fill:#e8f5e8
    style A3 fill:#fff3e0
    style C1 fill:#f3e5f5
    style D3 fill:#e8f5e8
    style D4 fill:#fff3e0

    classDef dataSource fill:#f5f5f5,stroke:#666,color:#333
    classDef aiLayer fill:#f3e5f5,stroke:#8e24aa,color:#4a148c
    classDef outcome fill:#e8f5e8,stroke:#4caf50,color:#1b5e20

    class B1,B2,B3,B4 dataSource
    class C1,C2,C3,C4 aiLayer
    class D1,D2,D3,D4 outcome
```

### Key Business Benefits

| Capability | Business Value | Technical Implementation |
|------------|----------------|------------------------|
| **🌅 Instant Daily Brief** | Start each day informed and focused | Claude AI + Multi-source integration |
| **⏰ Background Monitoring** | Never miss critical updates | Automated scanning + Smart notifications |
| **💬 Conversational Interface** | Natural interaction with your data | Session-aware AI conversations |
| **🔌 Universal Integration** | Connect all your developer tools | Industry-standard MCP protocol |
| **🎯 Smart Prioritization** | Focus on what matters most | AI-powered relevance ranking |
| **📈 Continuous Learning** | Gets better as you use it | Session continuity + Context awareness |

### Data Flow & Integration Points

```mermaid
graph LR
    subgraph "🔐 Secure Authentication"
        AUTH[Environment Variables<br/>• JIRA_TOKEN<br/>• GITHUB_TOKEN<br/>• Secure credential management]
    end

    subgraph "⚙️ Core Engine"
        ENGINE[DevAssist Engine<br/>• Claude AI integration<br/>• Session management<br/>• Configuration handling]
    end

    subgraph "📱 User Interfaces"
        CLI[Command Line<br/>• devassist brief<br/>• devassist ai run<br/>• Interactive sessions]
        OUTPUT[Rich Output<br/>• Formatted briefs<br/>• JSON export<br/>• Markdown reports]
    end

    AUTH --> ENGINE
    ENGINE --> CLI
    CLI --> OUTPUT

    ENGINE -.->|Background<br/>Monitoring| NOTIFY[Slack Notifications<br/>• Critical updates<br/>• Automated alerts]

    style AUTH fill:#ffebee
    style ENGINE fill:#f3e5f5
    style CLI fill:#e3f2fd
    style OUTPUT fill:#e8f5e8
    style NOTIFY fill:#fff3e0
```

> **For detailed technical implementation:** See [ARCHITECTURE.md](./ARCHITECTURE.md)

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
# Core Source Credentials (Required)
export JIRA_URL="https://yourcompany.atlassian.net"
export JIRA_USERNAME="your-email@company.com"
export JIRA_PERSONAL_TOKEN="secure-jira-token"
export GITHUB_TOKEN="secure-github-token"

# Optional Slack Integration
export SLACK_BOT_TOKEN="xoxb-secure-slack-bot-token"
export SLACK_USER_ID="U1234567890"

# Optional JIRA Configuration
export JIRA_SSL_VERIFY="true"

# Claude AI authentication is handled automatically by Agent SDK
```

### How to Get Tokens

#### JIRA Personal Access Token
1. Go to: `https://yourcompany.atlassian.net/secure/ViewProfile.jspa`
2. Click **Personal Access Tokens** → **Create Token**
3. Give it a name (e.g., "DevAssist CLI")
4. Copy the generated token

#### GitHub Personal Access Token
1. Go to: [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/personal-access-tokens)
2. Click **Generate new token (classic)**
3. Select scopes: `repo`, `read:user`, `read:org`, `notifications`
4. Copy the generated token

#### Slack Bot Token (Optional)
1. Go to: [Slack API Apps](https://api.slack.com/apps)
2. Create new app → From scratch
3. Go to **OAuth & Permissions** → **Bot Token Scopes**
4. Add scopes: `chat:write`, `users:read`
5. Install app to workspace and copy **Bot User OAuth Token**

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

### Security Best Practices
- ✅ **Use environment variables** for production deployments
- ✅ **Rotate tokens regularly** (every 90 days recommended)
- ✅ **Use minimal scopes** - only grant necessary permissions
- ❌ **Never commit credentials** to version control
- ❌ **Don't share tokens** in chat, email, or documentation
- ❌ **Avoid logging credentials** - our system filters them automatically

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

## 🔧 Troubleshooting

### Common Issues and Solutions

#### "No response received from Claude SDK"
This usually indicates MCP server connection issues:

```bash
# Check your credentials are set
env | grep -E "(JIRA|GITHUB)"

# Test connectivity
devassist ai test

# Check logs for detailed error messages
devassist ai logs

# Common causes:
# - Missing JIRA_URL, JIRA_USERNAME, or JIRA_PERSONAL_TOKEN
# - Invalid GitHub token or insufficient permissions
# - Network connectivity issues to your JIRA instance
```

#### Background Runner Not Working
```bash
# Check runner status
devassist ai status

# View detailed logs
devassist ai logs --lines 50

# Common issues:
# - Environment variables not passed to subprocess
# - Session file permissions
# - Port conflicts with MCP servers
```

#### Session Continuity Problems
```bash
# List active sessions
devassist brief sessions

# Clear problematic sessions
devassist brief clean --days 1

# Force new session
devassist brief --refresh
```

#### Permission Errors
```bash
# Check workspace permissions
ls -la ~/.devassist/

# Recreate workspace if needed
rm -rf ~/.devassist/
devassist status  # Recreates workspace
```

### Debug Mode
Enable verbose logging for troubleshooting:

```bash
# Enable debug logging
export DEVASSIST_DEBUG=true

# Run with detailed output
devassist brief --refresh

# Check all environment variables
devassist status
```

## 📋 Requirements

- **Python**: 3.11+ (uses modern syntax with `|` unions)
- **Claude Agent SDK**: Handles AI authentication automatically
- **MCP Servers**: Configured for desired integrations (JIRA, GitHub)
- **Source Credentials**: For each context source (JIRA, GitHub tokens)
- **Container Engine**: Docker or Podman for MCP server execution

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