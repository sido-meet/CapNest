"""Profile 仓库：创建、读取、覆盖、删除。"""

from __future__ import annotations

from pathlib import Path

import pytest

from capnest.errors import Conflict, NotFound
from capnest.store.profiles import ProfileStore
from capnest.store.workspace import Workspace


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    space = Workspace(tmp_path / "ws")
    space.ensure_layout()
    return space


def test_create_writes_a_profile(workspace: Workspace) -> None:
    store = ProfileStore(workspace)
    profile = store.create(
        "data-agent",
        assets=["skills/sql-analysis"],
        targets=["mcode", "claude-code"],
    )
    assert profile.metadata.id == "data-agent"
    assert store.path_for("data-agent").is_file()


def test_create_rejects_duplicates(workspace: Workspace) -> None:
    store = ProfileStore(workspace)
    store.create("data-agent")
    with pytest.raises(Conflict):
        store.create("data-agent")


def test_create_force_overwrites(workspace: Workspace) -> None:
    store = ProfileStore(workspace)
    store.create("data-agent", assets=["skills/a"])
    profile = store.create("data-agent", assets=["skills/b"], force=True)
    assert [item.ref for item in profile.spec.components] == ["skills/b"]


def test_get_raises_not_found(workspace: Workspace) -> None:
    with pytest.raises(NotFound):
        ProfileStore(workspace).get("nope")


def test_list_ignores_lock_files(workspace: Workspace) -> None:
    store = ProfileStore(workspace)
    store.create("data-agent")
    store.lock_path_for("data-agent").write_text("kind: CapabilityLock\n", encoding="utf-8")
    assert [profile.metadata.id for profile in store.list()] == ["data-agent"]


def test_delete(workspace: Workspace) -> None:
    store = ProfileStore(workspace)
    store.create("data-agent")
    store.delete("data-agent")
    assert not store.path_for("data-agent").exists()
