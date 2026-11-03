"""校验：10 项检查各自的行为。"""

from __future__ import annotations

from pathlib import Path

import pytest

from capnest.store.assets import AssetStore
from capnest.store.profiles import ProfileStore
from capnest.store.workspace import Workspace
from capnest.validation import is_semver, validate_workspace


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    space = Workspace(tmp_path / "ws")
    space.ensure_layout()
    return space


def make_skill(directory: Path, name: str = "demo") -> Path:
    root = directory / name
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text("---\nname: demo\n---\n\n正文\n", encoding="utf-8")
    return root


def codes(violations: list) -> set[str]:
    return {violation.code for violation in violations}


def test_clean_asset_has_no_violations(tmp_path: Path, workspace: Workspace) -> None:
    AssetStore(workspace).import_path(make_skill(tmp_path), "skill")
    records = AssetStore(workspace).scan()
    violations = validate_workspace(records, [], only="skills/demo")
    assert violations == []


def test_semver_detection() -> None:
    assert is_semver("1.0.0")
    assert is_semver("1.0.0-rc.1")
    assert is_semver("1.0.0+build.5")
    assert not is_semver("1.0")
    assert not is_semver("v1.0.0")
    assert not is_semver("")


def test_bad_id_is_an_error(tmp_path: Path, workspace: Workspace) -> None:
    AssetStore(workspace).import_path(make_skill(tmp_path), "skill")
    manifest = workspace.skills_dir / "demo" / "capability.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("id: skills/demo", "id: skills/other"),
        encoding="utf-8",
    )
    records = AssetStore(workspace).scan()
    assert "id_mismatch" in codes(validate_workspace(records, [], only="skills/demo"))


def test_unknown_format_is_a_warning(tmp_path: Path, workspace: Workspace) -> None:
    AssetStore(workspace).import_path(make_skill(tmp_path), "skill")
    manifest = workspace.skills_dir / "demo" / "capability.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("agentskills.io", "weird.format"),
        encoding="utf-8",
    )
    records = AssetStore(workspace).scan()
    violations = validate_workspace(records, [], only="skills/demo")
    assert "unknown_format" in codes(violations)
    assert all(item.level == "warn" for item in violations)


def test_strict_promotes_warnings(tmp_path: Path, workspace: Workspace) -> None:
    AssetStore(workspace).import_path(make_skill(tmp_path), "skill")
    manifest = workspace.skills_dir / "demo" / "capability.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("agentskills.io", "weird.format"),
        encoding="utf-8",
    )
    records = AssetStore(workspace).scan()
    violations = validate_workspace(records, [], strict=True, only="skills/demo")
    assert all(item.level == "error" for item in violations)


def test_missing_entrypoint_is_an_error(tmp_path: Path, workspace: Workspace) -> None:
    AssetStore(workspace).import_path(make_skill(tmp_path), "skill")
    (workspace.skills_dir / "demo" / "SKILL.md").unlink()
    records = AssetStore(workspace).scan()
    assert "entrypoint_missing" in codes(validate_workspace(records, [], only="skills/demo"))


def test_profile_with_missing_component_is_an_error(workspace: Workspace) -> None:
    store = ProfileStore(workspace)
    profile = store.create("data-agent", assets=["skills/nope"])
    violations = validate_workspace([], [profile])
    assert "profile_component_missing" in codes(violations)
