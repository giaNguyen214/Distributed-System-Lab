import grpc
import monitor_pb2
import monitor_pb2_grpc
from concurrent import futures
import time
from datetime import datetime

workers_last_seen = {}      # lưu lần cuối nhận metric
workers_status = {}         # lưu thông tin CPU/MEM/... hiện tại


class MonitorServicer(monitor_pb2_grpc.MonitorServiceServicer):
    def CommandStream(self, request_iterator, context):

        # Gửi lệnh đầu tiên khi client vừa kết nối
        yield monitor_pb2.CommandRequest(
            command="hostname",
            description="Lệnh test kết nối"
        )

        for response in request_iterator:
            hostname = response.data.hostname
            metric = response.data.metric
            value = response.data.value
            now = datetime.now().isoformat()

            # Lưu dấu vết worker
            workers_last_seen[hostname] = now

            # Lưu metrics hiện tại
            if hostname not in workers_status:
                workers_status[hostname] = {}
            workers_status[hostname][metric] = value

            print(f"[{hostname}] {metric} = {value}")

            # Server logic
            if metric == "cpu" and float(value) > 80:
                yield monitor_pb2.CommandRequest(
                    command="echo CPU TOO HIGH",
                    description="Phát hiện CPU cao"
                )

            if metric == "disk" and float(value) > 90:
                yield monitor_pb2.CommandRequest(
                    command="du -sh /",
                    description="Kiểm tra dung lượng"
                )

            if metric == "net_in" and float(value) > 5000:
                yield monitor_pb2.CommandRequest(
                    command="echo HIGH NETWORK TRAFFIC",
                    description="Tải mạng vào quá lớn"
                )

        # Nếu client đóng stream
        print("Client disconnected.")


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=50))
    monitor_pb2_grpc.add_MonitorServiceServicer_to_server(MonitorServicer(), server)
    server.add_insecure_port("[::]:50051")
    print("Master server running at port 50051")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
