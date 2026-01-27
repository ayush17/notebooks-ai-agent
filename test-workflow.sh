#!/bin/bash
# Simple DevAssist Test Workflow
# Tests basic functionality without requiring API credentials

set -e  # Exit on error

echo "========================================="
echo "DevAssist Basic Functionality Test"
echo "========================================="

# Activate virtual environment
source .venv/bin/activate

echo -e "\n✓ Virtual environment activated"

# Step 1: Check version
echo -e "\n--- Step 1: Check version ---"
devassist --version

# Step 2: Check status (creates workspace)
echo -e "\n--- Step 2: Check status ---"
devassist status

# Step 3: Verify workspace was created
echo -e "\n--- Step 3: Verify workspace created ---"
if [ -d ~/.devassist ]; then
    echo "✓ Workspace directory exists: ~/.devassist/"
    ls -la ~/.devassist/
else
    echo "✗ Workspace directory NOT created"
    exit 1
fi

# Step 4: List available config commands
echo -e "\n--- Step 4: Available config commands ---"
devassist config --help

# Step 5: List configured sources (should be empty)
echo -e "\n--- Step 5: List configured sources ---"
devassist config list

# Step 6: Generate brief with no sources (should handle gracefully)
echo -e "\n--- Step 6: Generate brief (no sources) ---"
devassist brief

# Step 7: Test brief with JSON output
echo -e "\n--- Step 7: Generate brief (JSON format) ---"
devassist brief --json

# Step 8: Run unit tests
echo -e "\n--- Step 8: Run unit tests ---"
pytest tests/unit/ -v --tb=short -q

echo -e "\n========================================="
echo "✓ All basic functionality tests passed!"
echo "========================================="
echo ""
echo "Next steps to test with real data:"
echo "1. Set up GCP credentials: gcloud auth application-default login"
echo "2. Add a source: devassist config add gmail"
echo "3. Generate a real brief: devassist brief"
