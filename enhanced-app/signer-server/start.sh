#!/bin/bash

# Signer Server Startup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"

echo "============================================"
echo "  Signer Server (Affinidi TDK)"
echo "============================================"
echo ""

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  Port $port is already in use!"
        echo "    Stopping existing process..."
        lsof -ti :$port | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
}

# Check and clear port 8454
echo "Checking port 8454..."
check_port 8454

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_PATH"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "Starting Signer Server..."
echo "----------------------------"

# Check if .env exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "    Copy .env.example to .env and configure Affinidi credentials"
    exit 1
fi

# Start the server
cd "$SCRIPT_DIR"
python main.py

# Deactivate on exit
deactivate
