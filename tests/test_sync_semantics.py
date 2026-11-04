"""真实用法：改工作区 → 两边同步（不是冲突）。"""

from __future__ import annotations

from pathlib import Path

import pytest


def make_skill(home: Path, name: str, *, body: str = "正文\n") -> Path:
    directory = home / "skills" / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(f"---\nname: {name}\n---\n\n{body}", encoding="utf-8")
    return directory


@pytest.fixture
def workspace(tmp_path: Path, run_cli) -> Path:
    path = tmp_path / "ws"
    assert run_cli("init", str(path)).returncode == 0
    return path


def test_editing_the_workspace_syncs_to_both_targets(
    run_cli, workspace, target_homes, sandbox_env
) -> None:
    """改工作区里的资产 → 正常同步，**不是**冲突。"""
    make_skill(target_homes["claude-code"], "docx")
    assert (
        run_cli("add", "--from", "claude-code:*", workspace=workspace, env=sandbox_env).returncode
        == 0
    )
    first = run_cli("--json", "sync", "--yes", workspace=workspace, env=sandbox_env)
    assert first.returncode == 0, first.stderr

    skill_md = workspace / "assets" / "skills" / "docx" / "SKILL.md"
    skill_md.write_text("---\nname: docx\n---\n\n改过的正文\n", encoding="utf-8")

    result = run_cli("--json", "sync", "--yes", workspace=workspace, env=sandbox_env)
    assert result.returncode == 0, result.stdout
    assert result.data["conflicts"] == []

    for home in target_homes.values():
        body = (home / "skills" / "docx" / "SKILL.md").read_text(encoding="utf-8")
        assert "改过的正文" in body


def test_external_edit_of_target_is_reported_as_drift(
    run_cli, workspace, target_homes, sandbox_env
) -> None:
    """目标侧被人手工改过 → 报漂移，拒绝覆盖。"""
    make_skill(target_homes["claude-code"], "docx")
    run_cli("add", "--from", "claude-code:*", workspace=workspace, env=sandbox_env)
    run_cli("sync", "--yes", workspace=workspace, env=sandbox_env)

    target_skill = target_homes["claude-code"] / "skills" / "docx" / "SKILL.md"
    target_skill.write_text("---\nname: docx\n---\n\n外部改的\n", encoding="utf-8")

    listed = run_cli("--json", "conflict", "list", workspace=workspace, env=sandbox_env)
    assert listed.data["count"] == 1
    assert listed.data["conflicts"][0]["kind"] == "drift"

    result = run_cli("--json", "sync", "--yes", workspace=workspace, env=sandbox_env)
    assert result.returncode == 7, result.stdout
    # 外部的修改没被覆盖。
    assert "外部改的" in target_skill.read_text(encoding="utf-8")
