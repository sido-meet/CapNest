"""Diff 引擎：目录树逐文件比对。

输出三类动作：`create` / `update` / `unchanged`。
文本文件给 unified diff，二进制只说「内容不同」——不把二进制塞进 diff。
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path

from capnest.util.text import decode_text

#: 动作取值。
CREATE = "create"
UPDATE = "update"
UNCHANGED = "unchanged"
EXTRA = "extra"


@dataclass(frozen=True)
class FileChange:
    """一个文件的变化。"""

    path: str
    action: str
    diff: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "action": self.action, "diff": self.diff}


@dataclass(frozen=True)
class SkillDiff:
    """一个 skill 目录的整体变化。"""

    name: str
    status: str
    files: list[FileChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return self.status in (CREATE, UPDATE)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "files": [item.to_dict() for item in self.files],
        }


def _list_files(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    found = [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()]
    return sorted(found)


def _unified(old: str, new: str, relative: str) -> str:
    lines = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{relative}",
        tofile=f"b/{relative}",
    )
    return "".join(lines)


def diff_skill(source: Path, target: Path | None, name: str) -> SkillDiff:
    """比对一个 skill 目录的期望内容与目标现状。"""
    if target is None or not target.is_dir():
        files = [FileChange(path=relative, action=CREATE) for relative in _list_files(source)]
        return SkillDiff(name=name, status=CREATE, files=files)

    source_files = _list_files(source)
    target_files = _list_files(target)
    changes: list[FileChange] = []

    for relative in source_files:
        source_file = source / relative
        target_file = target / relative
        if not target_file.is_file():
            changes.append(FileChange(path=relative, action=CREATE))
            continue
        source_bytes = source_file.read_bytes()
        target_bytes = target_file.read_bytes()
        if source_bytes == target_bytes:
            changes.append(FileChange(path=relative, action=UNCHANGED))
            continue
        source_text = decode_text(source_bytes)
        target_text = decode_text(target_bytes)
        if source_text is None or target_text is None:
            changes.append(
                FileChange(path=relative, action=UPDATE, diff="（二进制文件，内容不同）")
            )
            continue
        changes.append(
            FileChange(
                path=relative,
                action=UPDATE,
                diff=_unified(target_text, source_text, relative),
            )
        )

    for relative in target_files:
        if relative not in source_files:
            changes.append(FileChange(path=relative, action=EXTRA))

    # 多出来的文件也算「变了」：更新是**整个目录替换**，
    # 目标侧多出来的文件会随之消失——「两边完全相同」就得是这个意思。
    # 目标侧被用户手工改过的情况由归属检查挡住（漂移 → 拒绝写入）。
    changed = any(item.action in (CREATE, UPDATE, EXTRA) for item in changes)
    return SkillDiff(name=name, status=UPDATE if changed else UNCHANGED, files=changes)
