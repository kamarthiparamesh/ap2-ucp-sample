#!/bin/bash

# Merchant Backend Startup Script
# Starts the UCP-compliant merchant backend with Affinidi wallet support

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH="$PROJECT_ROOT/.venv"

echo "============================================"
echo "  Merchant Backend (UCP Server)"
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

# Check and clear port 8453
echo "Checking port 8453..."
check_port 8453

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

# Install Affinidi packages first (they require pydantic v1)
pip install -q affinidi-tdk-wallets-client affinidi-tdk-auth-provider

# Install other packages compatible with pydantic v1
# FastAPI 0.95.x is the last version compatible with pydantic v1
pip install -q -r <(python3 -c "
import sys
deps = [
    'fastapi>=0.95.0,<0.100.0',
    'uvicorn[standard]>=0.38.0',
    'pydantic<2.0.0,>=1.10.5',
    'sqlalchemy>=2.0.0',
    'aiosqlite>=0.19.0',
    'python-dotenv>=1.0.0',
    'httpx>=0.26.0',
    'cryptography>=41.0.0',
    'greenlet>=3.0.0',
]
for dep in deps:
    print(dep)
")

echo ""
echo "Starting Merchant Backend..."
echo "----------------------------"

# Check if .env exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "    Copy .env.example to .env and configure Affinidi credentials"
    echo "    The backend will start but Affinidi features will be disabled."
    echo ""
fi

# Start the backend
cd "$SCRIPT_DIR"
python main.py

# Deactivate on exit
deactivate
