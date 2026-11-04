"""冲突裁决的落盘处：`state/conflicts.json`。

**冲突**指的是：工作区里的资产与某个目标侧同名目录内容不同。
CapNest 不替用户决定「哪一份对」——它只负责把分歧摆出来，并记住裁决：

| 裁决 | 含义 |
| --- | --- |
| `workspace` | 以工作区为准——下次同步覆盖目标侧 |
| `target` | 以目标为准——目标侧内容已被拉回工作区 |

裁决记下来是为了让「同步」可重复执行：下一次不用再问一遍。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from capnest.store.workspace import Workspace

#: 裁决取值。
WORKSPACE = "workspace"
TARGET = "target"


@dataclass(frozen=True)
class Resolution:
    """一条裁决。"""

    asset: str
    target: str
    decision: str
    at: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> Resolution:
        return cls(
            asset=str(raw.get("asset", "")),
            target=str(raw.get("target", "")),
            decision=str(raw.get("decision", "")),
            at=str(raw.get("at", "")),
        )


class ConflictStore:
    """`state/conflicts.json` 的读写入口。"""

    def __init__(self, workspace: Workspace) -> None:
        self.path = workspace.state_dir / "conflicts.json"

    # ------------------------------------------------------------------ 读写

    def load(self) -> list[Resolution]:
        if not self.path.is_file():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(raw, list):
            return []
        return [Resolution.from_dict(item) for item in raw if isinstance(item, dict)]

    def save(self, resolutions: list[Resolution]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [item.to_dict() for item in resolutions]
        text = json.dumps(payload, ensure_ascii=True, indent=2)
        self.path.write_text(text + "\n", encoding="utf-8")

    # ------------------------------------------------------------------ 查询

    def find(self, asset: str, target: str) -> Resolution | None:
        """某个资产在某个目标上的裁决。"""
        for item in self.load():
            if item.asset == asset and item.target == target:
                return item
        return None

    # ------------------------------------------------------------------ 写入

    def resolve(self, asset: str, target: str, decision: str, at: str = "") -> Resolution:
        """记下一条裁决（覆盖同资产同目标的旧裁决）。"""
        resolutions = [
            item for item in self.load() if not (item.asset == asset and item.target == target)
        ]
        resolution = Resolution(asset=asset, target=target, decision=decision, at=at)
        resolutions.append(resolution)
        self.save(resolutions)
        return resolution
