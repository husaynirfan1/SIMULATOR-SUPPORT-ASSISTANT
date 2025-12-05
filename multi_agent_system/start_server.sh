#!/bin/bash

# Start the multi-agent system FastAPI server

echo "Starting Multi-Agent System API Server..."
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Set environment variables
export MORPHIK_URI=${MORPHIK_URI:-"http://localhost:8000"}

echo ""
echo "Starting server on http://0.0.0.0:8001"
echo "API docs available at http://localhost:8001/docs"
echo ""

# Start the server
python server.py
