"""部署记录：`state/deployments.json`。

一条记录 = 一次 apply。回滚靠它，状态汇报也靠它。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


def timestamp_now() -> str:
    """当前时间戳（秒级，UTC）。"""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    """当前时间的 ISO 8601 表示（UTC）。"""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class DeploymentRecord:
    """一次部署的记录。"""

    id: str
    profile: str
    target: str
    created_at: str
    mode: str = "copy"
    applied_paths: list[str] = field(default_factory=list)
    backups: dict[str, str] = field(default_factory=dict)
    created_paths: list[str] = field(default_factory=list)
    asset_hashes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> DeploymentRecord:
        return cls(
            id=str(raw.get("id", "")),
            profile=str(raw.get("profile", "")),
            target=str(raw.get("target", "")),
            created_at=str(raw.get("created_at", "")),
            mode=str(raw.get("mode", "copy")),
            applied_paths=[str(item) for item in raw.get("applied_paths", [])],
            backups={str(k): str(v) for k, v in (raw.get("backups") or {}).items()},
            created_paths=[str(item) for item in raw.get("created_paths", [])],
            asset_hashes={str(k): str(v) for k, v in (raw.get("asset_hashes") or {}).items()},
        )


class DeploymentStore:
    """`state/deployments.json` 的读写入口。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[DeploymentRecord]:
        """读出全部记录。"""
        if not self.path.is_file():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(raw, list):
            return []
        return [DeploymentRecord.from_dict(item) for item in raw if isinstance(item, dict)]

    def save(self, records: list[DeploymentRecord]) -> None:
        """写回全部记录。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.to_dict() for record in records]
        text = json.dumps(payload, ensure_ascii=True, indent=2)
        self.path.write_text(text + "\n", encoding="utf-8")

    def append(self, record: DeploymentRecord) -> None:
        records = self.load()
        records.append(record)
        self.save(records)

    def remove(self, record_id: str) -> None:
        records = [record for record in self.load() if record.id != record_id]
        self.save(records)

    def latest_for(self, target: str) -> DeploymentRecord | None:
        """某个目标最近一条记录。"""
        candidates = [record for record in self.load() if record.target == target]
        if not candidates:
            return None
        return max(candidates, key=lambda record: record.created_at)

    def find(self, record_id: str) -> DeploymentRecord | None:
        """按 ID 找一条记录。"""
        for record in self.load():
            if record.id == record_id:
                return record
        return None
