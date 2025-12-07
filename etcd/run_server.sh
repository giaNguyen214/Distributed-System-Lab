#!/bin/bash
# Script to run monitoring server (central monitor)
# Usage: ETCD_HOST=<etcd-cluster-ip-or-dns> ./run_server.sh

# Set defaults if not provided
ETCD_HOST=${ETCD_HOST:-"127.0.0.1"}
ETCD_PORT=${ETCD_PORT:-2379}

echo "[Setup] Starting monitoring server"
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

# Run monitor
echo "[Setup] Starting heartbeat monitor..."
ETCD_HOST=$ETCD_HOST ETCD_PORT=$ETCD_PORT python3 monitor_heartbeat.py
