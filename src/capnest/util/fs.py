"""文件系统工具：目录树复制、原子替换、目录联接。

部署层的三个硬要求都由这里提供：

1. **复制保真**——文件权限、修改时间都要跟过去；
2. **原子替换**——要么替换成功，要么原文件纹丝不动；
3. **目录联接**——Windows 上用 junction，不需要开发者模式。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def copy_tree(src: Path, dst: Path) -> None:
    """复制整棵目录树，保留权限与修改时间。`dst` 已存在时先清空。"""
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, symlinks=False, dirs_exist_ok=False)


def copy_file(src: Path, dst: Path) -> None:
    """复制单个文件，保留权限与修改时间。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def atomic_write_bytes(dst: Path, data: bytes) -> None:
    """原子写文件：先写同目录下的临时文件，再 `os.replace`。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=str(dst.parent), prefix=".capnest-", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, dst)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def atomic_write_text(dst: Path, text: str) -> None:
    """原子写文本（UTF-8，LF 换行）。"""
    atomic_write_bytes(dst, text.encode("utf-8"))


def replace_dir(src: Path, dst: Path) -> None:
    """用 `src` 目录替换 `dst` 目录。

    目录不能像文件一样 `os.replace`（目标已存在时会失败），所以分三步：
    把旧目录挪到临时名 → 把新目录挪到位 → 删掉临时名。
    中间任何一步失败都会把旧目录放回去。
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    backup = dst.with_name(dst.name + ".capnest-old")
    if backup.exists():
        shutil.rmtree(backup)
    had_old = dst.exists()
    if had_old:
        os.replace(dst, backup)
    try:
        os.replace(src, dst)
    except BaseException:
        if had_old:
            os.replace(backup, dst)
        raise
    if had_old:
        shutil.rmtree(backup, ignore_errors=True)


def symlink_supported(directory: Path | None = None) -> tuple[bool, str]:
    """探测当前系统能否创建符号链接。返回 `(可用, 原因)`。"""
    base = directory or Path(tempfile.gettempdir())
    target = base / ".capnest-symlink-probe"
    source = base / ".capnest-symlink-source"
    try:
        source.mkdir(parents=True, exist_ok=True)
        target.unlink(missing_ok=True)
        os.symlink(source, target, target_is_directory=True)
    except OSError as exc:
        target.unlink(missing_ok=True)
        if source.is_dir():
            shutil.rmtree(source, ignore_errors=True)
        return False, f"符号链接不可用：{exc.strerror or exc}"
    target.unlink(missing_ok=True)
    if source.is_dir():
        shutil.rmtree(source, ignore_errors=True)
    return True, "符号链接可用"


def link_dir(src: Path, dst: Path) -> None:
    """创建目录联接。Windows 用 junction（不需要开发者模式），其它平台用符号链接。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        raise FileExistsError(f"{dst} 已存在")
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise OSError(f"创建目录联接失败：{message}")
        return
    os.symlink(src, dst, target_is_directory=True)


def iter_files(root: Path) -> list[Path]:
    """递归列出目录下的全部文件，按相对路径的 POSIX 形式排序。"""
    if not root.is_dir():
        return []
    found: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        if path.is_file():
            found.append((path.relative_to(root).as_posix(), path))
    found.sort(key=lambda item: item[0].encode("utf-8"))
    return [path for _, path in found]
