import json
from base_plugin import BasePlugin


class ErrorFilterPlugin(BasePlugin):
    """Drop metrics whose values indicate command errors."""

    def initialize(self):
        pass

    def run(self, batch):
        if not batch:
            return batch

        kept = []
        skipped = 0
        for item in batch:
            value = getattr(item.data, "value", "")
            if isinstance(value, str) and value.startswith("ERR"):
                skipped += 1
                continue
            kept.append(item)

        if skipped:
            print(f"[ErrorFilterPlugin] Dropped {skipped} error metrics")
        return kept

    def finalize(self):
        pass
