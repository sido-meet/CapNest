"""校验：资产与 Profile 的 10 项检查。

检查项与失败级别见 [006 CLI](../../docs/006-cli.md) 的 `validate` 一节。
**error 级的问题让命令以退出码 3 结束；warn 级只在 `--strict` 下升级为 error。**
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from capnest.models import API_VERSION, CapabilityProfile
from capnest.security.scan import scan_tree
from capnest.store.assets import FAMILY_TO_TYPE, AssetRecord
from capnest.store.profiles import ProfileStore

#: `spec.format` 的已知词表。
KNOWN_FORMATS: frozenset[str] = frozenset(
    {
        "agentskills.io",
        "mcp.local-config",
        "mcp.registry-server-json",
        "codex.plugin",
        "claude.plugin",
        "io.capnest.workflow/v1alpha1",
    }
)

#: `spec.permissions.requested` 的已知权限类别。
KNOWN_PERMISSIONS: frozenset[str] = frozenset(
    {"database", "network", "filesystem", "shell", "secrets"}
)

_SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


@dataclass(frozen=True)
class Violation:
    """一条校验结果。"""

    level: str
    asset: str
    location: str
    message: str
    code: str

    def to_dict(self) -> dict[str, str]:
        return {
            "level": self.level,
            "asset": self.asset,
            "location": self.location,
            "message": self.message,
            "code": self.code,
        }


def _error(code: str, asset: str, location: str, message: str) -> Violation:
    return Violation(level="error", asset=asset, location=location, message=message, code=code)


def _warn(code: str, asset: str, location: str, message: str) -> Violation:
    return Violation(level="warn", asset=asset, location=location, message=message, code=code)


def is_semver(version: str) -> bool:
    """版本号是不是合法 semver。"""
    return bool(_SEMVER.match(version))


def validate_asset(record: AssetRecord, known_ids: set[str]) -> list[Violation]:
    """对单个资产跑全部检查项。"""
    manifest = record.manifest
    asset_id = record.asset_id
    violations: list[Violation] = []

    # 1 · apiVersion 与 kind
    if manifest.api_version != API_VERSION:
        violations.append(
            _error(
                "api_version",
                asset_id,
                "apiVersion",
                f"apiVersion 应为 {API_VERSION}，实际为 {manifest.api_version}",
            )
        )
    if manifest.kind != "Capability":
        violations.append(
            _error("kind", asset_id, "kind", f"kind 应为 Capability，实际为 {manifest.kind}")
        )

    # 2 · metadata.id 与所在目录一致
    expected_id = asset_id
    if manifest.metadata.id != expected_id:
        violations.append(
            _error(
                "id_mismatch",
                asset_id,
                "metadata.id",
                f"metadata.id 应为 {expected_id}，实际为 {manifest.metadata.id}",
            )
        )

    # 3 · spec.type 与目录类别一致
    family = asset_id.split("/", 1)[0]
    expected_type = FAMILY_TO_TYPE.get(family)
    if expected_type is None:
        violations.append(
            _error("unknown_family", asset_id, "metadata.id", f"未知资产类别：{family}")
        )
    elif str(manifest.spec.type) != str(expected_type):
        violations.append(
            _error(
                "type_mismatch",
                asset_id,
                "spec.type",
                f"spec.type 应为 {expected_type}，实际为 {manifest.spec.type}",
            )
        )

    # 4 · entrypoint 指向的文件存在
    entry = record.path / manifest.spec.entrypoint.lstrip("./")
    if not entry.is_file():
        violations.append(
            _error(
                "entrypoint_missing",
                asset_id,
                "spec.entrypoint",
                f"entrypoint 指向的文件不存在：{manifest.spec.entrypoint}",
            )
        )

    # 5 · 版本号是合法 semver
    if not is_semver(manifest.metadata.version):
        violations.append(
            _error(
                "bad_version",
                asset_id,
                "metadata.version",
                f"版本号不是合法 semver：{manifest.metadata.version}",
            )
        )

    # 6 · dependencies 指向存在的资产
    dependencies = getattr(manifest.spec, "dependencies", None) or []
    for index, dependency in enumerate(dependencies):
        ref = dependency.get("ref") if isinstance(dependency, dict) else None
        if ref and ref not in known_ids:
            violations.append(
                _error(
                    "dependency_missing",
                    asset_id,
                    f"spec.dependencies[{index}].ref",
                    f"依赖的资产不存在：{ref}",
                )
            )

    # 7 · 隐藏 Unicode 扫描
    findings = scan_tree(record.path)
    for finding in findings:
        violations.append(
            _error(
                "unsafe_unicode",
                asset_id,
                f"{finding.file}:{finding.line}:{finding.column}",
                f"{finding.category}：{finding.codepoint} {finding.detail}",
            )
        )

    # 9 · format 在已知词表内
    if manifest.spec.format not in KNOWN_FORMATS:
        violations.append(
            _warn(
                "unknown_format",
                asset_id,
                "spec.format",
                f"未知的 format：{manifest.spec.format}",
            )
        )

    # 10 · permissions 用了未知类别
    permissions = getattr(manifest.spec, "permissions", None) or {}
    requested = permissions.get("requested") if isinstance(permissions, dict) else None
    for category in requested or []:
        if category not in KNOWN_PERMISSIONS:
            violations.append(
                _warn(
                    "unknown_permission",
                    asset_id,
                    "spec.permissions.requested",
                    f"未知的权限类别：{category}",
                )
            )

    return violations


def validate_profile(profile: CapabilityProfile, known_ids: set[str]) -> list[Violation]:
    """Profile 只检查一件事：引用的资产都在。"""
    violations: list[Violation] = []
    for component in profile.spec.components:
        if component.ref not in known_ids:
            violations.append(
                _error(
                    "profile_component_missing",
                    profile.metadata.id,
                    f"spec.components[{component.ref}]",
                    f"引用的资产不存在：{component.ref}",
                )
            )
    return violations


def validate_workspace(
    records: list[AssetRecord],
    profiles: list[CapabilityProfile],
    *,
    strict: bool = False,
    only: str | None = None,
) -> list[Violation]:
    """跑全部检查；`only` 限定只校验某个资产。"""
    known_ids = {record.asset_id for record in records}
    violations: list[Violation] = []
    for record in records:
        if only and record.asset_id != only:
            continue
        violations.extend(validate_asset(record, known_ids))
    if not only:
        for profile in profiles:
            violations.extend(validate_profile(profile, known_ids))
    if not strict:
        return violations
    return [
        replace(violation, level="error") if violation.level == "warn" else violation
        for violation in violations
    ]


def load_profiles(store: ProfileStore) -> list[CapabilityProfile]:
    """读取全部 Profile；坏文件直接抛错，不静默跳过。"""
    return store.list()
