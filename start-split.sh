#!/bin/bash
# Start all UCP sample services in split terminal mode

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENHANCED_APP_DIR="$SCRIPT_DIR/enhanced-app"

# Set LD_LIBRARY_PATH to find libsqlite3
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

echo "Starting UCP Sample Services..."

# Function to check if a port is in use
check_port() {
    lsof -i:$1 >/dev/null 2>&1 && echo "1" || echo "0"
}

# Start Chat Backend
echo "Starting Chat Backend (port 8452)..."
cd "$ENHANCED_APP_DIR/chat-backend"
if [ $(check_port 8452) == "1" ]; then
    echo "  ⚠ Port 8452 already in use, skipping..."
else
    source venv/bin/activate
    nohup python3 main.py > chat-backend.log 2>&1 &
    echo "  ✓ Chat backend started (PID: $!)"
    deactivate
fi

# Start Merchant Backend
echo "Starting Merchant Backend (port 8453)..."
cd "$ENHANCED_APP_DIR/merchant-backend"
if [ $(check_port 8453) == "1" ]; then
    echo "  ⚠ Port 8453 already in use, skipping..."
else
    source venv/bin/activate
    nohup python3 main.py > merchant-backend.log 2>&1 &
    echo "  ✓ Merchant backend started (PID: $!)"
    deactivate
fi

# Start Chat Frontend
echo "Starting Chat Frontend (port 8450)..."
cd "$ENHANCED_APP_DIR/frontend/chat"
if [ $(check_port 8450) == "1" ]; then
    echo "  ⚠ Port 8450 already in use, skipping..."
else
    nohup ./node_modules/.bin/vite > chat-frontend.log 2>&1 &
    echo "  ✓ Chat frontend started (PID: $!)"
fi

# Start Merchant Portal Frontend
echo "Starting Merchant Portal Frontend (port 8451)..."
cd "$ENHANCED_APP_DIR/frontend/merchant-portal"
if [ $(check_port 8451) == "1" ]; then
    echo "  ⚠ Port 8451 already in use, skipping..."
else
    nohup ./node_modules/.bin/vite > merchant-portal.log 2>&1 &
    echo "  ✓ Merchant portal started (PID: $!)"
fi

echo ""
echo "✅ All services started!"
echo ""
echo "Services:"
echo "  Chat Frontend:        http://localhost:8450"
echo "  Merchant Portal:      http://localhost:8451"
echo "  Chat Backend API:     http://localhost:8452"
echo "  Merchant Backend API: http://localhost:8453"
echo ""
echo "Logs:"
echo "  Chat Backend:         $ENHANCED_APP_DIR/chat-backend/chat-backend.log"
echo "  Merchant Backend:     $ENHANCED_APP_DIR/merchant-backend/merchant-backend.log"
echo "  Chat Frontend:        $ENHANCED_APP_DIR/frontend/chat/chat-frontend.log"
echo "  Merchant Portal:      $ENHANCED_APP_DIR/frontend/merchant-portal/merchant-portal.log"
