#!/bin/bash

# Enhanced Business Agent - Split Backend Stop Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDS_DIR="$SCRIPT_DIR/pids"

echo "============================================"
echo "  Stopping Enhanced Business Agent"
echo "  (Split Backend Architecture)"
echo "============================================"
echo ""

# Function to stop a service
stop_service() {
    local service_name=$1
    local pid_file="$PIDS_DIR/${service_name}.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping $service_name (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 1
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                echo "  Force stopping $service_name..."
                kill -9 "$pid" 2>/dev/null || true
            fi
            echo "✓ $service_name stopped"
        else
            echo "⚠️  $service_name (PID: $pid) not running"
        fi
        rm -f "$pid_file"
    else
        echo "⚠️  No PID file found for $service_name"
    fi
}

# Stop all services
stop_service "trusted-service"
stop_service "merchant-backend"
stop_service "chat-backend"
stop_service "chat-frontend"
stop_service "merchant-portal"

# Also kill any remaining processes on the ports (backup cleanup)
echo ""
echo "Cleaning up any remaining processes on ports..."

for port in 8450 8451 8452 8453 8454; do
    pids=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "Killing processes on port $port: $pids"
        kill -9 $pids 2>/dev/null || true
    fi
done

# Clean up any orphaned vite/node processes
echo ""
echo "Cleaning up orphaned vite and node processes..."
pkill -f "vite --port 8450" 2>/dev/null || true
pkill -f "vite --port 8451" 2>/dev/null || true
pkill -f "esbuild --service" 2>/dev/null || true

# Clean up orphaned python processes
echo "Cleaning up orphaned python processes..."
pkill -f "python.*main.py" 2>/dev/null || true
pkill -f "uvicorn" 2>/dev/null || true

# Clean up log and pid files
echo "Cleaning up old PID files..."
rm -f "$PIDS_DIR"/*.pid 2>/dev/null || true

echo ""
echo "============================================"
echo "  ✓ All services stopped successfully"
echo "  ✓ Background processes cleaned up"
echo "============================================"
echo ""
