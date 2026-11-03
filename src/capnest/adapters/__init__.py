"""Adapter 注册表。

新增一个部署目标 = 在这里注册一个 Adapter 类。
"""

from __future__ import annotations

from pathlib import Path

from capnest.adapters.base import Adapter, TargetCapabilities, TargetState
from capnest.adapters.claude_code import ClaudeCodeAdapter
from capnest.adapters.mcode import McodeAdapter
from capnest.config import DEFAULT_TARGETS, default_target_paths
from capnest.errors import NotFound


def make_adapter(target: str, env: dict[str, str] | None = None) -> Adapter:
    """按目标名构造 Adapter。"""
    if target not in DEFAULT_TARGETS:
        raise NotFound(
            f"未知的目标：{target}",
            {"target": target, "supported": list(DEFAULT_TARGETS)},
        )
    paths = default_target_paths(target, env)
    if target == "mcode":
        return McodeAdapter(paths.home, paths.config_file)
    return ClaudeCodeAdapter(paths.home, paths.config_file)


def known_targets() -> tuple[str, ...]:
    """已注册的目标名。"""
    return DEFAULT_TARGETS


def skills_path_of(target: str, env: dict[str, str] | None = None) -> Path:
    """目标的 skills 目录。"""
    return default_target_paths(target, env).skills_path


__all__ = [
    "Adapter",
    "ClaudeCodeAdapter",
    "McodeAdapter",
    "TargetCapabilities",
    "TargetState",
    "known_targets",
    "make_adapter",
    "skills_path_of",
]
