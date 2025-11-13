#!/bin/bash
# Script to run the backend server
cd "$(dirname "$0")"

PORT=8000

# Function to check if port is in use and kill the process
check_and_kill_port() {
    local port=$1
    
    # Check if port is in use
    if command -v lsof >/dev/null 2>&1; then
        PID=$(lsof -ti :$port 2>/dev/null)
    elif command -v netstat >/dev/null 2>&1; then
        PID=$(netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $7}' | cut -d'/' -f1 | head -1)
    elif command -v ss >/dev/null 2>&1; then
        PID=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -oP 'pid=\K[0-9]+' | head -1)
    else
        echo "Warning: Could not find lsof, netstat, or ss. Cannot check port $port."
        return
    fi
    
    if [ -n "$PID" ]; then
        echo "Port $port is in use by process(es): $PID"
        echo "Killing process(es)..."
        kill -9 $PID 2>/dev/null
        sleep 1
        
        # Verify port is free
        if command -v lsof >/dev/null 2>&1; then
            REMAINING=$(lsof -ti :$port 2>/dev/null)
        elif command -v netstat >/dev/null 2>&1; then
            REMAINING=$(netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $7}' | cut -d'/' -f1 | head -1)
        elif command -v ss >/dev/null 2>&1; then
            REMAINING=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -oP 'pid=\K[0-9]+' | head -1)
        fi
        
        if [ -n "$REMAINING" ]; then
            echo "Warning: Some processes may still be using port $port. Trying to kill all uvicorn/python processes..."
            pkill -f "uvicorn.*$port" 2>/dev/null
            pkill -f "python.*main.py" 2>/dev/null
            sleep 1
        else
            echo "✓ Port $port is now free"
        fi
    else
        echo "Port $port is free"
    fi
}

# Check and kill any process using port 8000
check_and_kill_port $PORT

# Start the backend server
echo "Starting backend server on port $PORT..."
uv run backend/app/main.py

