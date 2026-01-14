#!/bin/bash

# Enhanced Business Agent - Stop Script

echo "🛑 Stopping Enhanced Business Agent..."

# Read PIDs and kill processes
if [ -f "pids/backend.pid" ]; then
    kill $(cat pids/backend.pid) 2>/dev/null && echo "✓ Backend stopped"
    rm pids/backend.pid
fi

if [ -f "pids/chat.pid" ]; then
    kill $(cat pids/chat.pid) 2>/dev/null && echo "✓ Chat interface stopped"
    rm pids/chat.pid
fi

if [ -f "pids/merchant.pid" ]; then
    kill $(cat pids/merchant.pid) 2>/dev/null && echo "✓ Merchant portal stopped"
    rm pids/merchant.pid
fi

# Kill all processes on the specified ports (more reliable method)
# Kill backend on port 8452
pkill -f "python.*main\.py" 2>/dev/null || true
fuser -k 8452/tcp 2>/dev/null || true

# Kill chat interface on port 8450
pkill -f "vite.*8450" 2>/dev/null || true
fuser -k 8450/tcp 2>/dev/null || true

# Kill merchant portal on port 8451
pkill -f "vite.*8451" 2>/dev/null || true
fuser -k 8451/tcp 2>/dev/null || true

# Cleanup PID files
rm -f pids/*.pid 2>/dev/null || true

echo "✓ All services stopped"
