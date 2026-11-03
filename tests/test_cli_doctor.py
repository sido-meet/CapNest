"""`capnest doctor` 的行为。"""

from __future__ import annotations

from pathlib import Path


def test_doctor_reports_checks(run_cli, tmp_path: Path):
    workspace = tmp_path / "ws"
    run_cli("init", str(workspace))
    result = run_cli("--workspace", str(workspace), "--json", "doctor")
    assert result.returncode == 0
    payload = result.json
    assert payload["ok"] is True
    names = {check["name"] for check in payload["data"]["checks"]}
    assert "python_version" in names
    assert "workspace.config" in names
    assert "capabilities" in payload["data"]


def test_doctor_warns_when_workspace_missing(run_cli, tmp_path: Path):
    result = run_cli("--workspace", str(tmp_path / "nope"), "--json", "doctor")
    assert result.returncode == 1
    statuses = {check["name"]: check["status"] for check in result.json["data"]["checks"]}
    assert statuses["workspace"] == "fail"


def test_doctor_uses_overridden_target_homes(run_cli, tmp_path: Path, sandbox_env):
    workspace = tmp_path / "ws"
    run_cli("init", str(workspace))
    result = run_cli("--workspace", str(workspace), "--json", "doctor", env=sandbox_env)
    details = " ".join(check["detail"] for check in result.json["data"]["checks"])
    assert str(tmp_path) in details
