"""备份与还原。

备份落在 `state/backups/<timestamp>/<target>/<name>/`——**在 CapNest 自己的
工作区里**，不污染 Agent 侧。

`created_paths`（本次新建的路径）不备份：回滚时直接删掉。
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from capnest.util.fs import copy_tree


@dataclass(frozen=True)
class BackupRef:
    """一条备份记录。"""

    path: Path
    ref: str


class BackupStore:
    """`state/backups/` 的读写入口。"""

    def __init__(self, root: Path) -> None:
        self.root = root

    def session_dir(self, timestamp: str, target: str) -> Path:
        """一次部署的备份目录。"""
        return self.root / timestamp / target

    def backup(self, timestamp: str, target: str, name: str, source: Path) -> str:
        """备份一个路径，返回相对 `state/backups/` 的引用。"""
        destination = self.session_dir(timestamp, target) / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            copy_tree(source, destination)
        else:
            shutil.copy2(source, destination)
        return f"{timestamp}/{target}/{name}"

    def resolve(self, ref: str) -> Path:
        """引用 → 磁盘路径。"""
        return self.root / ref

    def restore(self, ref: str, destination: Path) -> None:
        """把一份备份还原回原处。"""
        source = self.resolve(ref)
        if not source.exists():
            raise FileNotFoundError(f"备份不存在：{ref}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            copy_tree(source, destination)
        else:
            shutil.copy2(source, destination)

    def remove(self, ref: str) -> None:
        """删掉一份备份。"""
        source = self.resolve(ref)
        if source.is_dir():
            shutil.rmtree(source, ignore_errors=True)
        elif source.exists():
            source.unlink()
