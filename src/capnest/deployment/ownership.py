"""归属证明：CapNest 有没有资格改这个路径。

规则只有一条，但它决定了 CapNest 敢不敢动用户的数据：

> **无法证明归属的既有路径，一律拒绝写入。**

「已 claim 但指纹不符」视为漂移，同样拒绝——用户手改过的东西，
不该被 CapNest 悄悄覆盖掉。
"""

from __future__ import annotations

import json
from pathlib import Path

from capnest.errors import Conflict
from capnest.hashing import hash_dir


def fingerprint(path: Path) -> str:
    """路径的指纹。目录按内容哈希，文件按单文件哈希。"""
    if path.is_dir():
        return hash_dir(path)
    from capnest.hashing import hash_file

    return hash_file(path)


def _key(path: Path) -> str:
    """归属表的键。统一成绝对路径的字符串形式。"""
    return str(path.resolve())


class OwnershipRegistry:
    """`state/ownership.json`：路径 → 指纹。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: dict[str, str] | None = None

    # ------------------------------------------------------------------ 读写

    def _load(self) -> dict[str, str]:
        if self._entries is None:
            if not self.path.is_file():
                self._entries = {}
            else:
                raw = json.loads(self.path.read_text(encoding="utf-8") or "{}")
                self._entries = {str(k): str(v) for k, v in raw.items()}
        return self._entries

    def save(self) -> None:
        """写回磁盘。"""
        entries = self._load()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(entries, ensure_ascii=True, indent=2, sort_keys=True)
        self.path.write_text(text + "\n", encoding="utf-8")

    # ------------------------------------------------------------------ 查询

    def claimed(self, path: Path) -> str | None:
        """这个路径的 claim 指纹；没有 claim 则返回 None。"""
        return self._load().get(_key(path))

    def owned_by_us(self, path: Path) -> bool:
        """路径是否已被 CapNest claim。"""
        return self.claimed(path) is not None

    def check(self, path: Path) -> str | None:
        """写入前的归属检查。

        返回 None 表示可以写；否则抛 Conflict。
        """
        if not path.exists():
            return None
        stored = self.claimed(path)
        if stored is None:
            raise Conflict(
                "目标路径已存在且不由 CapNest 管理，拒绝写入",
                {"path": str(path), "reason": "not_owned"},
            )
        current = fingerprint(path)
        if stored != current:
            raise Conflict(
                "目标路径已被外部修改，拒绝写入",
                {
                    "path": str(path),
                    "reason": "drift",
                    "expected": stored,
                    "actual": current,
                },
            )
        return None

    # ------------------------------------------------------------------ 变更

    def claim(self, path: Path, value: str | None = None) -> None:
        """claim 一个路径。"""
        self._load()[_key(path)] = value or fingerprint(path)

    def release(self, path: Path) -> None:
        """释放一个路径的 claim。"""
        self._load().pop(_key(path), None)
