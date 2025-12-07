# Distributed System Monitoring Lab - Implementation Guide

## Overview

This monitoring system consists of:
- **etcd Cluster**: A 3-node etcd cluster for storing configuration and heartbeat data
- **Server (Master)**: Central monitoring node that watches heartbeats and node status
- **Agents (Workers)**: Monitoring agents running on each worker node

## Architecture

```
Master:
  - monitor_heartbeat.py (watches /monitor/heartbeat/* for alive nodes)

Worker1/Worker2:
  - heartbeat.py (sends periodic heartbeat with TTL lease)
  - load_json_config.py (watches /monitor/config/<nodename> for config changes)
```

## Prerequisites

- Python 3.6+
- etcd3 package: `pip install etcd3==0.12.0`
- Access to etcd cluster (already deployed in Kubernetes)

## Deployment Steps

### Step 1: etcd Cluster Setup (Already Done)

Verify etcd cluster is running:

```bash
kubectl -n etcd get pods -o wide
kubectl -n etcd exec etcd-0 -- etcdctl --endpoints=http://127.0.0.1:2379 member list -w table
```

Expected output: 3 members with "started" status

### Step 2: Get etcd Endpoint

For Kubernetes deployments, the endpoint is:
```
etcd-0.etcd-service.etcd.svc.cluster.local:2379
```

For local testing outside Kubernetes, get the IP address:
```bash
kubectl -n etcd get svc etcd-service
kubectl -n etcd get endpoints etcd-service
```

### Step 3: Initialize Configuration

Run setup script to create initial config in etcd:

```bash
# Option A: Using local etcdctl (if installed)
ETCD_HOST=<etcd-ip-or-dns> ETCD_PORT=2379 ./setup_config.sh

# Option B: Using kubectl
./setup_config.sh
```

This creates config keys:
- `/monitor/config/worker1` - config for worker1
- `/monitor/config/worker2` - config for worker2
- `/monitor/config/master` - config for master

### Step 4: Start Monitoring Server (on Master)

On the master node:

```bash
# Set etcd endpoint
export ETCD_HOST="etcd-0.etcd-service.etcd.svc.cluster.local"
export ETCD_PORT=2379

# Run monitoring server
python3 monitor_heartbeat.py
```

Expected output:
```
[Monitor] Starting heartbeat monitor...
[Monitor] Watching prefix: /monitor/heartbeat/
[Monitor] etcd endpoint: etcd-0.etcd-service.etcd.svc.cluster.local:2379
[Status] Currently ALIVE nodes: []
[Status] Total alive: 0
```

### Step 5: Start Agents (on Each Worker)

On each worker node:

```bash
# Set environment variables
export NODE_NAME="worker1"  # Change to worker2 on second worker
export ETCD_HOST="etcd-0.etcd-service.etcd.svc.cluster.local"
export ETCD_PORT=2379

# Run agent script (runs both heartbeat and config watcher)
./run_agent.sh

# Or run them individually in separate terminals:
# Terminal 1: Heartbeat sender
python3 heartbeat.py

# Terminal 2: Config watcher
python3 load_json_config.py
```

Expected output from heartbeat.py:
```
[Heartbeat] Lease created with TTL 5 seconds, ID: 123456789
[Heartbeat] Node: worker1, Key: /monitor/heartbeat/worker1
[Heartbeat] Sent for worker1
[Heartbeat] Sent for worker1
...
```

Expected output from load_json_config.py:
```
[Agent] Starting config watcher for node: worker1
[Agent] Config key: /monitor/config/worker1
[Agent] Loaded initial config: {'interval': 10, 'metrics': ['cpu', 'memory', 'disk']}
[Agent] Iteration 1: interval=10s, metrics=['cpu', 'memory', 'disk']
...
```

### Step 6: Verify System is Running

On master, you should see:
```
[+] Node worker1 ALIVE -> {"status": "alive", ...}
[+] Node worker2 ALIVE -> {"status": "alive", ...}
[Status] Currently ALIVE nodes: ['worker1', 'worker2']
```

## Test Scenarios

### Test 1: Dynamic Configuration Update

Update worker1 config to run faster:

```bash
# Using kubectl
kubectl -n etcd exec etcd-0 -- etcdctl --endpoints=http://127.0.0.1:2379 \
  put /monitor/config/worker1 '{"interval": 2, "metrics": ["cpu", "memory"]}'

# Or using etcdctl
etcdctl --endpoints=http://$ETCD_HOST:$ETCD_PORT \
  put /monitor/config/worker1 '{"interval": 2, "metrics": ["cpu", "memory"]}'
```

**Expected result:**
- Worker1 logs: `[Config] UPDATED config from etcd: {'interval': 2, 'metrics': ['cpu', 'memory']}`
- Worker1 iteration time changes from 10s to 2s

### Test 2: Node Failure Detection

Kill the heartbeat process on worker1:

```bash
# Find and kill the heartbeat process
ps aux | grep heartbeat
kill <PID>
```

**Expected result:**
- After ~5 seconds (TTL expires), master logs: `[-] Node worker1 DEAD (lease expired)`
- Status updates: `[Status] Currently ALIVE nodes: ['worker2']`

### Test 3: Full Automated Test

Run the complete test scenario:

```bash
ETCD_HOST="etcd-0.etcd-service.etcd.svc.cluster.local" \
ETCD_PORT=2379 \
./test_scenario.sh
```

This script will:
1. Check prerequisites and install etcd3
2. Initialize configuration in etcd
3. Start monitoring server
4. Start 2 worker agents
5. Test dynamic config update
6. Monitor for 20 seconds
7. Kill worker1 to test failure detection
8. Display results

## Troubleshooting

### Issue: Connection refused to etcd

**Solution:**
- Verify etcd pods are running: `kubectl -n etcd get pods`
- Check if using correct endpoint (inside Kubernetes: `etcd-0.etcd-service.etcd.svc.cluster.local`)
- If running outside Kubernetes, use external endpoint: `kubectl -n etcd get endpoints etcd-service`

### Issue: etcd3 module not found

**Solution:**
```bash
pip install etcd3==0.12.0
```

### Issue: Config not updating

**Solution:**
- Check etcd contains the key: `etcdctl get /monitor/config/worker1`
- Verify agent is watching correct key (check NODE_NAME env variable matches)
- Check agent logs for watch errors

### Issue: Node not showing as ALIVE

**Solution:**
- Verify heartbeat.py is running on worker
- Check logs for errors in heartbeat sender
- Verify etcd can be reached from worker
- Check firewall if running across different machines

## File Descriptions

- `heartbeat.py` - Sends periodic heartbeat with TTL lease to etcd
- `monitor_heartbeat.py` - Central server watching all heartbeats
- `load_json_config.py` - Agent-side config watcher with threading
- `run_agent.sh` - Convenience script to start both heartbeat and config watcher
- `run_server.sh` - Convenience script to start monitoring server
- `setup_config.sh` - Initialize configuration in etcd
- `test_scenario.sh` - Automated test of all features

## Configuration Schema

Config stored in etcd has the following format:

```json
{
  "interval": 10,
  "metrics": ["cpu", "memory", "disk"]
}
```

- `interval`: Time in seconds between agent iterations
- `metrics`: List of metrics to monitor (extensible)

## Key Paths in etcd

- `/monitor/heartbeat/<node-name>` - Heartbeat data with TTL (5 second lease)
- `/monitor/config/<node-name>` - Configuration for specific node
- Format of heartbeat: `{"status": "alive", "ts": <timestamp>, "hostname": "<node-name>"}`

## References

- etcd3 Python client: https://github.com/xhochy/etcd3-py
- etcd Leases: https://etcd.io/docs/v3.4/learning/api/#lease
- Watch API: https://etcd.io/docs/v3.4/learning/api/#watch
