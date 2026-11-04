"""共享测试夹具。

约定：所有测试都在临时目录里跑，**绝不碰用户的真实 Agent 配置**。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass
class CliResult:
    """一次 CLI 调用的结果。"""

    returncode: int
    stdout: str
    stderr: str

    @property
    def json(self) -> dict:
        """把 stdout 当作 JSON envelope 解析。"""
        return json.loads(self.stdout)

    @property
    def data(self) -> dict:
        return self.json["data"]


@pytest.fixture
def run_cli(tmp_path: Path):
    """在指定工作区里跑一次真实 CLI（子进程），返回退出码与输出。

    **默认隔离**：两个目标的 home 永远指向临时目录，
    任何测试都不可能写到用户真实的 `~/.minimax` 或 `~/.claude`。
    需要换目标时用 `env=` 显式覆盖。
    """

    def _run(
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        workspace: Path | None = None,
    ) -> CliResult:
        environ = dict(os.environ)
        environ.pop("CAPNEST_HOME", None)
        # 子进程固定用 UTF-8 输出，避免受本机控制台代码页影响。
        environ["PYTHONIOENCODING"] = "utf-8"
        # 目标 home 一律重定向到临时目录——这是最后一道保险。
        for key in list(environ):
            if key.startswith("CAPNEST_TARGET_HOME_"):
                environ.pop(key)
        isolated = tmp_path / "isolated-targets"
        environ["CAPNEST_TARGET_HOME_MCODE"] = str(isolated / "mcode")
        environ["CAPNEST_TARGET_HOME_CLAUDE_CODE"] = str(isolated / "claude-code")
        if env:
            environ.update(env)
        argv = [sys.executable, "-m", "capnest"]
        if workspace is not None:
            argv += ["--workspace", str(workspace)]
        argv += list(args)
        completed = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            env=environ,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return CliResult(completed.returncode, completed.stdout, completed.stderr)

    return _run


@pytest.fixture
def target_homes(tmp_path: Path) -> dict[str, Path]:
    """两个目标的假 home，隔离真实环境。"""
    homes = {
        "mcode": tmp_path / "target-home-mcode",
        "claude-code": tmp_path / "target-home-claude-code",
    }
    for home in homes.values():
        home.mkdir(parents=True, exist_ok=True)
    return homes


@pytest.fixture
def sandbox_env(target_homes: dict[str, Path]) -> dict[str, str]:
    """把两个目标指向临时目录的环境变量。"""
    return {
        "CAPNEST_TARGET_HOME_MCODE": str(target_homes["mcode"]),
        "CAPNEST_TARGET_HOME_CLAUDE_CODE": str(target_homes["claude-code"]),
    }
