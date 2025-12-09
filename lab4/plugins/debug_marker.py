import socket
from datetime import datetime
from base_plugin import BasePlugin


class DebugMarkerPlugin(BasePlugin):
    """Injects a debug metric so you can verify plugin changes are live."""

    def initialize(self, tag="plugin-debug"):
        self.tag = tag
        self.hostname = socket.gethostname()

    def run(self, batch):
        # Append a synthetic metric with a unique tag and timestamp.
        marker_value = f"{self.tag}-{datetime.now().isoformat()}"
        batch = list(batch) if batch else []
        from monitor_pb2 import CommandResponse, MonitorData  # local import to avoid circulars on server startup
        batch.append(
            CommandResponse(
                data=MonitorData(
                    time=datetime.now().isoformat(),
                    hostname=self.hostname,
                    metric="debug_marker",
                    value=marker_value,
                )
            )
        )
        return batch

    def finalize(self):
        pass
