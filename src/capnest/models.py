"""数据模型：Manifest 的唯一校验来源。

规则（见 [003 Architecture](../../docs/003-architecture.md)）：

- Pydantic v2，统一 camelCase 别名；
- **允许未知字段**（forward compatible）；
- **不可变**（领域对象一旦成立就不该被改）。

第一刀只实现闭环必需的字段：资产级 Manifest 不含 `dependencies` / `permissions` /
`deployment`；Profile 保留 `components` 与 `targets`，但不约束 `components[].version`。
这些字段在文档里仍然合法——`extra="allow"` 让它们被原样保留而不是报错。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

#: Manifest 格式版本。v1 发布前定稿，之后变更即属破坏性变更。
API_VERSION = "io.capnest.capability/v1alpha1"


class Base(BaseModel):
    """所有 Manifest 的共同基类。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="allow",
        frozen=True,
    )


class CapabilityType(StrEnum):
    """资产类型。"""

    SKILL = "skill"
    MCP_SERVER = "mcp-server"
    WORKFLOW = "workflow"


class DeploymentMode(StrEnum):
    """部署形态。"""

    COPY = "copy"
    SYMLINK = "symlink"


class PhaseStatus(StrEnum):
    """部署阶段状态。"""

    NOT_RUN = "not_run"
    APPLIED = "applied"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"
    FAILED = "failed"


class CapabilityMetadata(Base):
    """资产的元数据。"""

    id: str
    name: str
    version: str
    description: str | None = None


class CapabilitySpec(Base):
    """资产的规格。"""

    type: CapabilityType
    format: str
    entrypoint: str


class Capability(Base):
    """一个具体资产：自己是什么、入口是什么。"""

    api_version: str = API_VERSION
    kind: str = "Capability"
    metadata: CapabilityMetadata
    spec: CapabilitySpec


class ProfileComponent(Base):
    """Profile 引用的一个资产。"""

    ref: str


class ProfileSpec(Base):
    """Profile 的规格。"""

    components: list[ProfileComponent] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)


class CapabilityProfile(Base):
    """能力组合，也是部署的单位。"""

    api_version: str = API_VERSION
    kind: str = "CapabilityProfile"
    metadata: CapabilityMetadata
    spec: ProfileSpec


class ResolvedComponent(Base):
    """Lockfile 里解析出来的一个资产。"""

    ref: str
    version: str
    hash: str
    source: str = "local"


class LockSpec(Base):
    """Lockfile 的规格。"""

    resolved: list[ResolvedComponent] = Field(default_factory=list)


class CapabilityLock(Base):
    """依赖解析结果。"""

    api_version: str = API_VERSION
    kind: str = "CapabilityLock"
    metadata: CapabilityMetadata
    spec: LockSpec


#: 三种 `kind` 的合法取值。
MANIFEST_KINDS: tuple[str, ...] = ("Capability", "CapabilityProfile", "CapabilityLock")
