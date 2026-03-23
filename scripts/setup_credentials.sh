#!/bin/bash
# DevAssist Credential Setup Script
# This script helps you configure MCP server credentials

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"
CONFIG_DIR="$HOME/.devassist"
ENV_FILE="$CONFIG_DIR/.env"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   DevAssist Credential Setup Wizard    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Create config directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

# Initialize or load existing env file
if [ -f "$ENV_FILE" ]; then
    echo -e "${GREEN}Loading existing configuration...${NC}"
    source "$ENV_FILE"
fi

# Function to prompt for a credential
prompt_credential() {
    local var_name="$1"
    local prompt_text="$2"
    local current_value="${!var_name}"
    
    if [ -n "$current_value" ]; then
        echo -e "${YELLOW}$prompt_text${NC}"
        echo -e "  Current: ${GREEN}[configured]${NC}"
        read -p "  Enter new value (or press Enter to keep current): " new_value
        if [ -n "$new_value" ]; then
            eval "$var_name='$new_value'"
        fi
    else
        echo -e "${YELLOW}$prompt_text${NC}"
        read -p "  Enter value: " new_value
        eval "$var_name='$new_value'"
    fi
}

echo -e "\n${BLUE}=== GitHub Configuration ===${NC}"
echo "Get a Personal Access Token from: https://github.com/settings/tokens"
echo "Required scopes: repo, notifications"
prompt_credential "GITHUB_PERSONAL_ACCESS_TOKEN" "GitHub Personal Access Token:"

echo -e "\n${BLUE}=== Slack Configuration ===${NC}"
echo "Create a Slack App at: https://api.slack.com/apps"
echo "Get Bot Token from: OAuth & Permissions > Bot User OAuth Token"
prompt_credential "SLACK_BOT_TOKEN" "Slack Bot Token (xoxb-...):"
prompt_credential "SLACK_TEAM_ID" "Slack Team/Workspace ID:"

echo -e "\n${BLUE}=== Atlassian Rovo MCP Configuration (Jira/Confluence) ===${NC}"
echo "Uses official Atlassian Rovo MCP Server with OAuth authentication."
echo "On first use, you'll authenticate via your browser."
echo "Example URL: https://redhat.atlassian.net/"
prompt_credential "ATLASSIAN_SITE_URL" "Atlassian Site URL:"

echo -e "\n${BLUE}=== LLM Configuration ===${NC}"
echo "Choose your LLM provider:"
echo "  1) Anthropic (Claude) - Recommended"
echo "  2) Google Vertex AI (Gemini)"
read -p "Selection [1]: " llm_choice
llm_choice=${llm_choice:-1}

if [ "$llm_choice" == "1" ]; then
    echo "Get API key from: https://console.anthropic.com/settings/keys"
    prompt_credential "ANTHROPIC_API_KEY" "Anthropic API Key:"
    LLM_PROVIDER="anthropic"
else
    echo "Run: gcloud auth application-default login"
    prompt_credential "GOOGLE_CLOUD_PROJECT" "GCP Project ID:"
    LLM_PROVIDER="vertex"
fi

# Save to env file
echo -e "\n${GREEN}Saving configuration...${NC}"
cat > "$ENV_FILE" << EOF
# DevAssist Environment Configuration
# Generated on $(date)

# GitHub
export GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_PERSONAL_ACCESS_TOKEN"

# Slack
export SLACK_BOT_TOKEN="$SLACK_BOT_TOKEN"
export SLACK_TEAM_ID="$SLACK_TEAM_ID"

# Atlassian Rovo MCP (Jira/Confluence/Compass)
# Uses OAuth - will prompt for browser authentication on first use
export ATLASSIAN_SITE_URL="$ATLASSIAN_SITE_URL"

# LLM Provider
export LLM_PROVIDER="$LLM_PROVIDER"
export ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
export GOOGLE_CLOUD_PROJECT="$GOOGLE_CLOUD_PROJECT"
EOF

chmod 600 "$ENV_FILE"

echo -e "\n${GREEN}✓ Configuration saved to $ENV_FILE${NC}"
echo -e "${YELLOW}Note: Keep this file secure - it contains sensitive credentials${NC}"

# Test the configuration
echo -e "\n${BLUE}Testing configuration...${NC}"
source "$ENV_FILE"
source "$VENV_DIR/bin/activate" 2>/dev/null || true

if [ -n "$GITHUB_PERSONAL_ACCESS_TOKEN" ]; then
    echo -n "  GitHub: "
    if curl -s -H "Authorization: Bearer $GITHUB_PERSONAL_ACCESS_TOKEN" https://api.github.com/user | grep -q '"login"'; then
        echo -e "${GREEN}✓ Connected${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
fi

if [ -n "$SLACK_BOT_TOKEN" ]; then
    echo -n "  Slack: "
    if curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" https://slack.com/api/auth.test | grep -q '"ok":true'; then
        echo -e "${GREEN}✓ Connected${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
fi

if [ -n "$ATLASSIAN_SITE_URL" ]; then
    echo -e "  Atlassian: ${YELLOW}OAuth (will authenticate on first use)${NC}"
fi

echo -e "\n${GREEN}Setup complete!${NC}"
echo -e "To start DevAssist, run:"
echo -e "  ${BLUE}source ~/.devassist/.env && devassist ask 'your question' -s github,atlassian${NC}"
echo -e "\nOr start an interactive chat session:"
echo -e "  ${BLUE}source ~/.devassist/.env && devassist chat -s github,atlassian${NC}"
