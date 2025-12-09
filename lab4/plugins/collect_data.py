"""Helpers to collect metric data used by the monitor client."""

import re
import socket
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import monitor_pb2
from base_plugin import BasePlugin


def run(cmd):
	return subprocess.getoutput(cmd)


def format_percent(val):
	try:
		val = float(val)
		return f"{val:.2f}%"
	except Exception:
		return val


def get_iface():
	out = run("ip route get 8.8.8.8")
	m = re.search(r"dev (\S+)", out)
	return m.group(1) if m else "eth0"


iface = get_iface()


metrics_map = {
	"cpu": lambda: format_percent(
		run("top -bn1 | grep 'Cpu(s)' | awk '{print 100 - $8}'")
	),

	"mem": lambda: format_percent(
		run("free | awk '/^Mem:/ {printf(\"%.2f\", $3/$2 * 100)}'")
	),

	"disk": lambda: format_percent(
		run("df / | awk 'NR==2 {print $5}' | sed 's/%//'")
	),

	"disk_read": lambda: run(
		"iostat -d -k 1 2 | awk 'NR>7 {read+=$3} END {print read}'"
	),

	"disk_write": lambda: run(
		"iostat -d -k 1 2 | awk 'NR>7 {write+=$4} END {print write}'"
	),

	"net_in": lambda: run(
		f"ifstat -i {iface} 1 1 | awk 'NR>2 {{print $1}}'"
	),

	"net_out": lambda: run(
		f"ifstat -i {iface} 1 1 | awk 'NR>2 {{print $2}}'"
	),
}


hostname = socket.gethostname()


def collect_all_metrics(host, metrics):
	ts = datetime.now().isoformat()
	results = []

	with ThreadPoolExecutor(max_workers=len(metrics)) as executor:
		future_map = {
			executor.submit(metrics_map[m]): m
			for m in metrics
		}

		for future in as_completed(future_map):
			metric_name = future_map[future]
			try:
				value = str(future.result())
			except Exception as e:
				value = f"ERR: {e}"

			results.append(monitor_pb2.CommandResponse(
				data=monitor_pb2.MonitorData(
					time=ts,
					hostname=host,
					metric=metric_name,
					value=value
				)
			))

	return results


class CollectDataPlugin(BasePlugin):
	"""Plugin wrapper so metric collection can join the pipeline."""

	def __init__(self):
		self.default_metrics = ["cpu", "mem", "disk"]
		self.hostname = hostname

	def initialize(self, metrics=None, hostname_override=None):
		if metrics:
			self.default_metrics = metrics
		if hostname_override:
			self.hostname = hostname_override

	def run(self, batch):
		# If batch already contains CommandResponse items, leave them untouched.
		if batch and hasattr(batch[0], "data"):
			return batch

		metrics = batch if batch else self.default_metrics
		return collect_all_metrics(self.hostname, metrics)

	def finalize(self):
		pass
