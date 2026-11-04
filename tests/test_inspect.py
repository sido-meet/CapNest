"""`capnest inspect`：目标侧盘点。"""

from __future__ import annotations

from pathlib import Path

import pytest


def make_skill(home: Path, name: str, *, manifest: bool = True, nested: bool = False) -> Path:
    directory = home / "skills" / name
    directory.mkdir(parents=True, exist_ok=True)
    if manifest:
        (directory / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
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
    """把 Claude Code 的 home 指向临时目录。"""
    return {"CAPNEST_TARGET_HOME_CLAUDE_CODE": str(target_home)}


def test_inspect_lists_target_skills(run_cli, target_home, env) -> None:
    make_skill(target_home, "alpha")
    make_skill(target_home, "beta")
    result = run_cli("--json", "inspect", "claude-code", env=env)
    assert result.returncode == 0, result.stderr
    assert result.data["count"] == 2
    assert {item["name"] for item in result.data["skills"]} == {"alpha", "beta"}
    assert result.data["skills_path"].endswith("skills")


def test_inspect_marks_state(run_cli, target_home, env) -> None:
    make_skill(target_home, "plain")
    make_skill(target_home, "container", manifest=False)
    make_skill(target_home, "wrapped", nested=True)
    result = run_cli("--json", "inspect", "claude-code", env=env)
    states = {item["name"]: item["state"] for item in result.data["skills"]}
    assert states["plain"] == "unmanaged"
    assert states["container"] == "container"
    assert states["wrapped"] == "nested"


def test_inspect_is_read_only(run_cli, target_home, env) -> None:
    make_skill(target_home, "alpha")
    before = sorted(
        (path.relative_to(target_home).as_posix(), path.stat().st_mtime_ns)
        for path in target_home.rglob("*")
    )
    result = run_cli("--json", "inspect", "claude-code", env=env)
    assert result.returncode == 0
    after = sorted(
        (path.relative_to(target_home).as_posix(), path.stat().st_mtime_ns)
        for path in target_home.rglob("*")
    )
    assert before == after


def test_inspect_unknown_target_exits_8(run_cli) -> None:
    result = run_cli("--json", "inspect", "codex")
    assert result.returncode == 8
    assert result.json["error"]["code"] == "NOT_FOUND"


def test_inspect_reports_managed_skills(run_cli, tmp_path, target_home, env) -> None:
    """CapNest 已经管着的 skill 标成 managed。"""
    workspace = tmp_path / "ws"
    assert run_cli("init", str(workspace)).returncode == 0
    source = tmp_path / "src" / "alpha"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: alpha\n---\n", encoding="utf-8")
    assert run_cli("add", "skill", str(source), workspace=workspace).returncode == 0
    assert (
        run_cli(
            "profile",
            "create",
            "p",
            "--asset",
            "skills/alpha",
            "--target",
            "claude-code",
            workspace=workspace,
        ).returncode
        == 0
    )
    assert (
        run_cli(
            "apply",
            "--profile",
            "p",
            "--target",
            "claude-code",
            "--yes",
            workspace=workspace,
            env=env,
        ).returncode
        == 0
    )
    result = run_cli("--json", "inspect", "claude-code", workspace=workspace, env=env)
    states = {item["name"]: item["state"] for item in result.data["skills"]}
    assert states["alpha"] == "managed"
