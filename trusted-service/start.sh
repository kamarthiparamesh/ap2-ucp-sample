#!/bin/bash

# Trusted Service Startup Script

echo "Starting Trusted Service..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Please create .env file with Affinidi credentials"
    exit 1
fi

# Check if node_modules exists
if [ ! -d node_modules ]; then
    echo "Installing dependencies..."
    npm install
fi

# Build TypeScript
echo "Building TypeScript..."
npm run build

# Start server
echo "Starting server..."
npm start
