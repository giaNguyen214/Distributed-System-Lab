import etcd3 # version 0.12.0
import os
import threading
import time

# Get etcd endpoint from environment or use default
ETCD_HOST = os.environ.get('ETCD_HOST', 'etcd-0.etcd-service.etcd.svc.cluster.local')
ETCD_PORT = int(os.environ.get('ETCD_PORT', 2379))

etcd = etcd3.client(host=ETCD_HOST, port=ETCD_PORT)
KEY_PREFIX = "/monitor/heartbeat/"
alive_nodes = {}
alive_nodes_lock = threading.Lock()

def on_heartbeat_event(watch_response):
    for event in watch_response.events:
        node_id = event.key.decode('utf-8').split('/')[-1]
        if isinstance(event, etcd3.events.PutEvent):
            value = event.value.decode('utf-8')
            with alive_nodes_lock:
                alive_nodes[node_id] = value
            print(f"[+] Node {node_id} ALIVE -> {value}")
        elif isinstance(event, etcd3.events.DeleteEvent):
            with alive_nodes_lock:
                if node_id in alive_nodes:
                    del alive_nodes[node_id]
            print(f"[-] Node {node_id} DEAD (lease expired)")

def print_status():
    """Periodically print current alive nodes."""
    while True:
        time.sleep(10)
        with alive_nodes_lock:
            alive_list = list(alive_nodes.keys())
        print(f"\n[Status] Currently ALIVE nodes: {alive_list}")
        print(f"[Status] Total alive: {len(alive_list)}\n")

def monitor_heartbeats():
    print("[Monitor] Starting heartbeat monitor...")
    print(f"[Monitor] Watching prefix: {KEY_PREFIX}")
    print(f"[Monitor] etcd endpoint: {ETCD_HOST}:{ETCD_PORT}")
    
    # Start status printer thread
    status_thread = threading.Thread(target=print_status, daemon=True)
    status_thread.start()
    
    watch_id = etcd.add_watch_prefix_callback(KEY_PREFIX, on_heartbeat_event)
    try:
        while True:
            pass # doing main function
    except KeyboardInterrupt:
        print("\n[Monitor] Stopping watcher...")
        etcd.cancel_watch(watch_id)
    except Exception as e:
        print(f"[Monitor] Error: {e}")

        
if __name__ == "__main__":
    monitor_heartbeats()