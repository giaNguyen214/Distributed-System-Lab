import grpc
import subprocess
import socket
import time
from datetime import datetime
import os  # thêm
import monitor_pb2
import monitor_pb2_grpc


def run(cmd):
    return subprocess.getoutput(cmd)


def metric_cpu():
    return run("top -bn1 | grep 'Cpu(s)' | awk '{print 100 - $8}'")


def metric_mem():
    return run("free | awk '/^Mem:/ {printf(\"%.2f\", $3/$2 * 100)}'")


def metric_load():
    return run("cat /proc/loadavg | awk '{print $1}'")


def metric_disk():
    return run("df / | awk 'NR==2 {print $5}' | sed 's/%//'")  # bỏ dấu %


def metric_net_in():
    return run("cat /sys/class/net/eth0/statistics/rx_bytes")


def metric_net_out():
    return run("cat /sys/class/net/eth0/statistics/tx_bytes")


def metric_io_read():
    return run("iostat -d -k 1 2 | awk 'NR>7 {read+=$3} END {print read}'")


def metric_io_write():
    return run("iostat -d -k 1 2 | awk 'NR>7 {read+=$4} END {print write}'")


def generate_metrics(hostname):
    now = datetime.now().isoformat()

    metrics = {
        "cpu": metric_cpu(),
        "mem": metric_mem(),
        "load": metric_load(),
        "disk": metric_disk(),
        "net_in": metric_net_in(),
        "net_out": metric_net_out(),
        "io_read": metric_io_read(),
        "io_write": metric_io_write(),
    }

    for key, val in metrics.items():
        yield monitor_pb2.CommandResponse(
            data=monitor_pb2.MonitorData(
                time=now,
                hostname=hostname,
                metric=key,
                value=str(val)
            )
        )


def main():
    hostname = socket.gethostname()

    # Dùng env MASTER_ADDR, mặc định dùng DNS service trong K8s
    server_addr = os.getenv("MASTER_ADDR", "monitor-server-service:50051")
    channel = grpc.insecure_channel(server_addr)
    stub = monitor_pb2_grpc.MonitorServiceStub(channel)

    def request_stream():
        while True:
            for item in generate_metrics(hostname):
                yield item
            time.sleep(2)   # gửi mỗi 2 giây

    # Nhận command, thực thi và in log (không gửi exec_output nữa cho đơn giản)
    for command in stub.CommandStream(request_stream()):
        print(f"Received command from server: {command.command}")
        output = run(command.command)
        print(f"Command output:\n{output}")


if __name__ == "__main__":
    main()
