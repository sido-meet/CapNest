"""批量收编与来源标记。"""

from __future__ import annotations

from pathlib import Path

import pytest


def make_skill(home: Path, name: str, *, manifest: bool = True, nested: bool = False) -> Path:
    directory = home / "skills" / name
    directory.mkdir(parents=True, exist_ok=True)
    if manifest:
        (directory / "SKILL.md").write_text("---\nname: x\n---\n\n正文\n", encoding="utf-8")
    if nested:
        inner = directory / "inner"
        inner.mkdir()
        (inner / "SKILL.md").write_text("---\nname: inner\n---\n", encoding="utf-8")
    return directory


@pytest.fixture
def target_home(tmp_path: Path) -> Path:
    home = tmp_path / "claude-home"
    home.mkdir()
    return home


@pytest.fixture
def env(target_home: Path) -> dict[str, str]:
    return {"CAPNEST_TARGET_HOME_CLAUDE_CODE": str(target_home)}


@pytest.fixture
def workspace(tmp_path: Path, run_cli) -> Path:
    path = tmp_path / "ws"
    assert run_cli("init", str(path)).returncode == 0
    return path


def test_bulk_adopt_collects_everything(run_cli, workspace, target_home, env) -> None:
    make_skill(target_home, "alpha")
    make_skill(target_home, "beta")
    result = run_cli("--json", "add", "--from", "claude-code:*", workspace=workspace, env=env)
    assert result.returncode == 0, result.stderr
    assert result.data["count"] == 2
    assert {item["id"] for item in result.data["adopted"]} == {
        "skills/alpha",
        "skills/beta",
    }


def test_bulk_adopt_skips_nested_and_container(run_cli, workspace, target_home, env) -> None:
    make_skill(target_home, "alpha")
    make_skill(target_home, "container", manifest=False)
    make_skill(target_home, "wrapped", nested=True)
    result = run_cli("--json", "add", "--from", "claude-code:*", workspace=workspace, env=env)
    assert result.returncode == 0
    assert {item["id"] for item in result.data["adopted"]} == {"skills/alpha"}
    skipped = {item["name"] for item in result.data["skipped"]}
    assert skipped == {"container", "wrapped"}


def test_bulk_adopt_skips_unsafe_and_keeps_the_rest(run_cli, workspace, target_home, env) -> None:
    """命中的那一个被跳过，其余照常收编。"""
    make_skill(target_home, "alpha")
    bad = make_skill(target_home, "bad")
    (bad / "SKILL.md").write_text("x‎y", encoding="utf-8")
    result = run_cli("--json", "add", "--from", "claude-code:*", workspace=workspace, env=env)
    assert result.returncode == 0, result.stderr
    assert {item["id"] for item in result.data["adopted"]} == {"skills/alpha"}
    assert result.data["unsafe"] == ["bad"]


def test_single_adopt_still_blocks_on_unsafe(run_cli, workspace, target_home, env) -> None:
    """单个收编命中隐藏 Unicode → 整体中止（退出码 6）。"""
    bad = make_skill(target_home, "bad")
    (bad / "SKILL.md").write_text("x‎y", encoding="utf-8")
    result = run_cli("--json", "add", "--from", "claude-code:bad", workspace=workspace, env=env)
    assert result.returncode == 6
    assert result.json["error"]["code"] == "UNSAFE_CONTENT"


def test_adopted_asset_records_its_source(run_cli, workspace, target_home, env) -> None:
    make_skill(target_home, "alpha")
    assert (
        run_cli("add", "--from", "claude-code:alpha", workspace=workspace, env=env).returncode == 0
    )
    manifest = (workspace / "assets" / "skills" / "alpha" / "capability.yaml").read_text(
        encoding="utf-8"
    )
    assert "target: claude-code" in manifest
    assert "name: alpha" in manifest


def test_list_shows_the_source(run_cli, workspace, target_home, env) -> None:
    make_skill(target_home, "alpha")
    run_cli("add", "--from", "claude-code:alpha", workspace=workspace, env=env)

    listed = run_cli("--json", "list", workspace=workspace, env=env)
    assert listed.data["assets"][0]["source"]["target"] == "claude-code"

    text = run_cli("list", workspace=workspace, env=env).stdout
    assert "Claude Code" in text


def test_local_assets_are_marked_local(run_cli, workspace, tmp_path) -> None:
    source = tmp_path / "src" / "mine"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: mine\n---\n", encoding="utf-8")
    run_cli("add", "skill", str(source), workspace=workspace)
    listed = run_cli("--json", "list", workspace=workspace)
    assert listed.data["assets"][0]["source"] == {}
    assert "local" in run_cli("list", workspace=workspace).stdout


def test_list_filters_by_source(run_cli, workspace, target_home, env) -> None:
    make_skill(target_home, "alpha")
    run_cli("add", "--from", "claude-code:alpha", workspace=workspace, env=env)
    source = workspace.parent / "src" / "mine"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: mine\n---\n", encoding="utf-8")
    run_cli("add", "skill", str(source), workspace=workspace)

    only_claude = run_cli("--json", "list", "--source", "Claude Code", workspace=workspace)
    assert only_claude.data["count"] == 1
    assert only_claude.data["assets"][0]["id"] == "skills/alpha"

    only_local = run_cli("--json", "list", "--source", "local", workspace=workspace)
    assert only_local.data["count"] == 1
    assert only_local.data["assets"][0]["id"] == "skills/mine"


def test_adopted_hash_is_reproducible(run_cli, workspace, target_home, env) -> None:
    """同一份来源，两次收编得到同一个哈希。"""
    make_skill(target_home, "alpha")
    run_cli("add", "--from", "claude-code:alpha", workspace=workspace, env=env)
    first = run_cli("--json", "list", workspace=workspace).data["assets"][0]["hash"]

    run_cli("add", "--from", "claude-code:alpha", "--force", workspace=workspace, env=env)
    second = run_cli("--json", "list", workspace=workspace).data["assets"][0]["hash"]
    assert first == second


def test_bom_at_file_start_is_not_flagged(tmp_path: Path) -> None:
    """文件开头的 BOM 是正常字节，不是隐藏字符。"""
    from capnest.security.scan import scan_file

    path = tmp_path / "schema.xsd"
    path.write_bytes(b"\xef\xbb\xbf<schema/>")
    assert scan_file(path) == []


def test_bom_inside_a_file_is_flagged(tmp_path: Path) -> None:
    from capnest.security.scan import scan_file

    path = tmp_path / "SKILL.md"
    path.write_text("前面﻿后面\n", encoding="utf-8")
    findings = scan_file(path)
    assert findings
    assert findings[0].category == "zero-width"
