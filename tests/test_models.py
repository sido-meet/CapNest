"""数据模型：camelCase 别名、未知字段、不可变。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from capnest.models import (
    API_VERSION,
    Capability,
    CapabilityProfile,
    CapabilityType,
    DeploymentMode,
    PhaseStatus,
)


def test_capability_accepts_camel_case() -> None:
    manifest = Capability.model_validate(
        {
            "apiVersion": API_VERSION,
            "kind": "Capability",
            "metadata": {"id": "skills/x", "name": "X", "version": "1.0.0"},
            "spec": {"type": "skill", "format": "agentskills.io", "entrypoint": "./SKILL.md"},
        }
    )
    assert manifest.api_version == API_VERSION
    assert manifest.spec.type is CapabilityType.SKILL


def test_capability_keeps_unknown_fields() -> None:
    manifest = Capability.model_validate(
        {
            "apiVersion": API_VERSION,
            "kind": "Capability",
            "metadata": {"id": "skills/x", "name": "X", "version": "1.0.0"},
            "spec": {
                "type": "skill",
                "format": "agentskills.io",
                "entrypoint": "./SKILL.md",
                "dependencies": [{"ref": "skills/y"}],
                "permissions": {"requested": ["database"]},
            },
        }
    )
    assert getattr(manifest.spec, "dependencies") == [{"ref": "skills/y"}]
    assert getattr(manifest.spec, "permissions") == {"requested": ["database"]}


def test_capability_is_frozen() -> None:
    manifest = Capability.model_validate(
        {
            "metadata": {"id": "skills/x", "name": "X", "version": "1.0.0"},
            "spec": {"type": "skill", "format": "agentskills.io", "entrypoint": "./SKILL.md"},
        }
    )
    with pytest.raises(ValidationError):
        manifest.metadata.name = "Y"  # type: ignore[misc]


def test_capability_requires_core_fields() -> None:
    with pytest.raises(ValidationError):
        Capability.model_validate({"metadata": {"id": "skills/x"}})


def test_profile_keeps_components_and_targets() -> None:
    profile = CapabilityProfile.model_validate(
        {
            "apiVersion": API_VERSION,
            "kind": "CapabilityProfile",
            "metadata": {"id": "data-agent", "name": "Data Agent", "version": "1.0.0"},
            "spec": {"components": [{"ref": "skills/sql-analysis"}], "targets": ["mcode"]},
        }
    )
    assert [component.ref for component in profile.spec.components] == ["skills/sql-analysis"]
    assert profile.spec.targets == ["mcode"]


def test_enum_values() -> None:
    assert CapabilityType.MCP_SERVER == "mcp-server"
    assert DeploymentMode.COPY == "copy"
    assert PhaseStatus.NOT_RUN == "not_run"

