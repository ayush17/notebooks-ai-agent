#!/bin/bash
# DevAssist Setup for Red Hat Employees
# Uses Claude on Vertex AI (Red Hat's corporate setup)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"
CONFIG_DIR="$HOME/.devassist"
ENV_FILE="$CONFIG_DIR/.env"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   DevAssist Setup for Red Hat Employees        ║${NC}"
echo -e "${BLUE}║   (Uses Claude on Vertex AI)                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Create config directory
mkdir -p "$CONFIG_DIR"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI not found${NC}"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check gcloud auth
echo -e "${CYAN}Checking GCP authentication...${NC}"
if ! gcloud auth application-default print-access-token &> /dev/null; then
    echo -e "${YELLOW}You need to authenticate with GCP first.${NC}"
    echo ""
    echo "Running: gcloud auth application-default login"
    gcloud auth application-default login
    
    echo ""
    echo "Setting quota project..."
    gcloud auth application-default set-quota-project cloudability-it-gemini
fi
echo -e "${GREEN}✓ GCP authentication OK${NC}"

# Get/confirm project ID
echo ""
echo -e "${CYAN}GCP Project Configuration${NC}"
echo -e "Find your project ID in the Red Hat spreadsheet (see Claude setup docs)"
echo -e "It should match your team's reporting structure."
echo ""

CURRENT_PROJECT="${ANTHROPIC_VERTEX_PROJECT_ID:-}"
if [ -n "$CURRENT_PROJECT" ]; then
    echo -e "Current project: ${GREEN}$CURRENT_PROJECT${NC}"
    read -p "Keep this project? [Y/n]: " keep_project
    if [[ "$keep_project" =~ ^[Nn] ]]; then
        read -p "Enter your GCP Project ID: " ANTHROPIC_VERTEX_PROJECT_ID
    else
        ANTHROPIC_VERTEX_PROJECT_ID="$CURRENT_PROJECT"
    fi
else
    read -p "Enter your GCP Project ID: " ANTHROPIC_VERTEX_PROJECT_ID
fi

if [ -z "$ANTHROPIC_VERTEX_PROJECT_ID" ]; then
    echo -e "${RED}Error: Project ID is required${NC}"
    exit 1
fi

# GitHub Token
echo ""
echo -e "${CYAN}GitHub Configuration${NC}"
echo "Get a Personal Access Token from: https://github.com/settings/tokens"
echo "Required scopes: repo, notifications"
read -p "GitHub Personal Access Token: " GITHUB_PERSONAL_ACCESS_TOKEN

# Slack Configuration (optional)
echo ""
echo -e "${CYAN}Slack Configuration (optional)${NC}"
echo "Create a Slack App at: https://api.slack.com/apps"
echo "Or press Enter to skip"
read -p "Slack Bot Token (xoxb-...): " SLACK_BOT_TOKEN
if [ -n "$SLACK_BOT_TOKEN" ]; then
    read -p "Slack Team ID: " SLACK_TEAM_ID
fi

# Save configuration
echo ""
echo -e "${GREEN}Saving configuration...${NC}"

cat > "$ENV_FILE" << EOF
# DevAssist Environment Configuration for Red Hat
# Generated on $(date)
# Uses Claude on Vertex AI

# Claude on Vertex AI (Red Hat setup)
export CLAUDE_CODE_USE_VERTEX=1
export CLOUD_ML_REGION=us-east5
export ANTHROPIC_VERTEX_PROJECT_ID="$ANTHROPIC_VERTEX_PROJECT_ID"

# GitHub
export GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_PERSONAL_ACCESS_TOKEN"

# Slack (optional)
export SLACK_BOT_TOKEN="$SLACK_BOT_TOKEN"
export SLACK_TEAM_ID="$SLACK_TEAM_ID"

# LLM Provider (using anthropic client with Vertex backend)
export LLM_PROVIDER="anthropic"
EOF

chmod 600 "$ENV_FILE"

# Also add to shell rc if not present
SHELL_RC="$HOME/.zshrc"
if [ -f "$HOME/.bashrc" ] && [ ! -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if ! grep -q "CLAUDE_CODE_USE_VERTEX" "$SHELL_RC" 2>/dev/null; then
    echo ""
    echo -e "${YELLOW}Adding Vertex AI config to $SHELL_RC...${NC}"
    cat >> "$SHELL_RC" << EOF

# DevAssist / Claude on Vertex AI
export CLAUDE_CODE_USE_VERTEX=1
export CLOUD_ML_REGION=us-east5
export ANTHROPIC_VERTEX_PROJECT_ID="$ANTHROPIC_VERTEX_PROJECT_ID"
EOF
    echo -e "${GREEN}✓ Added to $SHELL_RC${NC}"
fi

echo ""
echo -e "${GREEN}✓ Configuration saved to $ENV_FILE${NC}"

# Test the setup
echo ""
echo -e "${CYAN}Testing configuration...${NC}"

# Test GitHub
if [ -n "$GITHUB_PERSONAL_ACCESS_TOKEN" ]; then
    echo -n "  GitHub: "
    if curl -s -H "Authorization: Bearer $GITHUB_PERSONAL_ACCESS_TOKEN" https://api.github.com/user | grep -q '"login"'; then
        GITHUB_USER=$(curl -s -H "Authorization: Bearer $GITHUB_PERSONAL_ACCESS_TOKEN" https://api.github.com/user | grep '"login"' | cut -d'"' -f4)
        echo -e "${GREEN}✓ Connected as $GITHUB_USER${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
fi

# Test Slack
if [ -n "$SLACK_BOT_TOKEN" ]; then
    echo -n "  Slack: "
    if curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" https://slack.com/api/auth.test | grep -q '"ok":true'; then
        echo -e "${GREEN}✓ Connected${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
fi

# Test Vertex AI
echo -n "  Claude on Vertex AI: "
if gcloud auth application-default print-access-token &> /dev/null; then
    echo -e "${GREEN}✓ Authenticated${NC}"
else
    echo -e "${RED}✗ Not authenticated${NC}"
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════${NC}"
echo ""
echo "To use DevAssist:"
echo ""
echo -e "  ${BLUE}# Load environment${NC}"
echo -e "  source ~/.devassist/.env"
echo ""
echo -e "  ${BLUE}# From repo root: sync deps (creates .venv)${NC}"
echo -e "  uv sync --extra dev"
echo ""
echo -e "  ${BLUE}# Activate virtual environment (optional — or use uv run)${NC}"
echo -e "  source $VENV_DIR/bin/activate"
echo ""
echo -e "  ${BLUE}# Ask a question${NC}"
echo -e "  uv run devassist ask 'What are my GitHub notifications?' -s github"
echo ""
echo -e "  ${BLUE}# Start background daemon${NC}"
echo -e "  ./scripts/start_daemon.sh"
echo ""
