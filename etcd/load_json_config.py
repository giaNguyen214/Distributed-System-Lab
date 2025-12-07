import time
import json
import etcd3 
import threading
import os
import socket

# Get etcd endpoint from environment or use default
ETCD_HOST = os.environ.get('ETCD_HOST', 'etcd-0.etcd-service.etcd.svc.cluster.local')
ETCD_PORT = int(os.environ.get('ETCD_PORT', 2379))
NODE_NAME = os.environ.get('NODE_NAME', socket.gethostname())

etcd = etcd3.client(host=ETCD_HOST, port=ETCD_PORT)
CONFIG_KEY = f"/monitor/config/{NODE_NAME}"

# Use threading.RLock for config access (Reader-Writer Lock equivalent in Python)
config_lock = threading.RLock()
config_value = {}

def watch_config_key(watch_response):
    global config_value
    for event in watch_response.events:
        if isinstance(event, etcd3.events.PutEvent):
            new_config = json.loads(event.value.decode('utf-8'))
            with config_lock:
                config_value = new_config
            print(f"[Config] UPDATED config from etcd: {config_value}")

def load_initial_config():
    """Load initial config from etcd."""
    global config_value
    try:
        value, _ = etcd.get(CONFIG_KEY)
        if value:
            with config_lock:
                config_value = json.loads(value.decode('utf-8'))
            print(f"[Config] Loaded initial config: {config_value}")
        else:
            # Set default config if not found
            default_config = {"interval": 10, "metrics": ["cpu", "memory", "disk"]}
            with config_lock:
                config_value = default_config.copy()
            print(f"[Config] No config found at {CONFIG_KEY}, using default: {config_value}")
    except Exception as e:
        print(f"[Config] Failed to load initial config: {e}")

def main():
    print(f"[Agent] Starting config watcher for node: {NODE_NAME}")
    print(f"[Agent] Config key: {CONFIG_KEY}")
    print(f"[Agent] etcd endpoint: {ETCD_HOST}:{ETCD_PORT}")
    load_initial_config()
    
    watch_id = etcd.add_watch_callback(CONFIG_KEY, watch_config_key)
    try:
        iteration = 0
        while True:
            # Simulate agent work with current config
            with config_lock:
                current_config = config_value.copy()
            
            interval = current_config.get('interval', 10)
            metrics = current_config.get('metrics', [])
            iteration += 1
            print(f"[Agent] Iteration {iteration}: interval={interval}s, metrics={metrics}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[Agent] Stopping config watcher...")
        etcd.cancel_watch(watch_id)
    except Exception as e:
        print(f"[Agent] Error: {e}")

if __name__ == "__main__":
    main()