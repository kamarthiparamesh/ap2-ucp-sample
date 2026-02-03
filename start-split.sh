#!/bin/bash

# Enhanced Business Agent - Split Backend Startup Script
# This script starts both chat and merchant backends communicating via UCP

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDS_DIR="$SCRIPT_DIR/pids"
LOGS_DIR="$SCRIPT_DIR/logs"

# Create directories if they don't exist
mkdir -p "$PIDS_DIR"
mkdir -p "$LOGS_DIR"

echo "============================================"
echo "  Enhanced Business Agent - Split Backend"
echo "  with UCP Communication"
echo "============================================"
echo ""

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  Port $port is already in use!"
        echo "    Please stop the process using this port or change the PORT in .env"
        return 1
    fi
    return 0
}

# Function to wait for a service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=0

    echo "Waiting for $name to be ready..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo "✓ $name is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done

    echo "✗ $name failed to start within 30 seconds"
    return 1
}

# Check ports
echo "Checking ports..."
check_port 8450 || exit 1  # Chat frontend
check_port 8451 || exit 1  # Merchant portal frontend
check_port 8452 || exit 1  # Chat backend
check_port 8453 || exit 1  # Merchant backend
check_port 8454 || exit 1  # Signer server

echo ""
echo "Step 1: Starting Signer Server (Affinidi TDK)"
echo "----------------------------------------------"
cd "$SCRIPT_DIR/signer-server"

# Start signer server using its own start.sh
echo "Starting Signer Server on port 8454..."
nohup bash start.sh > "$LOGS_DIR/signer-server.log" 2>&1 &
SIGNER_PID=$!
echo $SIGNER_PID > "$PIDS_DIR/signer-server.pid"
echo "✓ Signer Server started (PID: $SIGNER_PID)"

# Wait for signer server to be ready
wait_for_service "http://localhost:8454/health" "Signer Server" || exit 1

echo ""
echo "Step 2: Starting Merchant Backend (UCP Server)"
echo "----------------------------------------------"
cd "$SCRIPT_DIR/merchant-backend"

# Start merchant backend using its own start.sh
echo "Starting Merchant Backend on port 8453..."
nohup bash start.sh > "$LOGS_DIR/merchant-backend.log" 2>&1 &
MERCHANT_PID=$!
echo $MERCHANT_PID > "$PIDS_DIR/merchant-backend.pid"
echo "✓ Merchant Backend started (PID: $MERCHANT_PID)"

# Wait for merchant backend to be ready
wait_for_service "http://localhost:8453/health" "Merchant Backend" || exit 1

echo ""
echo "Step 3: Starting Chat Backend (UCP Client)"
echo "-------------------------------------------"
cd "$SCRIPT_DIR/chat-backend"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment for chat backend..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
echo "Installing chat backend dependencies..."
pip install -q --upgrade pip
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

# Start chat backend
echo "Starting Chat Backend on port 8452..."
nohup python3 main.py > "$LOGS_DIR/chat-backend.log" 2>&1 &
CHAT_PID=$!
echo $CHAT_PID > "$PIDS_DIR/chat-backend.pid"
echo "✓ Chat Backend started (PID: $CHAT_PID)"
deactivate

# Wait for chat backend to be ready
wait_for_service "http://localhost:8452/health" "Chat Backend" || exit 1

echo ""
echo "Step 4: Starting Frontend Applications"
echo "---------------------------------------"

# Start Chat Frontend
cd "$SCRIPT_DIR/frontend/chat"
if [ ! -d "node_modules" ]; then
    echo "Installing chat frontend dependencies..."
    npm install --silent
fi

echo "Starting Chat Frontend on port 8450..."
nohup npm run dev > "$LOGS_DIR/chat-frontend.log" 2>&1 &
CHAT_FRONTEND_PID=$!
echo $CHAT_FRONTEND_PID > "$PIDS_DIR/chat-frontend.pid"
echo "✓ Chat Frontend started (PID: $CHAT_FRONTEND_PID)"

# Start Merchant Portal Frontend
cd "$SCRIPT_DIR/frontend/merchant-portal"
if [ ! -d "node_modules" ]; then
    echo "Installing merchant portal dependencies..."
    npm install --silent
fi

echo "Starting Merchant Portal on port 8451..."
nohup npm run dev > "$LOGS_DIR/merchant-portal.log" 2>&1 &
MERCHANT_FRONTEND_PID=$!
echo $MERCHANT_FRONTEND_PID > "$PIDS_DIR/merchant-portal.pid"
echo "✓ Merchant Portal started (PID: $MERCHANT_FRONTEND_PID)"

echo ""
echo "============================================"
echo "  🚀 All Services Started Successfully!"
echo "============================================"
echo ""
echo "Services:"
echo "  • Chat Interface:                 http://localhost:8450"
echo "    - Domain:                       https://chat.abhinava.xyz"
echo ""
echo "  • Merchant Portal:                http://localhost:8451"
echo "    - Domain:                       https://app.abhinava.xyz"
echo ""
echo "  • Chat Backend (UCP Client):      http://localhost:8452"
echo "    - Health:                       http://localhost:8452/health"
echo "    - API Docs:                     http://localhost:8452/docs"
echo ""
echo "  • Merchant Backend (UCP Server):  http://localhost:8453"
echo "    - Health:                       http://localhost:8453/health"
echo "    - UCP Discovery:                http://localhost:8453/.well-known/ucp"
echo "    - API Docs:                     http://localhost:8453/docs"
echo ""
echo "  • Signer Server (Affinidi TDK):   http://localhost:8454"
echo "    - Health:                       http://localhost:8454/health"
echo "    - DID Generation:               http://localhost:8454/api/did-web-generate"
echo "    - JWT Signing:                  http://localhost:8454/api/sign-jwt"
echo ""
echo "Logs:"
echo "  • Signer Server:                  $LOGS_DIR/signer-server.log"
echo "  • Merchant Backend:               $LOGS_DIR/merchant-backend.log"
echo "  • Chat Backend:                   $LOGS_DIR/chat-backend.log"
echo "  • Chat Frontend:                  $LOGS_DIR/chat-frontend.log"
echo "  • Merchant Portal:                $LOGS_DIR/merchant-portal.log"
echo ""
echo "To stop all services, run: ./stop-split.sh"
echo ""
echo "UCP Architecture:"
echo "  Chat Frontend (8450) → Chat Backend (8452)"
echo "                         ↓ (UCP REST)"
echo "                         Merchant Backend (8453) → Signer Server (8454)"
echo "  Merchant Portal (8451) → Merchant Backend (8453) → Signer Server (8454)"
echo ""
