#!/bin/bash

# Chat Backend Startup Script
# Starts the AI shopping assistant with UCP client

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH="$SCRIPT_DIR/.venv"

echo "============================================"
echo "  Chat Backend (UCP Client)"
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

# Check and clear port 8452
echo "Checking port 8452..."
check_port 8452

# Check if virtual environment exists and is valid
if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "Creating Python virtual environment..."
    rm -rf "$VENV_PATH"  # Remove any incomplete venv
    python3 -m venv "$VENV_PATH"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip

# Install chat backend dependencies
pip install -q -r <(python3 -c "
import sys
deps = [
    'fastapi>=0.109.0',
    'uvicorn[standard]>=0.38.0',
    'pydantic[email]>=2.12.0',
    'python-dotenv>=1.0.0',
    'httpx>=0.26.0',
    'langchain-ollama>=0.1.0',
    'langchain-core>=0.2.0',
    'sqlalchemy>=2.0.0',
    'aiosqlite>=0.19.0',
    'cryptography>=41.0.0',
    'email_validator>=2.0.0',
    'greenlet>=3.0.0',
]
for dep in deps:
    print(dep)
")

echo ""
echo "Starting Chat Backend..."
echo "----------------------------"

# Check if .env exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "    The backend will start with default configuration."
    echo ""
fi

# Start the backend
cd "$SCRIPT_DIR"
python main.py

# Deactivate on exit
deactivate
