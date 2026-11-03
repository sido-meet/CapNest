"""第一刀的端到端验收：docs/010 §7 的六条断言。"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


def snapshot(root: Path) -> dict[str, bytes]:
    """目录树的逐字节快照。"""
    if not root.exists():
        return {}
    found: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_file():
            found[relative] = path.read_bytes()
        elif path.is_dir():
            found[relative + "/"] = b""
    return found


def dir_hash(root: Path) -> str:
    """目录树的内容哈希（与 hashing.hash_dir 同一套规则）。"""
    from capnest.hashing import hash_dir

    return hash_dir(root) if root.is_dir() else ""


@pytest.fixture
def workspace(tmp_path: Path, run_cli) -> Path:
    path = tmp_path / "ws"
    result = run_cli("init", str(path))
    assert result.returncode == 0, result.stderr
    return path


@pytest.fixture
def deployed(tmp_path: Path, run_cli, workspace: Path, sandbox_env) -> dict:
    """装好资产、建好 Profile，但**不部署**。"""
    source = tmp_path / "src" / "sql-analysis"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: sql-analysis\ndescription: 演示\n---\n\n正文\n",
        encoding="utf-8",
    )
    added = run_cli(
        "--json",
        "add",
        "skill",
        str(source),
        workspace=workspace,
        env=sandbox_env,
    )
    assert added.returncode == 0, added.stderr
    profile = run_cli(
        "--json",
        "profile",
        "create",
        "data-agent",
        "--asset",
        "skills/sql-analysis",
        "--target",
        "mcode",
        "--target",
        "claude-code",
        workspace=workspace,
        env=sandbox_env,
    )
    assert profile.returncode == 0, profile.stderr
    return {"workspace": workspace, "env": sandbox_env, "source": source}


def _skills(home: Path) -> Path:
    return home / "skills"


def test_assertion_1_plan_writes_nothing(deployed, run_cli, target_homes) -> None:
    """plan 之后两个 Agent 的 skills 目录与执行前逐字节一致。"""
    before = {name: snapshot(_skills(home)) for name, home in target_homes.items()}
    result = run_cli(
        "--json",
        "plan",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    assert result.returncode == 0, result.stderr
    after = {name: snapshot(_skills(home)) for name, home in target_homes.items()}
    assert before == after


def test_assertion_2_apply_makes_both_sides_identical(deployed, run_cli, target_homes) -> None:
    """apply 之后两个 Agent 都有该 skill，内容哈希与 assets/ 中一致。"""
    result = run_cli(
        "--json",
        "apply",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        "--yes",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    assert result.returncode == 0, result.stderr

    asset_dir = deployed["workspace"] / "assets" / "skills" / "sql-analysis"
    expected = dir_hash(asset_dir)
    for home in target_homes.values():
        deployed_dir = _skills(home) / "sql-analysis"
        assert deployed_dir.is_dir()
        assert dir_hash(deployed_dir) == expected

    mcode_hash = dir_hash(_skills(target_homes["mcode"]) / "sql-analysis")
    claude_hash = dir_hash(_skills(target_homes["claude-code"]) / "sql-analysis")
    assert mcode_hash == claude_hash


def test_assertion_3_unmanaged_path_is_refused(deployed, run_cli, target_homes) -> None:
    """目标上已存在同名、且不由 CapNest 管理的目录 → 退出码 7，不覆盖。"""
    intruder = _skills(target_homes["mcode"]) / "sql-analysis"
    intruder.mkdir(parents=True)
    (intruder / "SKILL.md").write_text("别人的东西\n", encoding="utf-8")
    before = snapshot(intruder)

    result = run_cli(
        "--json",
        "apply",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        "--yes",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    assert result.returncode == 7
    assert result.json["error"]["code"] == "CONFLICT"
    assert snapshot(intruder) == before


def test_assertion_4_repeated_apply_is_idempotent(deployed, run_cli, target_homes) -> None:
    """重复 apply → 退出码 0，文件 mtime 不变。"""
    first = run_cli(
        "--json",
        "apply",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        "--yes",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    assert first.returncode == 0, first.stderr

    deployed_file = _skills(target_homes["mcode"]) / "sql-analysis" / "SKILL.md"
    before = deployed_file.stat().st_mtime_ns
    content = deployed_file.read_bytes()

    second = run_cli(
        "--json",
        "apply",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        "--yes",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    assert second.returncode == 0, second.stderr
    assert deployed_file.stat().st_mtime_ns == before
    assert deployed_file.read_bytes() == content


def test_assertion_5_rollback_restores_the_initial_state(deployed, run_cli, target_homes) -> None:
    """rollback 之后目标目录回到初始状态（逐字节）。"""
    before = {name: snapshot(_skills(home)) for name, home in target_homes.items()}

    applied = run_cli(
        "--json",
        "apply",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        "--yes",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    assert applied.returncode == 0, applied.stderr

    for target in ("mcode", "claude-code"):
        result = run_cli(
            "--json",
            "rollback",
            "--target",
            target,
            workspace=deployed["workspace"],
            env=deployed["env"],
        )
        assert result.returncode == 0, result.stderr

    after = {name: snapshot(_skills(home)) for name, home in target_homes.items()}
    assert before == after


def test_assertion_6_failure_leaves_no_half_product(deployed, run_cli, target_homes) -> None:
    """任一步失败都不留下半成品。"""
    intruder = _skills(target_homes["claude-code"]) / "sql-analysis"
    intruder.mkdir(parents=True)
    (intruder / "SKILL.md").write_text("别人的东西\n", encoding="utf-8")

    result = run_cli(
        "--json",
        "apply",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        "--yes",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    assert result.returncode == 7
    # mcode 侧也必须干净——不能只写了一半。
    assert not (_skills(target_homes["mcode"]) / "sql-analysis").exists()


def test_apply_without_yes_requires_confirmation(deployed, run_cli, target_homes) -> None:
    """有写入但没给 --yes → 退出码 5。"""
    result = run_cli(
        "--json",
        "apply",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    assert result.returncode == 5
    assert result.json["error"]["code"] == "CONFIRMATION_REQUIRED"


def test_status_reports_up_to_date(deployed, run_cli) -> None:
    run_cli(
        "apply",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        "--yes",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    result = run_cli(
        "--json",
        "status",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    assert result.returncode == 0, result.stderr
    states = {row["target"]: row["status"] for row in result.data["targets"]}
    assert states == {"mcode": "up-to-date", "claude-code": "up-to-date"}


def test_dry_run_writes_nothing(deployed, run_cli, target_homes) -> None:
    before = {name: snapshot(_skills(home)) for name, home in target_homes.items()}
    result = run_cli(
        "--json",
        "apply",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        "--dry-run",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    assert result.returncode == 0, result.stderr
    after = {name: snapshot(_skills(home)) for name, home in target_homes.items()}
    assert before == after


def test_asset_change_is_reported_as_version_lag(deployed, run_cli, target_homes) -> None:
    """资产改了 → status 报 version-lag。"""
    run_cli(
        "apply",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        "--yes",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    asset_file = deployed["workspace"] / "assets" / "skills" / "sql-analysis" / "SKILL.md"
    asset_file.write_text(
        "---\nname: sql-analysis\ndescription: 演示\n---\n\n改过的正文\n",
        encoding="utf-8",
    )
    result = run_cli(
        "--json",
        "status",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    states = {row["target"]: row["status"] for row in result.data["targets"]}
    assert states == {"mcode": "version-lag", "claude-code": "version-lag"}


def test_external_change_is_reported_as_drift(deployed, run_cli, target_homes) -> None:
    """目标侧被外部改了 → status 报 drift。"""
    run_cli(
        "apply",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        "--yes",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    target_file = _skills(target_homes["mcode"]) / "sql-analysis" / "SKILL.md"
    target_file.write_text("被改过了\n", encoding="utf-8")
    result = run_cli(
        "--json",
        "status",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    states = {row["target"]: row["status"] for row in result.data["targets"]}
    assert states["mcode"] == "drift"


def test_deployed_files_match_the_workspace(deployed, run_cli, target_homes) -> None:
    """部署后的内容与工作区资产逐文件一致。"""
    run_cli(
        "apply",
        "--profile",
        "data-agent",
        "--target",
        "mcode,claude-code",
        "--yes",
        workspace=deployed["workspace"],
        env=deployed["env"],
    )
    asset_dir = deployed["workspace"] / "assets" / "skills" / "sql-analysis"
    for home in target_homes.values():
        deployed_dir = _skills(home) / "sql-analysis"
        for path in asset_dir.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(asset_dir)
            target_file = deployed_dir / relative
            assert target_file.is_file()
            assert (
                hashlib.sha256(target_file.read_bytes()).digest()
                == hashlib.sha256(path.read_bytes()).digest()
            )
