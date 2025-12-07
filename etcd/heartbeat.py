import time
import json
import etcd3 # version 0.12.0
import os
import socket
import threading

# Get etcd endpoint from environment or use default
ETCD_HOST = os.environ.get('ETCD_HOST', 'etcd-0.etcd-service.etcd.svc.cluster.local')
ETCD_PORT = int(os.environ.get('ETCD_PORT', 2379))

# Get node name from environment or hostname
NODE_NAME = os.environ.get('NODE_NAME', socket.gethostname())

etcd = etcd3.client(host=ETCD_HOST, port=ETCD_PORT)
HEARTBEAT_KEY = f"/monitor/heartbeat/{NODE_NAME}"
LEASE_TTL = 5 # seconds

def send_heartbeat():
    """Send heartbeat with lease (runs in separate thread)."""
    try:
        lease = etcd.lease(LEASE_TTL) # create a lease with TTL
        print(f"[Heartbeat] Lease created with TTL {LEASE_TTL} seconds, ID: {lease.id}")
        print(f"[Heartbeat] Node: {NODE_NAME}, Key: {HEARTBEAT_KEY}")
    except Exception as e:
        print(f"[Heartbeat] Failed to create lease: {e}")
        return
        
    try:
        while True:
            data = json.dumps({"status": "alive", "ts": time.time(), "hostname": NODE_NAME})
            etcd.put(HEARTBEAT_KEY, data, lease=lease) # put heartbeat key with lease attached
            print(f"[Heartbeat] Sent for {NODE_NAME}")
            lease.refresh() # refresh the lease before it expires to keep key alive
            time.sleep(LEASE_TTL / 2) # sleep less than TTL to ensure refresh before expiry
    except KeyboardInterrupt:
        print("[Heartbeat] Stopping heartbeat")
        try:
            lease.revoke() # optional: revoke lease and delete key immediately
        except:
            pass
    except Exception as e:
        print(f"[Heartbeat] Error: {e}")

if __name__ == "__main__":
    send_heartbeat()