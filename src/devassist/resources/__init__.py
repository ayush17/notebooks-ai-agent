"""Resources for DevAssist.

Contains system prompts and MCP server configurations.
"""

from pathlib import Path

RESOURCES_DIR = Path(__file__).parent
DEV_ASSIST_SYSTEM_PROMPT_FILE = RESOURCES_DIR / "dev-assistant.md"
PERSONAL_ASSIST_SYSTEM_PROMPT_FILE = RESOURCES_DIR / "personal-assistant.md"
MCP_SERVERS_FILE = RESOURCES_DIR / "mcp-servers.json"

def get_dev_assistant_system_prompt() -> str:
    """Load the system prompt from file.

    Returns:
        System prompt string.
    """
    if not DEV_ASSIST_SYSTEM_PROMPT_FILE.exists():
        return "You are a helpful executive assistant, who goes through my info and creates a concise and prioritized summary of action items for me."
    return DEV_ASSIST_SYSTEM_PROMPT_FILE.read_text()

def get_personal_assistant_system_prompt() -> str:
    """Load the system prompt from file.

    Returns:
        System prompt string.
    """
    if not PERSONAL_ASSIST_SYSTEM_PROMPT_FILE.exists():
        return "You are a helpful developer assistant."
    return PERSONAL_ASSIST_SYSTEM_PROMPT_FILE.read_text()


def get_mcp_servers_config() -> dict:
    """Load MCP servers configuration from file.

    Returns:
        Dictionary of MCP server configurations.
    """
    import json

    if not MCP_SERVERS_FILE.exists():
        return {}

    with open(MCP_SERVERS_FILE) as f:
        return json.load(f)
