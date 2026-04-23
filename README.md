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

This project uses [uv](https://docs.astral.sh/uv/) for environments and installs (pinned via `uv.lock` and `.python-version`).

```bash
# Clone the repository
git clone https://github.com/ayush17/notebooks-ai-agent.git
cd notebooks-ai-agent

# Install uv (once per machine): https://docs.astral.sh/uv/getting-started/installation/
# Then create .venv and install the project + dev dependencies
uv sync --extra dev

# Run CLI without activating the venv explicitly
uv run devassist --version
```

Activation is optional — use `source .venv/bin/activate` if you prefer a traditional workflow. Without uv, use `pip install -e ".[dev]"` in a Python 3.11+ virtual environment instead.

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

Credentials and exports live in `**~/.devassist/env**` (the CLI also reads a legacy `**~/.devassist/.env**` if present; new writes update both files with the same content).

```bash
mkdir -p ~/.devassist

cat > ~/.devassist/env << 'EOF'
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

chmod 600 ~/.devassist/env
```

Application settings (which sources are enabled, **brief AI provider**, Gemini project/region, etc.) are stored in `**~/.devassist/config.yaml`**. After you edit the env file, run `**devassist config sync**` so the `ai` section stays aligned with your Claude/Vertex credentials, or run `**devassist setup init**` once to drive both files interactively.

### 4. Test It

```bash
# Load environment (optional — the CLI loads ~/.devassist/env on every run)
source ~/.devassist/env

# One-off question
devassist ask "What PRs need my review?" -s github

# Interactive chat
devassist chat -s github,atlassian

# Check status (env file, YAML, brief AI provider)
devassist setup status
```

## Workspace directory (`~/.devassist`)


| Path          | Purpose                                                                                                             |
| ------------- | ------------------------------------------------------------------------------------------------------------------- |
| `env`         | Canonical shell-style exports (API keys, Atlassian URL, Vertex project, etc.).                                      |
| `.env`        | Legacy mirror of `env` for existing scripts that `source ~/.devassist/.env`.                                        |
| `config.yaml` | Non-secret app config: enabled sources, `**ai.provider**` / `**ai.project_id**` / region, MCP entries, preferences. |
| `briefs/`     | Generated morning brief output (daemon).                                                                            |
| `daemon.log`  | Daemon log file when using the background script.                                                                   |


## Usage

### Morning brief (`devassist brief`)

Briefs summarize aggregated context using **Anthropic Claude** by default (`config.yaml` → `ai.provider: anthropic`), matching the usual `ask` / chat path and avoiding Vertex-only Gemini setup when you do not need it.

- **Gemini on Vertex** (when you already use GCP for Claude or want Flash on Vertex): set `ai.provider` to `gemini` in `config.yaml`, or export `DEVASSIST_AI_PROVIDER=gemini` / `vertex`, and ensure `ai.project_id` and region are set. Running `**devassist setup init`** and choosing Vertex AI updates both `env` and `**config.yaml**` accordingly.
- **Override for one run:** `devassist brief -p gemini` or `devassist brief -p anthropic`.

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
├── ai/            # LLM clients (Anthropic brief, Vertex Gemini, prompts)
├── preferences/   # Preference learning (planned)
└── models/        # Pydantic data models
```

## MCP Servers


| Server    | Package                                           | Purpose                       |
| --------- | ------------------------------------------------- | ----------------------------- |
| GitHub    | `@modelcontextprotocol/server-github`             | PRs, issues, repos            |
| Atlassian | `mcp-remote` → `https://mcp.atlassian.com/v1/mcp` | Jira, Confluence (hosted MCP) |


## Troubleshooting

### "No MCP servers configured"

- Run `devassist setup status` to check configuration
- Ensure credentials exist: `~/.devassist/env` (or `source ~/.devassist/env` for other tools in the shell)

### Atlassian MCP slow or auth issues

- First run downloads `mcp-remote`; ensure outbound HTTPS is allowed
- Authentication follows Atlassian’s remote MCP flow (browser/OAuth as prompted by the connector)
- Large Jira searches may take 30–60 seconds

### GitHub MCP asks for repo details

- Use specific search syntax: "Search for PRs using is:pr is:open review-requested:@me"
- The LLM needs guidance on GitHub search queries

### Command not found: devassist

- Run `uv sync --extra dev` so `.venv` exists and the `devassist` console script is installed.
- Or activate the venv and retry: `source .venv/bin/activate`
- Without uv: `pip install -e .`

## Development

Use `uv run` so tools use the project environment:

```bash
uv run pytest
uv run pytest --cov=devassist
uv run mypy src/
uv run ruff check src/
```

After changing dependencies in `pyproject.toml`, refresh the lockfile with `uv lock` and commit `uv.lock` alongside your edits.

## Requirements

- Python 3.11+ (managed automatically when using uv with `.python-version`)
- uv (recommended) — optional; pip still works with `pip install -e ".[dev]"`.
- Node.js 18+ (for MCP servers)
- **Claude AI access** (one of the following):
  - Anthropic API key from [console.anthropic.com](https://console.anthropic.com) (paid)
  - OR Red Hat employees: Use Vertex AI with `ANTHROPIC_VERTEX_PROJECT_ID=itpc-gcp-ai-eng-claude`
- **GitHub**: Personal Access Token (free) - [Create here](https://github.com/settings/tokens)
- **Jira/Atlassian**: Access to an Atlassian Cloud site (OAuth - browser login on first use)

## Environment Variables Reference

Variables below can be stored in `**~/.devassist/env`** (recommended) or exported in the shell. `**DEVASSIST_***` overrides apply when set in the environment (including inside `env`) and merge with `**config.yaml**` at runtime via `ConfigManager`.


| Variable                       | Required | Description                                                                                               |
| ------------------------------ | -------- | --------------------------------------------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY`            | Yes*     | Anthropic API key for Claude (`ask`, chat, **brief** default)                                             |
| `CLAUDE_CODE_USE_VERTEX`       | Yes*     | Set to `1` when using Claude via Vertex                                                                   |
| `CLOUD_ML_REGION`              | Yes*     | GCP region for Vertex (e.g. `us-east5`)                                                                   |
| `ANTHROPIC_VERTEX_PROJECT_ID`  | Yes*     | GCP project ID for Vertex AI                                                                              |
| `DEVASSIST_AI_PROVIDER`        | No       | `anthropic` or `gemini` — brief summarization backend; persisted by `devassist config sync` when in `env` |
| `DEVASSIST_AI_PROJECT_ID`      | No       | Overrides `ai.project_id` in YAML (Gemini / Vertex brief)                                                 |
| `DEVASSIST_AI_LOCATION`        | No       | Overrides `ai.location` (GCP region for Gemini on Vertex)                                                 |
| `DEVASSIST_AI_MODEL`           | No       | Overrides `ai.model` (Gemini model id)                                                                    |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | Yes      | GitHub PAT with repo, notifications scopes                                                                |
| `ATLASSIAN_BASE_URL`           | No       | Optional; for `devassist brief` Jira adapter (not MCP remote)                                             |
| `ATLASSIAN_EMAIL`              | No       | Optional; same                                                                                            |
| `ATLASSIAN_API_TOKEN`          | No       | Optional; same                                                                                            |
| `SLACK_BOT_TOKEN`              | No       | Slack bot token (xoxb-...)                                                                                |
| `SLACK_TEAM_ID`                | No       | Slack workspace ID                                                                                        |


Either Anthropic API key OR Vertex AI (`CLAUDE_CODE_USE_VERTEX` + project id) config for Claude-powered flows

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `uv run pytest`
5. Submit a pull request

