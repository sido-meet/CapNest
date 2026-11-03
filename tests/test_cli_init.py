"""`capnest init` 的行为。"""

from __future__ import annotations

import json
from pathlib import Path


def test_init_creates_layout(run_cli, tmp_path: Path):
    workspace = tmp_path / "ws"
    result = run_cli("--json", "init", str(workspace))
    assert result.returncode == 0
    payload = result.json
    assert payload["ok"] is True
    assert payload["command"] == "init"
    assert (workspace / "config.yaml").is_file()
    assert (workspace / "assets" / "skills").is_dir()
    assert (workspace / "assets" / "mcp").is_dir()
    assert (workspace / "assets" / "workflows").is_dir()
    assert (workspace / "profiles").is_dir()
    assert (workspace / "state" / "backups").is_dir()
    assert (workspace / "state" / "logs").is_dir()
    assert json.loads((workspace / "state" / "deployments.json").read_text()) == []
    assert json.loads((workspace / "state" / "ownership.json").read_text()) == {}


def test_init_refuses_existing_workspace(run_cli, tmp_path: Path):
    workspace = tmp_path / "ws"
    assert run_cli("init", str(workspace)).returncode == 0
    result = run_cli("--json", "init", str(workspace))
    assert result.returncode == 7
    assert result.json["error"]["code"] == "CONFLICT"


def test_init_force_overwrites(run_cli, tmp_path: Path):
    workspace = tmp_path / "ws"
    assert run_cli("init", str(workspace)).returncode == 0
    result = run_cli("--json", "init", str(workspace), "--force")
    assert result.returncode == 0


def test_init_writes_targets(run_cli, tmp_path: Path):
    workspace = tmp_path / "ws"
    run_cli("init", str(workspace))
    text = (workspace / "config.yaml").read_text(encoding="utf-8")
    assert "mcode" in text
    assert "claude-code" in text
