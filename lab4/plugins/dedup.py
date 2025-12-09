import json
from base_plugin import BasePlugin

class DedupPlugin(BasePlugin):
    def __init__(self):
        self.last_payload = None

    def initialize(self):
        pass

    def run(self, batch):
        simple = [
            {"metric": b.data.metric, "value": b.data.value}
            for b in batch
        ]

        cur = json.dumps(simple, sort_keys=True)
        if cur == self.last_payload:
            print("[DedupPlugin] Duplicate metrics → skip sending")
            return []

        self.last_payload = cur
        return batch

    def finalize(self):
        pass