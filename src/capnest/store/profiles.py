"""Profile 仓库：读取 `profiles/*.yaml`。

Profile 是**部署单位**：它引用哪些资产、部署到哪些目标。
Lockfile（`*.lock.yaml`）第一刀只保留读写能力，不参与部署计算。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from capnest.errors import Conflict, NotFound, ValidationFailed
from capnest.models import (
    API_VERSION,
    CapabilityLock,
    CapabilityProfile,
    ProfileComponent,
)
from capnest.store.workspace import Workspace

LOCK_SUFFIX = ".lock.yaml"


class ProfileStore:
    """`profiles/` 目录的读写入口。"""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def path_for(self, name: str) -> Path:
        return self.workspace.profiles_dir / f"{name}.yaml"

    def lock_path_for(self, name: str) -> Path:
        return self.workspace.profiles_dir / f"{name}{LOCK_SUFFIX}"

    # ------------------------------------------------------------------ 读

    def list(self) -> list[CapabilityProfile]:
        """列出全部 Profile（不含 lockfile）。"""
        profiles: list[CapabilityProfile] = []
        if not self.workspace.profiles_dir.is_dir():
            return profiles
        for path in sorted(self.workspace.profiles_dir.glob("*.yaml")):
            if path.name.endswith(LOCK_SUFFIX):
                continue
            profiles.append(self._load(path))
        return profiles

    def get(self, name: str) -> CapabilityProfile:
        """按名字取一个 Profile，不存在则报 NOT_FOUND。"""
        path = self.path_for(name)
        if not path.is_file():
            raise NotFound(f"Profile 不存在：{name}", {"profile": name})
        return self._load(path)

    def exists(self, name: str) -> bool:
        return self.path_for(name).is_file()

    def _load(self, path: Path) -> CapabilityProfile:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValidationFailed(
                f"{path.name} 不是合法的 YAML",
                {"path": str(path), "reason": str(exc)},
            ) from None
        if not isinstance(raw, dict):
            raise ValidationFailed(
                f"{path.name} 的顶层必须是映射",
                {"path": str(path)},
            )
        try:
            return CapabilityProfile.model_validate(raw)
        except Exception as exc:
            raise ValidationFailed(
                f"{path.name} 不符合 CapabilityProfile 结构",
                {"path": str(path), "reason": str(exc)},
            ) from None

    # ------------------------------------------------------------------ 写

    def create(
        self,
        name: str,
        *,
        assets: list[str] | None = None,
        targets: list[str] | None = None,
        force: bool = False,
    ) -> CapabilityProfile:
        """新建一个 Profile。同名已存在时拒绝，除非 `force`。"""
        path = self.path_for(name)
        if path.is_file() and not force:
            raise Conflict(
                f"Profile 已存在：{name}",
                {"profile": name, "path": str(path)},
            )
        profile = CapabilityProfile.model_validate(
            {
                "apiVersion": API_VERSION,
                "kind": "CapabilityProfile",
                "metadata": {
                    "id": name,
                    "name": name,
                    "version": "0.1.0",
                    "description": "",
                },
                "spec": {
                    "components": [{"ref": ref} for ref in (assets or [])],
                    "targets": list(targets or []),
                },
            }
        )
        self.save(profile)
        return profile

    def save(self, profile: CapabilityProfile) -> Path:
        """写出一个 Profile。"""
        path = self.path_for(profile.metadata.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = profile.model_dump(mode="json", by_alias=True, exclude_none=True)
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        path.write_text(text, encoding="utf-8")
        return path

    def delete(self, name: str) -> None:
        """删除一个 Profile。"""
        path = self.path_for(name)
        if not path.is_file():
            raise NotFound(f"Profile 不存在：{name}", {"profile": name})
        path.unlink()

    # ------------------------------------------------------------------ 锁文件

    def save_lock(self, lock: CapabilityLock) -> Path:
        """写出一个 Lockfile。"""
        path = self.lock_path_for(lock.metadata.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = lock.model_dump(mode="json", by_alias=True, exclude_none=True)
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        path.write_text(text, encoding="utf-8")
        return path

    def load_lock(self, name: str) -> CapabilityLock | None:
        """读出 Lockfile；不存在返回 None。"""
        path = self.lock_path_for(name)
        if not path.is_file():
            return None
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValidationFailed(
                f"{path.name} 的顶层必须是映射",
                {"path": str(path)},
            )
        try:
            return CapabilityLock.model_validate(raw)
        except Exception as exc:
            raise ValidationFailed(
                f"{path.name} 不符合 CapabilityLock 结构",
                {"path": str(path), "reason": str(exc)},
            ) from None


def profile_components(profile: CapabilityProfile) -> list[str]:
    """Profile 引用的资产 ID 列表。"""
    return [component.ref for component in profile.spec.components]


def make_profile(name: str, assets: list[str], targets: list[str]) -> CapabilityProfile:
    """构造一个 Profile（供命令层使用）。"""
    return CapabilityProfile.model_validate(
        {
            "apiVersion": API_VERSION,
            "kind": "CapabilityProfile",
            "metadata": {"id": name, "name": name, "version": "0.1.0", "description": ""},
            "spec": {
                "components": [{"ref": ref} for ref in assets],
                "targets": list(targets),
            },
        }
    )


__all__ = [
    "LOCK_SUFFIX",
    "ProfileComponent",
    "ProfileStore",
    "make_profile",
    "profile_components",
]
