#!/bin/bash
# Script to set up etcd config for dynamic configuration testing
# Usage: ./setup_config.sh <etcd-host> <etcd-port>

ETCD_HOST=${1:-"127.0.0.1"}
ETCD_PORT=${2:-2379}

echo "[Setup] Configuring etcd for monitoring system..."
echo "[Setup] etcd endpoint: $ETCD_HOST:$ETCD_PORT"

# Check if etcdctl is available
if ! command -v etcdctl &> /dev/null; then
    echo "[Warning] etcdctl not found. Will try to use kubectl exec if in Kubernetes cluster"
    # Try to use kubectl exec instead
    ETCDCTL_CMD="kubectl -n etcd exec etcd-0 -- etcdctl --endpoints=http://127.0.0.1:2379"
else
    ETCDCTL_CMD="etcdctl --endpoints=http://$ETCD_HOST:$ETCD_PORT"
fi

# Helper function to set key
set_key() {
    local key=$1
    local value=$2
    echo "[Config] Setting $key = $value"
    $ETCDCTL_CMD put "$key" "$value"
}

# Default config for monitoring nodes
DEFAULT_CONFIG='{"interval": 10, "metrics": ["cpu", "memory", "disk"]}'
FAST_CONFIG='{"interval": 2, "metrics": ["cpu", "memory"]}'

# Set initial config for nodes (adjust worker1, worker2 as needed)
set_key "/monitor/config/worker1" "$DEFAULT_CONFIG"
set_key "/monitor/config/worker2" "$DEFAULT_CONFIG"
set_key "/monitor/config/master" "$DEFAULT_CONFIG"

echo "[Setup] Config setup complete!"
echo ""
echo "[Info] To test dynamic config update, run:"
echo "  $ETCDCTL_CMD put /monitor/config/worker1 '$FAST_CONFIG'"
echo ""
echo "[Info] To view all monitor config keys:"
echo "  $ETCDCTL_CMD get --prefix /monitor/config"
