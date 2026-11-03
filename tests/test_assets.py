"""资产仓库：扫描、导入、收编。"""

from __future__ import annotations

from pathlib import Path

import pytest

from capnest.errors import Conflict, NotFound, UnsafeContent, ValidationFailed
from capnest.store.assets import AssetStore
from capnest.store.workspace import Workspace


def make_skill(directory: Path, name: str = "demo") -> Path:
    """造一个最小 skill 目录。"""
    root = directory / name
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        "---\nname: demo\ndescription: 演示用的 skill\n---\n\n正文\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    space = Workspace(tmp_path / "ws")
    space.ensure_layout()
    return space


def test_import_path_copies_and_generates_manifest(tmp_path: Path, workspace: Workspace) -> None:
    source = make_skill(tmp_path)
    record = AssetStore(workspace).import_path(source, "skill")

    assert record.asset_id == "skills/demo"
    assert record.path == workspace.skills_dir / "demo"
    assert (record.path / "capability.yaml").is_file()
    assert record.manifest.metadata.version == "0.1.0"
    assert record.manifest.spec.type == "skill"
    assert record.manifest.spec.entrypoint == "./SKILL.md"


def test_import_copies_instead_of_referencing(tmp_path: Path, workspace: Workspace) -> None:
    source = make_skill(tmp_path)
    record = AssetStore(workspace).import_path(source, "skill")
    (record.path / "SKILL.md").write_text("changed\n", encoding="utf-8")
    assert (source / "SKILL.md").read_text(encoding="utf-8") != "changed\n"


def test_import_rejects_duplicate(tmp_path: Path, workspace: Workspace) -> None:
    source = make_skill(tmp_path)
    store = AssetStore(workspace)
    store.import_path(source, "skill")
    with pytest.raises(Conflict):
        store.import_path(source, "skill")


def test_import_force_overrides(tmp_path: Path, workspace: Workspace) -> None:
    source = make_skill(tmp_path)
    store = AssetStore(workspace)
    store.import_path(source, "skill")
    record = store.import_path(source, "skill", force=True)
    assert record.asset_id == "skills/demo"


def test_import_blocks_unsafe_content(tmp_path: Path, workspace: Workspace) -> None:
    source = make_skill(tmp_path)
    (source / "SKILL.md").write_text("x\u200ey", encoding="utf-8")
    with pytest.raises(UnsafeContent):
        AssetStore(workspace).import_path(source, "skill")


def test_import_rejects_unknown_kind(tmp_path: Path, workspace: Workspace) -> None:
    source = make_skill(tmp_path)
    with pytest.raises(ValidationFailed):
        AssetStore(workspace).import_path(source, "plugin")


def test_import_requires_a_directory(tmp_path: Path, workspace: Workspace) -> None:
    with pytest.raises(NotFound):
        AssetStore(workspace).import_path(tmp_path / "missing", "skill")


def test_import_keeps_existing_manifest(tmp_path: Path, workspace: Workspace) -> None:
    source = make_skill(tmp_path)
    (source / "capability.yaml").write_text(
        "apiVersion: io.capnest.capability/v1alpha1\n"
        "kind: Capability\n"
        "metadata:\n"
        "  id: skills/demo\n"
        "  name: Demo\n"
        "  version: 2.1.0\n"
        "spec:\n"
        "  type: skill\n"
        "  format: agentskills.io\n"
        "  entrypoint: ./SKILL.md\n",
        encoding="utf-8",
    )
    record = AssetStore(workspace).import_path(source, "skill")
    assert record.version == "2.1.0"


def test_scan_lists_imported_assets(tmp_path: Path, workspace: Workspace) -> None:
    store = AssetStore(workspace)
    store.import_path(make_skill(tmp_path), "skill")
    records = store.scan()
    assert [record.asset_id for record in records] == ["skills/demo"]


def test_get_raises_not_found(workspace: Workspace) -> None:
    with pytest.raises(NotFound):
        AssetStore(workspace).get("skills/nope")


def test_adopt_from_target_leaves_the_original_untouched(
    tmp_path: Path,
    workspace: Workspace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skills = tmp_path / "target-home" / "skills"
    skills.mkdir(parents=True)
    original = skills / "manim"
    original.mkdir()
    (original / "SKILL.md").write_text("original\n", encoding="utf-8")
    before = (original / "SKILL.md").read_bytes()

    monkeypatch.setenv("CAPNEST_TARGET_HOME_MCODE", str(tmp_path / "target-home"))
    record = AssetStore(workspace).adopt_from_target("mcode", "manim")

    assert record.asset_id == "skills/manim"
    assert (record.path / "SKILL.md").read_text(encoding="utf-8") == "original\n"
    assert (original / "SKILL.md").read_bytes() == before
    assert not (original / "capability.yaml").exists()


def test_adopt_missing_skill_raises_not_found(
    tmp_path: Path,
    workspace: Workspace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAPNEST_TARGET_HOME_MCODE", str(tmp_path / "target-home"))
    with pytest.raises(NotFound):
        AssetStore(workspace).adopt_from_target("mcode", "nope")
