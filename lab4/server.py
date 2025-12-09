import grpc
import json
import threading
from datetime import datetime
from concurrent import futures

import etcd3
from fastapi import FastAPI
import uvicorn

import monitor_pb2
import monitor_pb2_grpc

# ================================
# Kafka (Confluent)
# ================================
from confluent_kafka import Producer, Consumer
import queue


# ===========================================================
# ETCD CLIENT (CONNECT FROM OUTSIDE K8S THROUGH NODEPORT)
# ===========================================================

etcd = etcd3.client(
    host="172.31.12.78",   # choose any node IP
    port=32379
)

node_state = {}
workers_status = {}
workers_last_seen = {}

# queue command gửi xuống từng agent
command_queues = {}

# ===========================================================
# KAFKA PRODUCER + CONSUMER
# ===========================================================

kafka_producer = Producer({
    "bootstrap.servers": "172.31.15.99:30092,172.31.8.184:30092"
})

kafka_consumer = Consumer({
    "bootstrap.servers": "172.31.15.99:30092,172.31.8.184:30092",
    "group.id": "monitor-server",
    "auto.offset.reset": "latest"
})

kafka_consumer.subscribe(["commands"])


# ===========================================================
# REST API
# ===========================================================

api = FastAPI()

@api.get("/nodes")
def list_nodes():
    return node_state


@api.post("/config/{node}")
def update_config(node: str, interval: int, metrics: str, plugins: str = ""):
    cfg = {
        "interval": interval,
        "metrics": [m.strip() for m in metrics.split(",")],
        "plugins": [p.strip() for p in plugins.split(",")] if plugins else []
    }

    etcd.put(f"/monitor/config/{node}", json.dumps(cfg))
    print(f"[CONFIG] updated for {node}: {cfg}")
    return cfg


def run_rest_api():
    print("REST API running at :8000")
    uvicorn.run(api, host="0.0.0.0", port=8000)


# ===========================================================
# WATCH HEARTBEAT
# ===========================================================

def watch_heartbeat():
    print("[ETCD] Watching /monitor/heartbeat/ ...")

    events_iterator, cancel = etcd.watch_prefix("/monitor/heartbeat/")

    for event in events_iterator:
        key = event.key.decode()
        host = key.split("/")[-1]

        if not event.value:
            node_state[host] = "dead"
            print(f"[Heartbeat] {host} DEAD")
        else:
            node_state[host] = "alive"
            print(f"[Heartbeat] {host} alive")


# ===========================================================
# THREAD: KAFKA COMMAND LISTENER
# ===========================================================

def kafka_command_loop():
    print("[KAFKA] Listening to 'commands' topic ...")

    while True:
        msg = kafka_consumer.poll(1.0)
        if msg is None:
            continue

        if msg.error():
            print("[KAFKA ERROR]", msg.error())
            continue

        data = json.loads(msg.value().decode())
        host = data.get("hostname")
        cmd = data.get("command")

        if not host or not cmd:
            continue

        command_queues.setdefault(host, queue.Queue()).put(cmd)
        print(f"[KAFKA] Command queued for {host}: {cmd}")


# ===========================================================
# gRPC SERVER
# ===========================================================

class MonitorServicer(monitor_pb2_grpc.MonitorServiceServicer):

    def CommandStream(self, request_iterator, context):

        # giữ nguyên handshake cũ
        yield monitor_pb2.CommandRequest(
            command="hostname",
            description="Handshake"
        )

        first_hostname = None

        for response in request_iterator:
            hostname = response.data.hostname
            metric = response.data.metric
            value = response.data.value

            if first_hostname is None:
                first_hostname = hostname
                command_queues.setdefault(hostname, queue.Queue())

            workers_last_seen[hostname] = datetime.now().isoformat()
            workers_status.setdefault(hostname, {})
            workers_status[hostname][metric] = value

            # highlight special metrics so they're easy to spot in logs
            try:
                if metric == "config_update":
                    parsed = json.loads(value) if value else None
                    print(f"[CONFIG_UPDATE] [{hostname}] {json.dumps(parsed)}")
                elif metric == "debug_marker":
                    print(f"[DEBUG_MARKER] [{hostname}] {value}")
                else:
                    print(f"   [{hostname}] {metric} = {value}")
            except Exception:
                print(f"   [{hostname}] {metric} = {value}")

            # ================================
            # PUSH metrics vào Kafka
            # ================================
            kafka_producer.produce(
                "metrics",
                json.dumps({
                    "time": response.data.time,
                    "hostname": hostname,
                    "metric": metric,
                    "value": value
                }).encode("utf-8")
            )

            # ================================
            # GỬI command từ Kafka → worker
            # ================================
            q = command_queues[hostname]
            while not q.empty():
                cmd = q.get()
                yield monitor_pb2.CommandRequest(
                    command=cmd,
                    description="From Kafka"
                )


def run_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=50))
    monitor_pb2_grpc.add_MonitorServiceServicer_to_server(MonitorServicer(), server)

    server.add_insecure_port("[::]:50051")
    print("gRPC server running on :50051")

    server.start()
    server.wait_for_termination()


# ===========================================================
# MAIN
# ===========================================================

if __name__ == "__main__":

    threading.Thread(target=run_rest_api, daemon=True).start()
    threading.Thread(target=watch_heartbeat, daemon=True).start()
    threading.Thread(target=kafka_command_loop, daemon=True).start()

    run_grpc()