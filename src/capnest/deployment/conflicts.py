"""冲突检测：目标侧的内容与**两边都不一致**时，才是冲突。

这是最容易搞错的一件事，所以写死：

| 目标侧内容 | 判定 | 处理 |
| --- | --- | --- |
| 与工作区一致 | 已同步 | 什么都不做 |
| 与**上次部署**的版本一致 | 工作区更新了 | 正常同步（这就是「改一处，两边同步」） |
| 与工作区**和**上次部署都不一致 | **冲突** | 需要人裁决 |

第三种才是冲突：目标侧在部署之后被**外部**改过了（漂移），
或者两个 Agent 侧本来就有同名不同内容的资产（分歧）。
前两种都不该拦住同步——拦住同步就等于把 CapNest 的核心用途堵死了。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from capnest.adapters import make_adapter
from capnest.deployment.state import DeploymentStore
from capnest.hashing import hash_dir
from capnest.models import CapabilityType
from capnest.store.assets import AssetStore, content_hash
from capnest.store.workspace import Workspace

#: 冲突的两种来源。
DIVERGENCE = "divergence"  # 两边本来就不一样（还没部署过）
DRIFT = "drift"  # 部署之后被外部改了


@dataclass(frozen=True)
class Conflict:
    """一处需要人裁决的分歧。"""

    asset: str
    name: str
    target: str
    workspace_hash: str
    target_hash: str
    deployed_hash: str
    kind: str

    def to_dict(self) -> dict[str, str]:
        return {
            "asset": self.asset,
            "name": self.name,
            "target": self.target,
            "workspaceHash": self.workspace_hash,
            "targetHash": self.target_hash,
            "deployedHash": self.deployed_hash,
            "kind": self.kind,
        }


def deployed_hashes(workspace: Workspace, target: str) -> dict[str, str]:
    """某个目标上，每个资产**上次部署**时的内容哈希。"""
    store = DeploymentStore(workspace.deployments_file)
    records = [record for record in store.load() if record.target == target]
    if not records:
        return {}
    latest = max(records, key=lambda record: record.created_at)
    return dict(latest.asset_hashes)


def detect_conflicts(workspace: Workspace, target: str) -> list[Conflict]:
    """列出这个目标上需要裁决的分歧。"""
    assets = AssetStore(workspace)
    adapter = make_adapter(target)
    deployed = deployed_hashes(workspace, target)
    conflicts: list[Conflict] = []
    for record in assets.scan():
        if record.kind is not CapabilityType.SKILL:
            continue
        target_dir = adapter.skill_path(record.name)
        if not target_dir.is_dir():
            continue
        # 两个哈希各管一件事：
        #   内容哈希——「是不是同一份能力」（忽略 manifest）；
        #   完整哈希——「目标侧有没有被动过」（与部署记录里存的一致）。
        if content_hash(target_dir) == content_hash(record.path):
            continue
        deployed_hash = deployed.get(record.asset_id, "")
        if deployed_hash and hash_dir(target_dir) == deployed_hash:
            # 目标侧没被动过——只是工作区更新了。这是正常同步，不是冲突。
            continue
        conflicts.append(
            Conflict(
                asset=record.asset_id,
                name=record.name,
                target=target,
                workspace_hash=hash_dir(record.path),
                target_hash=hash_dir(target_dir),
                deployed_hash=deployed_hash,
                kind=DRIFT if deployed_hash else DIVERGENCE,
            )
        )
    return conflicts


def target_path(target: str, name: str) -> Path:
    """目标侧某个 skill 的落点。"""
    return make_adapter(target).skill_path(name)
