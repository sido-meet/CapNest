"""解析器：Profile + 资产 → 期望状态。

Resolver **不碰目标文件系统**，只回答「应该有哪些 skill、它们应该长什么样」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from capnest.errors import ValidationFailed
from capnest.models import CapabilityProfile, CapabilityType, DeploymentMode
from capnest.store.assets import AssetRecord


@dataclass(frozen=True)
class DesiredAsset:
    """一个待部署的资产。"""

    asset_id: str
    name: str
    path: Path
    hash: str
    version: str
    kind: CapabilityType = CapabilityType.SKILL

    def to_dict(self) -> dict[str, object]:
        return {
            "asset": self.asset_id,
            "name": self.name,
            "version": self.version,
            "hash": self.hash,
            "path": str(self.path),
        }


@dataclass(frozen=True)
class DeploymentPlan:
    """一个目标上的期望状态。"""

    profile: str
    target: str
    assets: list[DesiredAsset] = field(default_factory=list)
    mode: DeploymentMode = DeploymentMode.COPY
    target_path: Path | None = None
    skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "target": self.target,
            "mode": str(self.mode),
            "target_path": str(self.target_path) if self.target_path else None,
            "assets": [asset.to_dict() for asset in self.assets],
            "skipped": list(self.skipped),
        }


def resolve(
    profile: CapabilityProfile,
    records: list[AssetRecord],
    target: str,
    *,
    mode: DeploymentMode = DeploymentMode.COPY,
    target_path: Path | None = None,
) -> DeploymentPlan:
    """把 Profile 解析成一个目标上的期望状态。

    引用了不存在的资产 → 退出码 3（前置校验失败）。
    非 Skill 资产第一刀不部署，列进 `skipped` 并说明原因。
    """
    known = {record.asset_id: record for record in records}
    assets: list[DesiredAsset] = []
    skipped: list[str] = []
    missing: list[str] = []

    for component in profile.spec.components:
        record = known.get(component.ref)
        if record is None:
            missing.append(component.ref)
            continue
        if record.kind is not CapabilityType.SKILL:
            skipped.append(
                f"{component.ref} [skipped: {record.kind} deployment not supported in v1]"
            )
            continue
        assets.append(
            DesiredAsset(
                asset_id=record.asset_id,
                name=record.path.name,
                path=record.path,
                hash=record.hash,
                version=record.version,
                kind=record.kind,
            )
        )

    if missing:
        raise ValidationFailed(
            f"Profile 引用的资产不存在：{', '.join(missing)}",
            {"profile": profile.metadata.id, "missing": missing},
        )

    return DeploymentPlan(
        profile=profile.metadata.id,
        target=target,
        assets=assets,
        mode=mode,
        target_path=target_path,
        skipped=skipped,
    )
