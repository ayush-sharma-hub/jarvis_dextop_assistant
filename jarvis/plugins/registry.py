"""Plugin registration and risk-aware execution policy."""
from __future__ import annotations
import logging
from typing import Callable
from .base import Plugin, PluginResult, RiskLevel, RouteMatch

class PluginRegistry:
    def __init__(self, action_mode: str) -> None:
        self.action_mode = action_mode
        self._plugins: dict[str, Plugin] = {}
        self.log = logging.getLogger(self.__class__.__name__)
    def register(self, plugin: Plugin) -> None:
        if plugin.name in self._plugins: raise ValueError(f"Duplicate plugin: {plugin.name}")
        self._plugins[plugin.name] = plugin
    def route(self, command: str) -> RouteMatch:
        matches: list[Plugin] = []
        for plugin in self._plugins.values():
            try:
                if plugin.match(command): matches.append(plugin)
            except Exception:
                self.log.exception("Plugin match failed: %s", plugin.name)
        if len(matches) > 1: self.log.warning("Multiple plugins matched; using %s", matches[0].name)
        return RouteMatch(bool(matches), matches[0] if matches else None)
    def execute(self, plugin: Plugin, command: str, confirm: Callable[[str], bool]) -> PluginResult:
        if self._plugins.get(plugin.name) is not plugin:
            self.log.warning("Denied unregistered plugin %s", plugin.name); return PluginResult("Yeh plugin registered nahi hai bhai.", False)
        parsed = plugin.parse(command)
        if not parsed.valid:
            self.log.info("Plugin %s rejected invalid command", plugin.name); return PluginResult(parsed.rejection, False)
        try: risk = plugin.risk_for(command)
        except Exception:
            self.log.exception("Plugin risk calculation failed: %s", plugin.name); return PluginResult("Yeh kaam abhi nahi ho paya bhai.", False)
        allowed = self.action_mode != "disabled" and (self.action_mode == "auto" and risk != RiskLevel.DESTRUCTIVE or self.action_mode == "confirm" and risk == RiskLevel.READ_ONLY)
        if self.action_mode == "disabled":
            self.log.info("Plugin %s %s denied: disabled", plugin.name, risk.name); return PluginResult("Plugin actions abhi disabled hain bhai.", False)
        if not allowed:
            description = plugin.describe(command)
            if not confirm(description):
                self.log.info("Plugin %s %s denied by confirmation", plugin.name, risk.name); return PluginResult("Theek hai bhai, maine kuch nahi kiya.", False)
        self.log.info("Plugin %s %s allowed", plugin.name, risk.name)
        try: return plugin.run(command)
        except Exception:
            self.log.exception("Plugin run failed: %s", plugin.name); return PluginResult("Yeh kaam abhi nahi ho paya bhai.", False)
