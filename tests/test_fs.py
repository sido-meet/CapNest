"""文件系统工具：只读文件也删得掉。

Windows 上 git 的 pack 文件是 444，直接 `shutil.rmtree` 会 PermissionError——
替换一个带 `.git` 的 skill 目录就会半路失败。
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from capnest.util.fs import remove_tree


def test_remove_tree_deletes_readonly_files(tmp_path: Path) -> None:
    directory = tmp_path / "skill"
    (directory / ".git" / "objects").mkdir(parents=True)
    pack = directory / ".git" / "objects" / "pack-abc.idx"
    pack.write_bytes(b"readonly")
    os.chmod(pack, stat.S_IREAD)

    remove_tree(directory)

    assert not directory.exists()


def test_remove_tree_is_a_noop_for_missing_path(tmp_path: Path) -> None:
    remove_tree(tmp_path / "nothing")
    assert not (tmp_path / "nothing").exists()


def test_copy_tree_replaces_readonly_destination(tmp_path: Path) -> None:
    from capnest.util.fs import copy_tree

    source = tmp_path / "src"
    source.mkdir()
    (source / "SKILL.md").write_text("new\n", encoding="utf-8")

    destination = tmp_path / "dst"
    destination.mkdir()
    old = destination / "old.md"
    old.write_text("old\n", encoding="utf-8")
    os.chmod(old, stat.S_IREAD)

    copy_tree(source, destination)

    assert (destination / "SKILL.md").read_text(encoding="utf-8") == "new\n"
    assert not (destination / "old.md").exists()
