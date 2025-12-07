#!/bin/bash
# Script to run monitoring agent on worker nodes
# Usage: NODE_NAME=worker1 ETCD_HOST=<etcd-cluster-ip-or-dns> ./run_agent.sh

# Set defaults if not provided
NODE_NAME=${NODE_NAME:-$(hostname)}
ETCD_HOST=${ETCD_HOST:-"127.0.0.1"}
ETCD_PORT=${ETCD_PORT:-2379}

echo "[Setup] Starting agent on node: $NODE_NAME"
echo "[Setup] etcd endpoint: $ETCD_HOST:$ETCD_PORT"

# Check if python3 and etcd3 are available
if ! command -v python3 &> /dev/null; then
    echo "[Error] python3 not found"
    exit 1
fi

# Install dependencies from requirements.txt if present
if [ -f "requirements.txt" ]; then
    python3 -c "import etcd3" > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "[Setup] Installing dependencies from requirements.txt..."
        
        if [[ -n "$VIRTUAL_ENV" ]]; then
            pip install -r requirements.txt > /dev/null 2>&1
        else
            python3 -m pip install --break-system-packages -r requirements.txt > /dev/null 2>&1
        fi
        
        if [ $? -eq 0 ]; then
            echo "[OK] Dependencies installed successfully"
        else
            echo "[Error] Failed to install dependencies"
            echo "[Help] Try manually:"
            echo "  pip install -r requirements.txt"
            exit 1
        fi
    fi
fi

# Run both heartbeat and config watcher in parallel
echo "[Setup] Starting heartbeat sender..."
ETCD_HOST=$ETCD_HOST ETCD_PORT=$ETCD_PORT NODE_NAME=$NODE_NAME python3 heartbeat.py &
PID_HEARTBEAT=$!

echo "[Setup] Starting config watcher..."
ETCD_HOST=$ETCD_HOST ETCD_PORT=$ETCD_PORT NODE_NAME=$NODE_NAME python3 load_json_config.py &
PID_CONFIG=$!

echo "[Setup] Agent started (PIDs: heartbeat=$PID_HEARTBEAT, config=$PID_CONFIG)"
echo "[Setup] Press Ctrl+C to stop"

# Wait for both processes
wait


