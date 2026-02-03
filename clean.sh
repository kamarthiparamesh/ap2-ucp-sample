#!/bin/bash

# Cleanup Script - Removes logs, PIDs, and virtual environments

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo "  Cleanup Script"
echo "============================================"
echo ""
echo "This will remove:"
echo "  - All log files"
echo "  - All PID files"
echo "  - All Python virtual environments"
echo "  - All node_modules directories"
echo ""
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Cleaning up..."

# Clean vent
if [ -d "$SCRIPT_DIR/.venv" ]; then
    echo "✓ Removing .venv/"
    rm -rf "$SCRIPT_DIR/.venv"
fi

# Clean logs
if [ -d "$SCRIPT_DIR/logs" ]; then
    echo "✓ Removing logs/"
    rm -rf "$SCRIPT_DIR/logs"
fi

# Clean PIDs
if [ -d "$SCRIPT_DIR/pids" ]; then
    echo "✓ Removing pids/"
    rm -rf "$SCRIPT_DIR/pids"
fi

# Clean chat-backend
if [ -d "$SCRIPT_DIR/chat-backend/venv" ]; then
    echo "✓ Removing chat-backend/venv/"
    rm -rf "$SCRIPT_DIR/chat-backend/venv"
fi

if [ -d "$SCRIPT_DIR/chat-backend/__pycache__" ]; then
    echo "✓ Removing chat-backend/__pycache__/"
    rm -rf "$SCRIPT_DIR/chat-backend/__pycache__"
fi

# Clean merchant-backend
if [ -d "$SCRIPT_DIR/merchant-backend/venv" ]; then
    echo "✓ Removing merchant-backend/venv/"
    rm -rf "$SCRIPT_DIR/merchant-backend/venv"
fi

if [ -d "$SCRIPT_DIR/merchant-backend/__pycache__" ]; then
    echo "✓ Removing merchant-backend/__pycache__/"
    rm -rf "$SCRIPT_DIR/merchant-backend/__pycache__"
fi

# Clean signer-server
if [ -d "$SCRIPT_DIR/signer-server/venv" ]; then
    echo "✓ Removing signer-server/venv/"
    rm -rf "$SCRIPT_DIR/signer-server/venv"
fi

if [ -d "$SCRIPT_DIR/signer-server/__pycache__" ]; then
    echo "✓ Removing signer-server/__pycache__/"
    rm -rf "$SCRIPT_DIR/signer-server/__pycache__"
fi

if [ -d "$SCRIPT_DIR/signer-server/logs" ]; then
    echo "✓ Removing signer-server/logs/"
    rm -rf "$SCRIPT_DIR/signer-server/logs"
fi

# Clean frontend node_modules
if [ -d "$SCRIPT_DIR/frontend/chat/node_modules" ]; then
    echo "✓ Removing frontend/chat/node_modules/"
    rm -rf "$SCRIPT_DIR/frontend/chat/node_modules"
fi

if [ -d "$SCRIPT_DIR/frontend/merchant-portal/node_modules" ]; then
    echo "✓ Removing frontend/merchant-portal/node_modules/"
    rm -rf "$SCRIPT_DIR/frontend/merchant-portal/node_modules"
fi

# Clean database files
if [ -f "$SCRIPT_DIR/chat-backend/chat_backend.db" ]; then
    echo "✓ Removing chat-backend/chat_backend.db"
    rm -f "$SCRIPT_DIR/chat-backend/chat_backend.db"
fi

if [ -f "$SCRIPT_DIR/merchant-backend/merchant.db" ]; then
    echo "✓ Removing merchant-backend/merchant.db"
    rm -f "$SCRIPT_DIR/merchant-backend/merchant.db"
fi

# Clean a2a directories if they exist
if [ -d "$SCRIPT_DIR/a2a/business_agent/venv" ]; then
    echo "✓ Removing a2a/business_agent/venv/"
    rm -rf "$SCRIPT_DIR/a2a/business_agent/venv"
fi

if [ -d "$SCRIPT_DIR/a2a/chat-client/node_modules" ]; then
    echo "✓ Removing a2a/chat-client/node_modules/"
    rm -rf "$SCRIPT_DIR/a2a/chat-client/node_modules"
fi

# Clean rest/nodejs if it exists
if [ -d "$SCRIPT_DIR/rest/nodejs/node_modules" ]; then
    echo "✓ Removing rest/nodejs/node_modules/"
    rm -rf "$SCRIPT_DIR/rest/nodejs/node_modules"
fi

echo ""
echo "✓ Cleanup complete!"
echo ""
echo "To reinstall everything, run: ./start-split.sh"
