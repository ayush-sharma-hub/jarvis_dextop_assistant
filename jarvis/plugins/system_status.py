"""Read-only local system metrics."""
from __future__ import annotations
import re
from .base import ParsedOperation, Plugin, PluginResult, RiskLevel
class SystemStatusPlugin(Plugin):
    name="system_status"; description="Read system status"; phrases=("system status", "battery", "ram", "cpu")
    def match(self,c: str)->bool: return bool(re.match(r"^(?:battery(?:\s+status)?|ram(?:\s+status)?|cpu(?:\s+status)?|system\s+status)\b",c.strip().casefold()))
    def parse(self,c: str)->ParsedOperation: return ParsedOperation(True,"status") if self.match(c) else ParsedOperation(False,rejection="System status command samajh nahi aaya bhai.")
    def risk_for(self,c: str)->RiskLevel: return RiskLevel.READ_ONLY
    def describe(self,c: str)->str: return "Read system status"
    def run(self,c: str)->PluginResult:
        try: import psutil
        except ImportError: return PluginResult("System status ke liye psutil install nahi hai bhai.",False)
        bat=psutil.sensors_battery(); battery="battery unavailable" if bat is None else f"battery {bat.percent:.0f}% ({'charging' if bat.power_plugged else 'not charging'})"
        mem=psutil.virtual_memory().percent; cpu=psutil.cpu_percent(interval=.5); disk=psutil.disk_usage(__import__('os').path.abspath(__import__('os').sep)).percent
        return PluginResult(f"{battery}, RAM {mem:.0f}%, CPU {cpu:.0f}%, disk {disk:.0f}% used bhai.")
