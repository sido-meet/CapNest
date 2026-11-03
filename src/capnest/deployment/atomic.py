"""原子写 + 预写事务。

三段式：**stage → commit → verify**。

- stage：把新内容写到临时目录，**不动目标**；
- commit：备份原内容 → 原子替换 → 校验指纹；
- abort：把已经提交的部分还原。

任何一步失败，已提交的部分都会回到原样——要么没写，要么写完整。
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from capnest.deployment.backup import BackupStore
from capnest.hashing import hash_dir
from capnest.util.fs import copy_tree


@dataclass(frozen=True)
class WriteIntent:
    """一次写入的意图。"""

    source: Path
    target: Path
    action: str
    asset_id: str = ""
    name: str = ""


@dataclass
class Transaction:
    """一个事务的现场。"""

    intents: list[WriteIntent] = field(default_factory=list)
    staged: dict[str, Path] = field(default_factory=dict)
    committed: list[WriteIntent] = field(default_factory=list)
    backups: dict[str, str] = field(default_factory=dict)
    created: list[str] = field(default_factory=list)


class AtomicWriter:
    """把一批写入变成「全成或全不成」。"""

    def __init__(self, backups: BackupStore, timestamp: str, target: str) -> None:
        self.backups = backups
        self.timestamp = timestamp
        self.target = target

    # ------------------------------------------------------------------ stage

    def stage(self, intents: list[WriteIntent]) -> Transaction:
        """把新内容写到目标旁边的临时目录。目标本身不动。"""
        transaction = Transaction(intents=list(intents))
        for intent in intents:
            target = intent.target
            target.parent.mkdir(parents=True, exist_ok=True)
            staged = Path(tempfile.mkdtemp(dir=str(target.parent), prefix=".capnest-stage-"))
            copy_tree(intent.source, staged / intent.name)
            transaction.staged[str(target)] = staged
        return transaction

    # ------------------------------------------------------------------ commit

    def commit(self, transaction: Transaction) -> None:
        """逐项「备份 → 替换 → 校验」。失败自动回滚已提交的部分。"""
        try:
            for intent in transaction.intents:
                target = intent.target
                staged = transaction.staged[str(target)]
                payload = staged / intent.name
                if target.exists():
                    ref = self.backups.backup(
                        self.timestamp,
                        self.target,
                        intent.name,
                        target,
                    )
                    transaction.backups[str(target)] = ref
                    shutil.rmtree(target)
                else:
                    transaction.created.append(str(target))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(payload), str(target))
                transaction.committed.append(intent)
                shutil.rmtree(staged, ignore_errors=True)
        except BaseException:
            self.abort(transaction)
            raise

    # ------------------------------------------------------------------ abort

    def abort(self, transaction: Transaction) -> None:
        """回滚：还原备份，删掉新建的路径，清掉暂存目录。"""
        for intent in reversed(transaction.committed):
            target = intent.target
            ref = transaction.backups.get(str(target))
            if ref:
                self.backups.restore(ref, target)
            elif target.exists():
                shutil.rmtree(target, ignore_errors=True)
        transaction.committed.clear()
        for staged in transaction.staged.values():
            shutil.rmtree(staged, ignore_errors=True)
        transaction.staged.clear()

    # ------------------------------------------------------------------ verify

    def verify(self, transaction: Transaction) -> list[str]:
        """校验每个已写路径的指纹。返回不一致的路径列表。"""
        mismatched: list[str] = []
        for intent in transaction.committed:
            if not intent.target.is_dir():
                mismatched.append(str(intent.target))
                continue
            if hash_dir(intent.target) != hash_dir(intent.source):
                mismatched.append(str(intent.target))
        return mismatched
