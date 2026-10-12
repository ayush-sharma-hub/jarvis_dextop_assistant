"""Default registry construction; importing this module has no side effects."""
from __future__ import annotations
from typing import Callable
from .notes import NotesPlugin
from .registry import PluginRegistry
from .system_status import SystemStatusPlugin
from .timer import TimerPlugin
def build_default_registry(action_mode: str, speak: Callable[[str],None]) -> PluginRegistry:
    registry=PluginRegistry(action_mode)
    registry.register(NotesPlugin()); registry.register(TimerPlugin(speak)); registry.register(SystemStatusPlugin())
    return registry
