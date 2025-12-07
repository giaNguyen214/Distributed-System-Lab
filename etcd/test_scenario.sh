#!/bin/bash
# Script to run full test scenario
# This script demonstrates heartbeat monitoring and dynamic config update

set -e

ETCD_HOST=${ETCD_HOST:-"127.0.0.1"}
ETCD_PORT=${ETCD_PORT:-2379}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "Distributed System Monitoring Lab - Test"
echo "=========================================="
echo ""

# Check prerequisites
check_prerequisites() {
    echo "[Step 1] Checking prerequisites..."
    
    if ! command -v python3 &> /dev/null; then
        echo "[Error] python3 not found"
        exit 1
    fi
    
    python3 -c "import etcd3" > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "[Setup] Installing etcd3 package..."
        # Try pip3, then apt-get, then python3 -m pip
        if command -v pip3 &> /dev/null; then
            pip3 install etcd3==0.12.0 2>&1 | tail -n 1
        elif command -v apt-get &> /dev/null; then
            echo "[Setup] Using apt-get to install python3-pip..."
            apt-get update && apt-get install -y python3-pip > /dev/null 2>&1
            pip3 install etcd3==0.12.0 2>&1 | tail -n 1
        else
            echo "[Error] Cannot install etcd3. Please install manually: pip3 install etcd3==0.12.0"
            exit 1
        fi
    fi
    
    echo "[OK] Prerequisites satisfied"
    echo ""
}

# Initialize etcd config
init_etcd_config() {
    echo "[Step 2] Initializing etcd configuration..."
    
    # Check if we can access etcd
    if command -v etcdctl &> /dev/null; then
        ETCDCTL_CMD="etcdctl --endpoints=http://$ETCD_HOST:$ETCD_PORT"
    else
        ETCDCTL_CMD="kubectl -n etcd exec etcd-0 -- etcdctl --endpoints=http://127.0.0.1:2379"
    fi
    
    # Set initial config
    CONFIG='{"interval": 10, "metrics": ["cpu", "memory", "disk"]}'
    $ETCDCTL_CMD put /monitor/config/worker1 "$CONFIG" 2>/dev/null || true
    $ETCDCTL_CMD put /monitor/config/worker2 "$CONFIG" 2>/dev/null || true
    $ETCDCTL_CMD put /monitor/config/master "$CONFIG" 2>/dev/null || true
    
    echo "[OK] Config initialized"
    echo ""
}

# Start monitoring server
start_server() {
    echo "[Step 3] Starting monitoring server on master..."
    echo "  Command: ETCD_HOST=$ETCD_HOST ETCD_PORT=$ETCD_PORT python3 monitor_heartbeat.py"
    echo ""
    
    cd "$SCRIPT_DIR"
    ETCD_HOST=$ETCD_HOST ETCD_PORT=$ETCD_PORT python3 monitor_heartbeat.py &
    PID_SERVER=$!
    echo "[OK] Server started (PID: $PID_SERVER)"
    sleep 2
}

# Start agent on worker1
start_agent1() {
    echo "[Step 4] Starting agent on worker1..."
    echo "  Command: NODE_NAME=worker1 ETCD_HOST=$ETCD_HOST ETCD_PORT=$ETCD_PORT python3 heartbeat.py & python3 load_json_config.py"
    echo ""
    
    cd "$SCRIPT_DIR"
    NODE_NAME=worker1 ETCD_HOST=$ETCD_HOST ETCD_PORT=$ETCD_PORT python3 heartbeat.py &
    PID_HB1=$!
    NODE_NAME=worker1 ETCD_HOST=$ETCD_HOST ETCD_PORT=$ETCD_PORT python3 load_json_config.py &
    PID_CFG1=$!
    echo "[OK] Worker1 agent started (Heartbeat PID: $PID_HB1, Config PID: $PID_CFG1)"
    sleep 2
}

# Start agent on worker2
start_agent2() {
    echo "[Step 5] Starting agent on worker2..."
    echo "  Command: NODE_NAME=worker2 ETCD_HOST=$ETCD_HOST ETCD_PORT=$ETCD_PORT python3 heartbeat.py & python3 load_json_config.py"
    echo ""
    
    cd "$SCRIPT_DIR"
    NODE_NAME=worker2 ETCD_HOST=$ETCD_HOST ETCD_PORT=$ETCD_PORT python3 heartbeat.py &
    PID_HB2=$!
    NODE_NAME=worker2 ETCD_HOST=$ETCD_HOST ETCD_PORT=$ETCD_PORT python3 load_json_config.py &
    PID_CFG2=$!
    echo "[OK] Worker2 agent started (Heartbeat PID: $PID_HB2, Config PID: $PID_CFG2)"
    sleep 2
}

# Test dynamic config update
test_dynamic_config() {
    echo "[Step 6] Testing dynamic config update..."
    echo "  Waiting 5 seconds before updating config..."
    sleep 5
    
    if command -v etcdctl &> /dev/null; then
        ETCDCTL_CMD="etcdctl --endpoints=http://$ETCD_HOST:$ETCD_PORT"
    else
        ETCDCTL_CMD="kubectl -n etcd exec etcd-0 -- etcdctl --endpoints=http://127.0.0.1:2379"
    fi
    
    FAST_CONFIG='{"interval": 2, "metrics": ["cpu", "memory"]}'
    echo "  Updating worker1 config: interval=10s -> 2s"
    $ETCDCTL_CMD put /monitor/config/worker1 "$FAST_CONFIG"
    
    echo "[OK] Config updated! Watch for log message in worker1 showing config change"
    echo ""
    echo "Expected behavior:"
    echo "  - Worker1 should log 'UPDATED config from etcd' with new interval"
    echo "  - Worker1 iterations should now happen every 2s instead of 10s"
    echo ""
}

# Test heartbeat detection
test_heartbeat() {
    echo "[Step 7] Testing heartbeat detection..."
    echo "  Waiting 20 seconds to observe heartbeats and status..."
    sleep 20
    
    echo ""
    echo "[OK] Observation period complete"
    echo ""
    echo "Expected behavior:"
    echo "  - Monitor shows 'worker1 ALIVE' and 'worker2 ALIVE' messages"
    echo "  - Status prints every 10 seconds showing alive node count"
    echo ""
}

# Kill test
kill_agent_test() {
    echo "[Step 8] Testing node failure detection..."
    echo "  Waiting 5 seconds, then killing worker1 heartbeat..."
    sleep 5
    
    kill $PID_HB1 2>/dev/null || true
    echo "  [Killed] Worker1 heartbeat sender (PID: $PID_HB1)"
    
    echo "  Waiting 15 seconds for lease to expire..."
    sleep 15
    
    echo "[OK] Lease expiration test complete"
    echo ""
    echo "Expected behavior:"
    echo "  - After ~5 seconds (LEASE_TTL), monitor shows 'worker1 DEAD' message"
    echo "  - Status count changes from 2 to 1 alive nodes"
    echo ""
}

# Cleanup
cleanup() {
    echo "[Cleanup] Stopping all processes..."
    kill $PID_SERVER 2>/dev/null || true
    kill $PID_HB1 2>/dev/null || true
    kill $PID_CFG1 2>/dev/null || true
    kill $PID_HB2 2>/dev/null || true
    kill $PID_CFG2 2>/dev/null || true
    echo "[OK] All processes stopped"
}

# Main flow
main() {
    trap cleanup EXIT
    
    check_prerequisites
    init_etcd_config
    start_server
    start_agent1
    start_agent2
    test_dynamic_config
    test_heartbeat
    kill_agent_test
    
    echo ""
    echo "=========================================="
    echo "Test complete! Check logs above for results"
    echo "=========================================="
}

main "$@"
