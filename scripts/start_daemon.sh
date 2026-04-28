#!/bin/bash
# Start DevAssist Daemon
# This script starts the background daemon for continuous operation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"
CONFIG_DIR="$HOME/.devassist"
PID_FILE="$CONFIG_DIR/daemon.pid"
LOG_FILE="$CONFIG_DIR/daemon.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Load environment
if [ -f "$CONFIG_DIR/.env" ]; then
    source "$CONFIG_DIR/.env"
else
    echo -e "${RED}Error: No configuration found.${NC}"
    echo "Run ./scripts/setup_credentials.sh first"
    exit 1
fi

# Activate virtual environment
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
else
    echo -e "${RED}Error: Virtual environment not found.${NC}"
    echo "Run: uv sync"
    exit 1
fi

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}Daemon already running (PID: $OLD_PID)${NC}"
        echo "Use ./scripts/stop_daemon.sh to stop it first"
        exit 1
    else
        rm "$PID_FILE"
    fi
fi

# Parse arguments
BACKGROUND=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--background)
            BACKGROUND=true
            shift
            ;;
        -f|--foreground)
            BACKGROUND=false
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      DevAssist Daemon Starting...      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

if [ "$BACKGROUND" = true ]; then
    echo -e "${GREEN}Starting in background mode...${NC}"
    nohup python "$SCRIPT_DIR/devassist_daemon.py" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo -e "${GREEN}✓ Daemon started (PID: $(cat $PID_FILE))${NC}"
    echo ""
    echo "Log file: $LOG_FILE"
    echo "Briefs saved to: $CONFIG_DIR/briefs/"
    echo ""
    echo "To stop: ./scripts/stop_daemon.sh"
    echo "To view logs: tail -f $LOG_FILE"
else
    echo -e "${GREEN}Starting in foreground mode...${NC}"
    echo "Press Ctrl+C to stop"
    echo ""
    python "$SCRIPT_DIR/devassist_daemon.py"
fi
