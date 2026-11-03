"""Adapter 协议与能力矩阵。

Adapter 只做两件事：**读**——把目标 Agent 的现状解析成内部结构；
**写**——把内部结构变成目标格式并落盘。diff、归属、原子写、备份都在
`deployment/`（与 Agent 无关的核心）里。

第一刀每个 Adapter 只负责 `skills` 目录——MCP 段在第二刀加入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from capnest.models import CapabilityType, DeploymentMode


@dataclass(frozen=True)
class TargetCapabilities:
    """一个目标 Agent 支持什么。"""

    target: str
    supports: frozenset[CapabilityType] = frozenset({CapabilityType.SKILL})
    deployment_modes: frozenset[DeploymentMode] = frozenset({DeploymentMode.COPY})
    skills_path: Path | None = None
    config_file: Path | None = None
    mcp_backend: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "supports": sorted(str(item) for item in self.supports),
            "deployment_modes": sorted(str(item) for item in self.deployment_modes),
            "skills_path": str(self.skills_path) if self.skills_path else None,
            "config_file": str(self.config_file) if self.config_file else None,
            "mcp_backend": self.mcp_backend,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class TargetState:
    """目标 Agent 的现状（第一刀只有 skills 一个字段）。"""

    skills: dict[str, str] = field(default_factory=dict)
    nested: tuple[str, ...] = ()
    config_fingerprint: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "skills": dict(self.skills),
            "nested": list(self.nested),
            "config_fingerprint": self.config_fingerprint,
        }


class Adapter(Protocol):
    """Adapter 协议。"""

    target: str

    def capabilities(self) -> TargetCapabilities: ...

    def read(self) -> TargetState: ...
