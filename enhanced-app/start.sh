#!/bin/bash

# Enhanced Business Agent - Startup Script
# This script starts all components of the application

set -e

echo "🚀 Starting Enhanced Business Agent..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create necessary directories
mkdir -p logs
mkdir -p pids

# Load environment variables first
if [ -f ".env" ]; then
    echo -e "${BLUE}Loading environment variables...${NC}"
    export $(cat .env | grep -v '^#' | xargs)
    echo -e "${GREEN}✓ Environment variables loaded${NC}"
else
    echo -e "${YELLOW}⚠ Warning: .env file not found${NC}"
fi

echo ""

# Set defaults if not in environment
OLLAMA_URL=${OLLAMA_URL:-http://localhost:11434}
OLLAMA_MODEL=${OLLAMA_MODEL:-qwen2.5:latest}

# Extract host from OLLAMA_URL (remove http:// and port)
OLLAMA_HOST=$(echo $OLLAMA_URL | sed 's|http://||' | sed 's|:[0-9]*$||')
OLLAMA_PORT=$(echo $OLLAMA_URL | grep -oP ':\K[0-9]+$' || echo "11434")

# Check if Ollama is running
echo -e "${BLUE}Checking Ollama connection at ${OLLAMA_URL}...${NC}"
if curl -s ${OLLAMA_URL}/api/version > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ollama is running${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Ollama is not running at ${OLLAMA_URL}${NC}"
    echo -e "${YELLOW}  Please start Ollama and ensure ${OLLAMA_MODEL} is installed${NC}"
    echo -e "${YELLOW}  Run: ollama pull ${OLLAMA_MODEL}${NC}"
fi

echo ""

# Start Backend
echo -e "${BLUE}Starting Backend Server...${NC}"
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv || python -m venv venv
fi

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo -e "${YELLOW}⚠ Error: Failed to create virtual environment${NC}"
    exit 1
fi

# Install dependencies
echo "Installing Python dependencies..."
pip install -q -r requirements.txt

# Start backend in background
echo -e "${GREEN}✓ Starting backend on port 8451${NC}"
python main.py > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../pids/backend.pid

cd ..

# Wait for backend to start
echo "Waiting for backend to be ready..."
sleep 3

# Start Chat Frontend
echo ""
echo -e "${BLUE}Starting Chat Interface...${NC}"
cd frontend/chat

if [ ! -d "node_modules" ]; then
    echo "Installing Chat dependencies..."
    npm install
fi

echo -e "${GREEN}✓ Starting chat interface on port 8450${NC}"
npm run dev > ../../logs/chat.log 2>&1 &
CHAT_PID=$!
echo $CHAT_PID > ../../pids/chat.pid

cd ../..

# Start Merchant Portal
echo ""
echo -e "${BLUE}Starting Merchant Portal...${NC}"
cd frontend/merchant-portal

if [ ! -d "node_modules" ]; then
    echo "Installing Merchant Portal dependencies..."
    npm install
fi

echo -e "${GREEN}✓ Starting merchant portal on port 8451${NC}"
npm run dev > ../../logs/merchant.log 2>&1 &
MERCHANT_PID=$!
echo $MERCHANT_PID > ../../pids/merchant.pid

cd ../..

# Wait a bit for everything to start
sleep 5

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✨ Enhanced Business Agent is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "📱 ${BLUE}Chat Interface:${NC}      http://localhost:8450"
echo -e "🏪 ${BLUE}Merchant Portal:${NC}     http://localhost:8451"
echo -e "📚 ${BLUE}API Documentation:${NC}   http://localhost:8451/docs"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""
echo "📋 Logs:"
echo "   Backend:         tail -f logs/backend.log"
echo "   Chat:            tail -f logs/chat.log"
echo "   Merchant Portal: tail -f logs/merchant.log"
echo ""

# Wait for Ctrl+C
trap 'echo -e "\n${YELLOW}Stopping all services...${NC}"; kill $BACKEND_PID $CHAT_PID $MERCHANT_PID 2>/dev/null; rm -f pids/*.pid; echo -e "${GREEN}✓ All services stopped${NC}"; exit 0' INT

# Keep script running
wait
