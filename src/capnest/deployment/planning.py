"""把「Profile + 目标」算成一份可执行的计划。

`plan` 与 `apply` **共用这一个函数**——这是「先能看见差异，再允许落盘」
的前提：两个命令看到的必须是同一份计划。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from capnest.adapters import make_adapter
from capnest.adapters.base import Adapter, TargetState
from capnest.config import load_config
from capnest.deployment.diff import SkillDiff, diff_skill
from capnest.deployment.resolver import DeploymentPlan, resolve
from capnest.errors import Conflict, NotFound, UsageError
from capnest.models import DeploymentMode
from capnest.store.assets import AssetStore
from capnest.store.profiles import ProfileStore
from capnest.store.workspace import Workspace


@dataclass
class TargetPlan:
    """一个目标上的完整计划。"""

    target: str
    adapter: Adapter
    plan: DeploymentPlan
    state: TargetState
    diffs: list[SkillDiff] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return any(item.has_changes for item in self.diffs)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "mode": str(self.plan.mode),
            "target_path": str(self.plan.target_path) if self.plan.target_path else None,
            "assets": [asset.to_dict() for asset in self.plan.assets],
            "diffs": [item.to_dict() for item in self.diffs],
            "skipped": list(self.plan.skipped),
            "nested": list(self.state.nested),
        }


def parse_targets(value: str) -> list[str]:
    """解析 `--target`：逗号分隔，可重复出现。"""
    names: list[str] = []
    for chunk in value.split(","):
        for name in chunk.split():
            if name and name not in names:
                names.append(name)
    return names


def resolve_profile_name(workspace: Workspace, explicit: str | None) -> str:
    """确定用哪个 Profile：命令行优先，否则取 `config.yaml` 的默认值。"""
    if explicit:
        return explicit
    config = load_config(workspace.config_file)
    if not config.default_profile:
        raise UsageError(
            "没有指定 --profile，工作区也没有 default_profile",
            {"hint": "capnest plan --profile <NAME>"},
        )
    return config.default_profile


def build_plans(
    workspace: Workspace,
    profile_name: str | None,
    targets: list[str],
    *,
    mode: DeploymentMode = DeploymentMode.COPY,
) -> list[TargetPlan]:
    """算出每个目标的计划。"""
    profiles = ProfileStore(workspace)
    name = resolve_profile_name(workspace, profile_name)
    try:
        profile = profiles.get(name)
    except NotFound:
        raise

    records = AssetStore(workspace).scan()
    plans: list[TargetPlan] = []
    for target in targets:
        adapter = make_adapter(target)
        state = adapter.read()
        plan = resolve(profile, records, target, mode=mode, target_path=adapter.skills_path)
        diffs = [
            diff_skill(asset.path, adapter.skill_path(asset.name), asset.name)
            for asset in plan.assets
        ]
        _reject_nested(plan, state, target)
        plans.append(
            TargetPlan(target=target, adapter=adapter, plan=plan, state=state, diffs=diffs)
        )
    return plans


def _reject_nested(plan: DeploymentPlan, state: TargetState, target: str) -> None:
    """目标 skills 目录只支持单层；检测到嵌套就拒绝覆盖。"""
    nested = set(state.nested)
    clashes = [asset.name for asset in plan.assets if asset.name in nested]
    if clashes:
        raise Conflict(
            "目标 skill 目录包含嵌套子目录，v1 不支持覆盖",
            {"target": target, "paths": clashes},
        )


def skill_target_path(workspace: Workspace, target: str, name: str) -> Path:
    """目标侧某个 skill 的落点。"""
    return make_adapter(target).skill_path(name)
