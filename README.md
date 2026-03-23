# DevAssist - AI-Powered Developer Assistant

A Python CLI application that aggregates context from multiple developer tools (GitHub, Jira, Slack) and uses AI to provide:
- **Morning Briefs** - Consolidated summaries of your PRs, issues, and messages
- **Interactive Chat** - Ask questions about your work in natural language
- **Background Daemon** - Scheduled briefs at 8am, 1pm, and 5pm

## Features

- **GitHub Integration** - PRs needing review, issues assigned to you, notifications
- **Jira/Atlassian Integration** - Open issues, sprint status, recent updates
- **Slack Integration** - Unread messages, mentions, channel activity
- **Interactive REPL** - `devassist chat` for continuous conversation
- **Background Daemon** - Runs in background, generates scheduled briefs

## Quick Start

### 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/ayush17/notebooks-ai-agent.git
cd notebooks-ai-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install in development mode
pip install -e ".[dev]"
```

### 2. Install MCP Servers

```bash
# GitHub MCP (required)
npm install -g @modelcontextprotocol/server-github

# Atlassian MCP: `npx -y mcp-remote https://mcp.atlassian.com/v1/mcp` (no global install required)
# Same transport as Cursor `mcp.json`; Node.js 18+ on PATH is enough.
```

### 3. Configure Credentials

#### Option A: Interactive Setup
```bash
devassist setup init
```

#### Option B: Manual Configuration

Create `~/.devassist/.env`:

```bash
mkdir -p ~/.devassist

cat > ~/.devassist/.env << 'EOF'
# Claude AI (via Anthropic API)
export ANTHROPIC_API_KEY="your-anthropic-key"

# OR Claude on Vertex AI (Red Hat)
export CLAUDE_CODE_USE_VERTEX=1
export CLOUD_ML_REGION=us-east5
export ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project

# GitHub (required)
# Get token: https://github.com/settings/tokens
# Scopes needed: repo, notifications, read:user
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_xxx"

# Atlassian API (optional — only for `devassist brief` Jira/Confluence adapters;
# `devassist ask` / `chat -s atlassian` uses remote MCP and does not need these)
# Get token: https://id.atlassian.com/manage-profile/security/api-tokens
export ATLASSIAN_BASE_URL="https://your-site.atlassian.net"
export ATLASSIAN_EMAIL="your-email@example.com"
export ATLASSIAN_API_TOKEN="your-atlassian-token"
EOF

chmod 600 ~/.devassist/.env
```

### 4. Test It

```bash
# Load environment
source ~/.devassist/.env

# One-off question
devassist ask "What PRs need my review?" -s github

# Interactive chat
devassist chat -s github,atlassian

# Check status
devassist setup status
```

## Usage

### Ask Command (One-off Questions)

```bash
# GitHub queries
devassist ask "What PRs need my review?" -s github
devassist ask "Search for PRs where I'm a reviewer using is:pr is:open review-requested:@me" -s github

# Jira queries
devassist ask "What are my open Jira issues?" -s atlassian

# Combined
devassist ask "Give me a morning brief" -s github,atlassian
```

### Chat Command (Interactive REPL)

```bash
devassist chat -s github,atlassian
```

Available commands in chat:
- `/help` - Show help
- `/servers` - List connected MCP servers
- `/tools` - List available tools
- `/clear` - Clear conversation history
- `/quit` - Exit

### Background Daemon

```bash
# Start in foreground (for testing)
./scripts/start_daemon.sh

# Start in background
./scripts/start_daemon.sh -b

# Stop daemon
./scripts/stop_daemon.sh

# View logs
tail -f ~/.devassist/daemon.log

# View latest brief
cat ~/.devassist/briefs/latest.md
```

The daemon generates briefs at:
- 8:00 AM
- 1:00 PM  
- 5:00 PM

## Architecture

```
src/devassist/
├── cli/           # Typer CLI commands (ask, chat, setup)
├── core/          # Business logic (aggregator, ranker, brief_generator)
├── adapters/      # Context source adapters (gmail, slack, jira, github)
├── mcp/           # MCP client and server registry
├── orchestrator/  # LLM orchestration agent
├── ai/            # Vertex AI integration
├── preferences/   # Preference learning (planned)
└── models/        # Pydantic data models
```

## MCP Servers

| Server | Package | Purpose |
|--------|---------|---------|
| GitHub | `@modelcontextprotocol/server-github` | PRs, issues, repos |
| Atlassian | `mcp-remote` → `https://mcp.atlassian.com/v1/mcp` | Jira, Confluence (hosted MCP) |

## Troubleshooting

### "No MCP servers configured"
- Run `devassist setup status` to check configuration
- Ensure environment variables are set: `source ~/.devassist/.env`

### Atlassian MCP slow or auth issues
- First run downloads `mcp-remote`; ensure outbound HTTPS is allowed
- Authentication follows Atlassian’s remote MCP flow (browser/OAuth as prompted by the connector)
- Large Jira searches may take 30–60 seconds

### GitHub MCP asks for repo details
- Use specific search syntax: "Search for PRs using is:pr is:open review-requested:@me"
- The LLM needs guidance on GitHub search queries

### Command not found: devassist
- Ensure you've activated the venv: `source .venv/bin/activate`
- Reinstall: `pip install -e .`

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=devassist

# Type checking
mypy src/

# Linting
ruff check src/
```

## Requirements

- Python 3.11+
- Node.js 18+ (for MCP servers)
- **Claude AI access** (one of the following):
  - Anthropic API key from [console.anthropic.com](https://console.anthropic.com) (paid)
  - OR Red Hat employees: Use Vertex AI with `ANTHROPIC_VERTEX_PROJECT_ID=itpc-gcp-ai-eng-claude`
- **GitHub**: Personal Access Token (free) - [Create here](https://github.com/settings/tokens)
- **Jira/Atlassian**: Access to an Atlassian Cloud site (OAuth - browser login on first use)

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes* | Anthropic API key for Claude |
| `CLAUDE_CODE_USE_VERTEX` | Yes* | Set to `1` for Vertex AI |
| `ANTHROPIC_VERTEX_PROJECT_ID` | Yes* | GCP project ID for Vertex AI |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | Yes | GitHub PAT with repo, notifications scopes |
| `ATLASSIAN_BASE_URL` | No | Optional; for `devassist brief` Jira adapter (not MCP remote) |
| `ATLASSIAN_EMAIL` | No | Optional; same |
| `ATLASSIAN_API_TOKEN` | No | Optional; same |
| `SLACK_BOT_TOKEN` | No | Slack bot token (xoxb-...) |
| `SLACK_TEAM_ID` | No | Slack workspace ID |

*Either Anthropic API key OR Vertex AI config required

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request
