from base_plugin import BasePlugin


class ConsoleLogPlugin(BasePlugin):
    """Print each metric to stdout for quick debugging."""

    def __init__(self):
        self.prefix = "[Metric]"

    def initialize(self, prefix=None):
        if prefix:
            self.prefix = prefix

    def run(self, batch):
        if not batch:
            return batch

        for item in batch:
            data = item.data
            print(f"{self.prefix} {data.time} {data.hostname} {data.metric}={data.value}")
        return batch

    def finalize(self):
        pass
