# DevAssist - Developer Assistant CLI

A Python CLI application that aggregates context from multiple developer tools (Gmail, Slack, JIRA, GitHub) and uses AI to generate a Unified Morning Brief and other productivity features.

## Features

- **Unified Morning Brief**: Consolidated summary from all your communication and work tracking tools
- **Context Source Configuration**: Easy setup for Gmail, Slack, JIRA, and GitHub integrations
- **Preference Learning**: (Planned) Learns your priorities over time to improve relevance
- **EC2 Sandbox Toggle**: (Planned) Start/stop development instances from the CLI
- **Auto-Response Drafts**: (Planned) AI-generated responses with human-in-the-loop approval
- **Quarterly Notes**: (Planned) Generate contribution summaries for performance reviews

## Installation

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

## Quick Start

```bash
# Configure GCP for AI features (required)
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# Add context sources (workspace directory ~/.devassist/ is created automatically)
# Each command will prompt for required credentials interactively
devassist config add gmail
devassist config add slack
devassist config add jira
devassist config add github

# Generate morning brief
devassist brief
```

## Usage

### Morning Brief

```bash
# Generate brief from all sources
devassist brief

# Brief from specific sources
devassist brief --sources gmail,jira

# Force refresh (ignore cache)
devassist brief --refresh

# JSON output
devassist brief --json
```

### Configuration

```bash
# List configured sources
devassist config list

# Test connections
devassist config test

# Remove a source
devassist config remove slack
```


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

## Architecture

```
src/devassist/
├── cli/         # Typer CLI commands
├── core/        # Business logic (aggregator, ranker, brief_generator)
├── adapters/    # Context source adapters (gmail, slack, jira, github)
├── ai/          # Vertex AI integration
├── preferences/ # Preference learning
└── models/      # Pydantic data models
```

## Requirements

- Python 3.11+
- GCP project with Vertex AI API enabled
- API credentials for desired integrations

## License

MIT License - see LICENSE file for details.
