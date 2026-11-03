"""文本归一与二进制判定。

哈希、diff、归属指纹全部依赖这两个判断，所以它们必须**只有一个实现**：
同一份内容在任何机器上都要得到同一个哈希。
"""

from __future__ import annotations

from pathlib import Path

#: 判定为二进制的字节。
NUL = b"\x00"


def normalize_newlines(text: str) -> str:
    """CRLF 与 CR 一律归一为 LF。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def is_binary(data: bytes) -> bool:
    """含 NUL 字节或不可 UTF-8 解码 → 判为二进制。"""
    if NUL in data:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def decode_text(data: bytes) -> str | None:
    """尝试按 UTF-8 解码并归一换行；不是文本则返回 None。"""
    if is_binary(data):
        return None
    return normalize_newlines(data.decode("utf-8"))


def read_text(path: Path) -> str | None:
    """读一个文件并归一；不是文本返回 None。"""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return decode_text(data)
