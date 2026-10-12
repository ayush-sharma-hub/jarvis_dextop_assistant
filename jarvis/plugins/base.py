"""Base types for deterministic, side-effect-contained voice plugins."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

class RiskLevel(Enum):
    READ_ONLY = auto()
    REVERSIBLE = auto()
    DESTRUCTIVE = auto()

@dataclass(frozen=True)
class PluginResult:
    speech: str
    ok: bool = True
    data: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ParsedOperation:
    valid: bool
    kind: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    rejection: str = ""

class Plugin(ABC):
    name: str
    description: str
    phrases: tuple[str, ...]
    @abstractmethod
    def match(self, command: str) -> bool: ...
    @abstractmethod
    def parse(self, command: str) -> ParsedOperation: ...
    @abstractmethod
    def risk_for(self, command: str) -> RiskLevel: ...
    @abstractmethod
    def describe(self, command: str) -> str: ...
    @abstractmethod
    def run(self, command: str) -> PluginResult: ...

@dataclass(frozen=True)
class RouteMatch:
    matched: bool
    plugin: Plugin | None = None
    def __post_init__(self) -> None:
        if self.matched != (self.plugin is not None):
            raise ValueError("A route match must contain exactly one plugin")
