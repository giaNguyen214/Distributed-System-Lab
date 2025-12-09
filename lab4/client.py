import grpc
import socket
import time
import json
import threading
from datetime import datetime
from queue import Queue

import etcd3
from readerwriterlock import rwlock

import monitor_pb2
import monitor_pb2_grpc


# =============================
# Plugins
# =============================
import importlib
from base_plugin import BasePlugin
from plugins.collect_data import collect_all_metrics, run


hostname = socket.gethostname()


# ==========================================================
# ETCD + MASTER CONFIG
# ==========================================================
ETCD_HOST = "172.31.12.78"
ETCD_PORT = 32379
MASTER_ADDR = "172.31.12.78:50051"

etcd = etcd3.client(host=ETCD_HOST, port=ETCD_PORT)

config_lock = rwlock.RWLockWrite()

current_cfg = {
    "interval": 2,
    "metrics": ["cpu", "mem", "disk"],
    "plugins": [
        "plugins.console_log.ConsoleLogPlugin",
        "plugins.error_filter.ErrorFilterPlugin"
    ]
}


# ==========================================================
# Plugin Manager
# ==========================================================

class PluginManager:
    def __init__(self):
        self.plugins = []

    def load_from_config(self, plugin_list):
        self.plugins = []
        for p in plugin_list:
            try:
                module, cls = p.rsplit(".", 1)
                mod = importlib.import_module(module)
                obj = getattr(mod, cls)()
                obj.initialize()
                self.plugins.append(obj)
                print("[PLUGIN LOADED]", p)
            except Exception as e:
                print("[PLUGIN ERROR]", p, e)

    def apply(self, batch):
        result = batch
        for p in self.plugins:
            result = p.run(result)
        return result

plugin_manager = PluginManager()

# queue to push config change events so they can be sent to server
config_events = Queue()


# ==========================================================
# LOAD CONFIG AT STARTUP
# ==========================================================

def load_initial_config():
    key = f"/monitor/config/{hostname}"
    val, _ = etcd.get(key)
    if val:
        cfg = json.loads(val.decode())
        with config_lock.gen_wlock():
            current_cfg["interval"] = cfg.get("interval", current_cfg["interval"])
            current_cfg["metrics"]  = cfg.get("metrics", current_cfg["metrics"])
            current_cfg["plugins"]  = cfg.get("plugins", current_cfg["plugins"])
        plugin_manager.load_from_config(current_cfg["plugins"])
        config_events.put({
            "type": "config_init",
            "interval": current_cfg["interval"],
            "metrics": list(current_cfg["metrics"]),
            "plugins": list(current_cfg["plugins"])
        })
        print("[INITIAL CONFIG LOADED]", current_cfg)
    else:
        print(f"[NO CONFIG FOUND IN ETCD] Using default: {current_cfg}")


# ==========================================================
# HEARTBEAT
# ==========================================================

def heartbeat():
    key = f"/monitor/heartbeat/{hostname}"
    lease = etcd.lease(5)

    while True:
        etcd.put(key, json.dumps({"ts": time.time()}), lease=lease)
        lease.refresh()
        time.sleep(1)


# ==========================================================
# WATCH CONFIG
# ==========================================================

def watch_config():
    key = f"/monitor/config/{hostname}"
    events, cancel = etcd.watch(key)

    for event in events:
        if event.value:
            cfg = json.loads(event.value.decode())
            with config_lock.gen_wlock():
                current_cfg["interval"] = cfg.get("interval", current_cfg["interval"])
                current_cfg["metrics"]  = cfg.get("metrics", current_cfg["metrics"])
                current_cfg["plugins"]  = cfg.get("plugins", current_cfg["plugins"])
            plugin_manager.load_from_config(current_cfg["plugins"])
            config_events.put({
                "type": "config_update",
                "interval": current_cfg["interval"],
                "metrics": list(current_cfg["metrics"]),
                "plugins": list(current_cfg["plugins"])
            })
            print("[CONFIG UPDATED]", current_cfg)


# ==========================================================
# MAIN
# ==========================================================

def main(local=False):
    load_initial_config()
    threading.Thread(target=heartbeat, daemon=True).start()
    threading.Thread(target=watch_config, daemon=True).start()

    stub = monitor_pb2_grpc.MonitorServiceStub(
        grpc.insecure_channel(MASTER_ADDR)
    )

    def stream():
        while True:
            # flush any config updates to the server immediately
            while not config_events.empty():
                cfg_snapshot = config_events.get()
                yield monitor_pb2.CommandResponse(
                    data=monitor_pb2.MonitorData(
                        time=datetime.now().isoformat(),
                        hostname=hostname,
                        metric="config_update",
                        value=json.dumps(cfg_snapshot)
                    )
                )

            with config_lock.gen_rlock():
                interval = current_cfg["interval"]
                metrics = current_cfg["metrics"]

            batch = collect_all_metrics(hostname, metrics)

            # APPLY PLUGIN
            batch = plugin_manager.apply(batch)

            for item in batch:
                yield item

            time.sleep(interval)

    for resp in stub.CommandStream(stream()):
        print("[CMD]", resp.command)
        print(run(resp.command))


if __name__ == "__main__":
    main()