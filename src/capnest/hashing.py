"""规范化内容哈希。

**规则必须写死**，否则跨机器哈希不一致，两边就永远比不出「一样」。
规则表见 [003 Architecture](../../docs/003-architecture.md)：

| 规则 | 取值 |
| --- | --- |
| 文件遍历 | 递归，按相对路径 POSIX 风格**字节序排序** |
| 排除 | `__pycache__/`、`*.pyc`、`.git/`、`.DS_Store`、`Thumbs.db`、`.venv/` |
| 换行归一 | 文本文件 CRLF / CR → LF |
| 编码 | UTF-8；解码失败视为二进制 |
| 二进制判定 | 含 NUL 字节或不可 UTF-8 解码 → 用原始字节 |
| 是否含 `capability.yaml` | **包含** |
| 最终计算 | 逐文件算 SHA256，拼接为 `relpath\0hash\n`，再对整体算 SHA256 |
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

from capnest.util.text import decode_text

#: 参与哈希时忽略的目录名。
EXCLUDED_DIRS: frozenset[str] = frozenset({"__pycache__", ".git", ".venv"})

#: 参与哈希时忽略的文件名。
EXCLUDED_FILES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db"})

#: 参与哈希时忽略的后缀。
EXCLUDED_SUFFIXES: tuple[str, ...] = (".pyc",)


def is_excluded(relative: str) -> bool:
    """相对路径是否落在排除规则里。"""
    parts = Path(relative).parts
    for part in parts[:-1]:
        if part in EXCLUDED_DIRS:
            return True
    name = parts[-1]
    if name in EXCLUDED_FILES:
        return True
    return name.endswith(EXCLUDED_SUFFIXES)


def hash_bytes(data: bytes) -> str:
    """单个文件的哈希。文本先归一换行，二进制用原始字节。"""
    text = decode_text(data)
    payload = data if text is None else text.encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def hash_file(path: Path) -> str:
    """单个文件的哈希。"""
    return hash_bytes(path.read_bytes())


def hash_dir(
    path: Path,
    *,
    exclude: Sequence[str] | None = None,
    exclude_files: Sequence[str] | None = None,
) -> str:
    """目录树的规范化哈希。

    `exclude` 是额外的排除目录名，追加在默认规则之外。
    `exclude_files` 是额外的排除文件（相对路径，POSIX 风格）。
    """
    extra = set(exclude or ())
    ignored_files = set(exclude_files or ())
    entries: list[tuple[str, Path]] = []
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        relative = item.relative_to(path).as_posix()
        if is_excluded(relative):
            continue
        if relative in ignored_files:
            continue
        if extra.intersection(Path(relative).parts):
            continue
        entries.append((relative, item))
    entries.sort(key=lambda pair: pair[0].encode("utf-8"))

    digest = hashlib.sha256()
    for relative, item in entries:
        file_hash = hash_file(item)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(file_hash.removeprefix("sha256:").encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def hash_text(text: str) -> str:
    """一段文本的哈希（换行已归一）。"""
    return hash_bytes(text.encode("utf-8"))
