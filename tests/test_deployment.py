"""Diff、归属、原子写与备份。"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from capnest.deployment.atomic import AtomicWriter, WriteIntent
from capnest.deployment.backup import BackupStore
from capnest.deployment.diff import CREATE, EXTRA, UNCHANGED, UPDATE, diff_skill
from capnest.deployment.ownership import OwnershipRegistry
from capnest.errors import Conflict


def make_skill(root: Path, name: str = "demo", body: str = "hello\n") -> Path:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(body, encoding="utf-8")
    return directory


# --------------------------------------------------------------------- diff


def test_missing_target_is_a_create(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "src")
    diff = diff_skill(source, None, "demo")
    assert diff.status == CREATE
    assert {item.path for item in diff.files} == {"SKILL.md"}


def test_identical_content_is_unchanged(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "src")
    target = make_skill(tmp_path / "dst")
    diff = diff_skill(source, target, "demo")
    assert diff.status == UNCHANGED
    assert diff.files[0].action == UNCHANGED


def test_changed_content_is_an_update_with_a_diff(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "src", body="new\n")
    target = make_skill(tmp_path / "dst", body="old\n")
    diff = diff_skill(source, target, "demo")
    assert diff.status == UPDATE
    assert diff.files[0].action == UPDATE
    assert "-old" in diff.files[0].diff
    assert "+new" in diff.files[0].diff


def test_binary_difference_is_reported_without_bytes(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "src")
    target = make_skill(tmp_path / "dst")
    (source / "blob.bin").write_bytes(b"\x00\x01")
    (target / "blob.bin").write_bytes(b"\x00\x02")
    diff = diff_skill(source, target, "demo")
    binary = next(item for item in diff.files if item.path == "blob.bin")
    assert binary.action == UPDATE
    assert "二进制" in binary.diff


def test_extra_files_are_listed_but_not_removed(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "src")
    target = make_skill(tmp_path / "dst")
    (target / "extra.md").write_text("多出来的\n", encoding="utf-8")
    diff = diff_skill(source, target, "demo")
    extra = next(item for item in diff.files if item.path == "extra.md")
    assert extra.action == EXTRA


# ----------------------------------------------------------------- ownership


def test_unowned_path_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "skills" / "demo"
    path.mkdir(parents=True)
    registry = OwnershipRegistry(tmp_path / "ownership.json")
    with pytest.raises(Conflict) as info:
        registry.check(path)
    assert info.value.exit_code == 7
    assert info.value.details["reason"] == "not_owned"


def test_missing_path_is_allowed(tmp_path: Path) -> None:
    registry = OwnershipRegistry(tmp_path / "ownership.json")
    assert registry.check(tmp_path / "skills" / "demo") is None


def test_claimed_and_unchanged_path_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "skills" / "demo"
    make_skill(tmp_path / "skills")
    registry = OwnershipRegistry(tmp_path / "ownership.json")
    registry.claim(path)
    registry.save()
    assert registry.check(path) is None


def test_claimed_but_modified_path_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "skills" / "demo"
    make_skill(tmp_path / "skills")
    registry = OwnershipRegistry(tmp_path / "ownership.json")
    registry.claim(path)
    (path / "SKILL.md").write_text("被人改过了\n", encoding="utf-8")
    with pytest.raises(Conflict) as info:
        registry.check(path)
    assert info.value.details["reason"] == "drift"


def test_release_drops_the_claim(tmp_path: Path) -> None:
    path = tmp_path / "skills" / "demo"
    make_skill(tmp_path / "skills")
    registry = OwnershipRegistry(tmp_path / "ownership.json")
    registry.claim(path)
    registry.release(path)
    assert not registry.owned_by_us(path)


# -------------------------------------------------------------------- atomic


def test_stage_does_not_touch_the_target(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "src")
    target = tmp_path / "skills" / "demo"
    writer = AtomicWriter(BackupStore(tmp_path / "backups"), "20260101T000000Z", "mcode")
    transaction = writer.stage([WriteIntent(source=source, target=target, action=CREATE)])
    assert not target.exists()
    writer.abort(transaction)


def test_commit_replaces_and_backs_up(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "src", body="new\n")
    target = make_skill(tmp_path / "skills", body="old\n")
    backups = BackupStore(tmp_path / "backups")
    writer = AtomicWriter(backups, "20260101T000000Z", "mcode")
    transaction = writer.stage([WriteIntent(source=source, target=target, action=UPDATE)])
    writer.commit(transaction)

    assert (target / "SKILL.md").read_text(encoding="utf-8") == "new\n"
    assert transaction.backups
    ref = next(iter(transaction.backups.values()))
    assert (backups.resolve(ref) / "SKILL.md").read_text(encoding="utf-8") == "old\n"


def test_abort_restores_the_original(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "src", body="new\n")
    target = make_skill(tmp_path / "skills", body="old\n")
    writer = AtomicWriter(BackupStore(tmp_path / "backups"), "20260101T000000Z", "mcode")
    transaction = writer.stage([WriteIntent(source=source, target=target, action=UPDATE)])
    writer.commit(transaction)
    writer.abort(transaction)

    assert (target / "SKILL.md").read_text(encoding="utf-8") == "old\n"


def test_verify_reports_mismatches(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "src")
    target = tmp_path / "skills" / "demo"
    writer = AtomicWriter(BackupStore(tmp_path / "backups"), "20260101T000000Z", "mcode")
    transaction = writer.stage([WriteIntent(source=source, target=target, action=CREATE)])
    writer.commit(transaction)
    assert writer.verify(transaction) == []

    (target / "SKILL.md").write_text("变了\n", encoding="utf-8")
    assert writer.verify(transaction) == [str(target)]


# -------------------------------------------------------------------- backup


def test_backup_restore_round_trip(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "src")
    store = BackupStore(tmp_path / "backups")
    ref = store.backup("20260101T000000Z", "mcode", "demo", source)
    destination = tmp_path / "restored" / "demo"
    store.restore(ref, destination)
    assert (destination / "SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()


def test_backup_remove(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "src")
    store = BackupStore(tmp_path / "backups")
    ref = store.backup("20260101T000000Z", "mcode", "demo", source)
    store.remove(ref)
    assert not store.resolve(ref).exists()
    shutil.rmtree(source)
