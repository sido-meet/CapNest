"""资产仓库：扫描、导入、收编。

资产是**目录**，不是单个文件——哈希、diff、拷贝规则因此完全一致。
仓库里的一切都以 `assets/` 下的目录为准，`capability.yaml` 是它们的说明书。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from capnest.config import default_target_paths
from capnest.errors import Conflict, NotFound, ValidationFailed
from capnest.hashing import hash_dir
from capnest.models import API_VERSION, Capability, CapabilityType, SourceInfo
from capnest.security.scan import scan_tree
from capnest.store.workspace import Workspace
from capnest.util.fs import copy_tree, remove_tree

#: `add` 的 kind 参数 → `assets/` 下的目录名。
KIND_TO_FAMILY: dict[str, str] = {
    "skill": "skills",
    "mcp": "mcp",
    "workflow": "workflows",
}

#: `assets/` 下的目录名 → `spec.type`。
FAMILY_TO_TYPE: dict[str, CapabilityType] = {
    "skills": CapabilityType.SKILL,
    "mcp": CapabilityType.MCP_SERVER,
    "workflows": CapabilityType.WORKFLOW,
}

#: 生成 manifest 时各类型的默认 `spec.format`。
DEFAULT_FORMAT: dict[str, str] = {
    "skill": "agentskills.io",
    "mcp": "mcp.local-config",
    "workflow": "io.capnest.workflow/v1alpha1",
}

#: 生成 manifest 时各类型的首选入口文件名。
DEFAULT_ENTRYPOINT: dict[str, str] = {
    "skill": "SKILL.md",
    "mcp": "server.json",
    "workflow": "workflow.yaml",
}

#: 入口文件的候选后缀（首选文件不存在时按顺序找）。
ENTRYPOINT_SUFFIXES: tuple[str, ...] = (".md", ".json", ".yaml", ".yml")

MANIFEST_FILENAME = "capability.yaml"


def content_hash(path: Path) -> str:
    """目录的**内容**哈希：忽略 `capability.yaml`。

    判断「是不是同一份能力」时只看实际内容——manifest 是 CapNest 的说明书，
    不是能力本身。工作区那份多了 manifest，目标侧那份没有，
    比内容时必须把它排除掉，否则同一份能力永远「不一样」。
    """
    return hash_dir(path, exclude_files=(MANIFEST_FILENAME,))


@dataclass(frozen=True)
class AssetRecord:
    """一个已登记的资产。"""

    asset_id: str
    kind: CapabilityType
    path: Path
    manifest: Capability
    hash: str

    @property
    def name(self) -> str:
        return self.manifest.metadata.name

    @property
    def version(self) -> str:
        return self.manifest.metadata.version

    @property
    def description(self) -> str | None:
        return self.manifest.metadata.description

    @property
    def format(self) -> str:
        return self.manifest.spec.format

    @property
    def source(self) -> SourceInfo | None:
        """资产从哪来。None 表示本地创建。"""
        return self.manifest.metadata.source

    @property
    def sources(self) -> list[SourceInfo]:
        """资产在哪些 Agent 侧出现过。同一份能力两边都有时会有多条。"""
        sources = list(self.manifest.metadata.sources)
        if not sources and self.manifest.metadata.source is not None:
            sources.append(self.manifest.metadata.source)
        return sources

    @property
    def entrypoint(self) -> str:
        return self.manifest.spec.entrypoint

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.asset_id,
            "type": str(self.kind),
            "name": self.name,
            "version": self.version,
            "description": self.description or "",
            "format": self.format,
            "entrypoint": self.entrypoint,
            "hash": self.hash,
            "path": str(self.path),
            "source": (
                {
                    "target": self.source.target,
                    "name": self.source.name or "",
                    "adoptedAt": self.source.adopted_at or "",
                }
                if self.source is not None
                else {}
            ),
            "sources": [
                {
                    "target": item.target,
                    "name": item.name or "",
                    "adoptedAt": item.adopted_at or "",
                }
                for item in self.sources
            ],
        }


def read_manifest(path: Path) -> Capability:
    """读取并校验 `capability.yaml`。"""
    if not path.is_file():
        raise ValidationFailed(
            f"缺少 {MANIFEST_FILENAME}",
            {"path": str(path)},
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationFailed(
            f"{MANIFEST_FILENAME} 不是合法的 YAML",
            {"path": str(path), "reason": str(exc)},
        ) from None
    if not isinstance(raw, dict):
        raise ValidationFailed(
            f"{MANIFEST_FILENAME} 的顶层必须是映射",
            {"path": str(path)},
        )
    try:
        return Capability.model_validate(raw)
    except Exception as exc:  # pydantic 的校验错误类型不作为对外契约
        raise ValidationFailed(
            f"{MANIFEST_FILENAME} 不符合 Capability 结构",
            {"path": str(path), "reason": str(exc)},
        ) from None


def write_manifest(path: Path, manifest: Capability) -> None:
    """写出 `capability.yaml`。"""
    data = manifest.model_dump(mode="json", by_alias=True, exclude_none=True)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    path.write_text(text, encoding="utf-8")


def _pick_entrypoint(directory: Path, kind: str) -> str:
    """给新资产挑一个入口文件。挑不到就报错，不猜。"""
    preferred = DEFAULT_ENTRYPOINT[kind]
    if (directory / preferred).is_file():
        return f"./{preferred}"
    candidates = sorted(
        item.name
        for item in directory.iterdir()
        if item.is_file() and item.suffix.lower() in ENTRYPOINT_SUFFIXES
    )
    if not candidates:
        raise ValidationFailed(
            "目录里没有可作为入口的文件",
            {
                "path": str(directory),
                "expected": preferred,
                "suffixes": list(ENTRYPOINT_SUFFIXES),
            },
        )
    return f"./{candidates[0]}"


def build_manifest(kind: str, family: str, name: str, directory: Path) -> Capability:
    """为一个还没有 manifest 的目录生成一份最小 manifest。"""
    return Capability.model_validate(
        {
            "apiVersion": API_VERSION,
            "kind": "Capability",
            "metadata": {
                "id": f"{family}/{name}",
                "name": name,
                "version": "0.1.0",
                "description": "",
            },
            "spec": {
                "type": str(FAMILY_TO_TYPE[family]),
                "format": DEFAULT_FORMAT[kind],
                "entrypoint": _pick_entrypoint(directory, kind),
            },
        }
    )


def assert_safe(directory: Path) -> None:
    """隐藏 Unicode 扫描：命中即阻断。"""
    findings = scan_tree(directory)
    if not findings:
        return
    from capnest.errors import UnsafeContent

    raise UnsafeContent(
        f"检测到 {len(findings)} 处隐藏 Unicode 字符，已阻断",
        {
            "path": str(directory),
            "findings": [finding.to_dict() for finding in findings],
        },
    )


class AssetStore:
    """`assets/` 目录的读写入口。"""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    # ------------------------------------------------------------------ 扫描

    def scan(self) -> list[AssetRecord]:
        """遍历 `assets/`，产出全部合法资产。"""
        records: list[AssetRecord] = []
        for family, kind in FAMILY_TO_TYPE.items():
            directory = self.workspace.asset_dir(family)
            if not directory.is_dir():
                continue
            for item in sorted(directory.iterdir()):
                if not item.is_dir():
                    continue
                manifest_path = item / MANIFEST_FILENAME
                if not manifest_path.is_file():
                    continue
                manifest = read_manifest(manifest_path)
                records.append(
                    AssetRecord(
                        asset_id=f"{family}/{item.name}",
                        kind=kind,
                        path=item,
                        manifest=manifest,
                        hash=hash_dir(item),
                    )
                )
        return records

    def get(self, asset_id: str) -> AssetRecord:
        """按 ID 取一个资产，不存在则报 NOT_FOUND。"""
        for record in self.scan():
            if record.asset_id == asset_id:
                return record
        raise NotFound(f"资产不存在：{asset_id}", {"asset": asset_id})

    def exists(self, asset_id: str) -> bool:
        return any(record.asset_id == asset_id for record in self.scan())

    # ------------------------------------------------------------------ 导入

    def import_path(
        self,
        src: Path,
        kind: str,
        *,
        name: str | None = None,
        force: bool = False,
        source: SourceInfo | None = None,
    ) -> AssetRecord:
        """把一个外部目录导入工作区。**复制而非引用**。"""
        if kind not in KIND_TO_FAMILY:
            raise ValidationFailed(
                f"未知的资产类型：{kind}",
                {"kind": kind, "supported": sorted(KIND_TO_FAMILY)},
            )
        source_dir = src.expanduser().resolve()
        if not source_dir.is_dir():
            raise NotFound(f"源路径不是目录：{source_dir}", {"path": str(source_dir)})

        family = KIND_TO_FAMILY[kind]
        asset_name = name or source_dir.name
        destination = self.workspace.asset_dir(family) / asset_name

        if destination.exists() and not force:
            raise Conflict(
                f"资产已存在：{family}/{asset_name}",
                {"asset": f"{family}/{asset_name}", "path": str(destination)},
            )

        assert_safe(source_dir)

        manifest_path = source_dir / MANIFEST_FILENAME
        if manifest_path.is_file():
            manifest = read_manifest(manifest_path)
            entry = (source_dir / manifest.spec.entrypoint.lstrip("./")).resolve()
            if not entry.is_file():
                raise ValidationFailed(
                    "manifest 的 entrypoint 指向的文件不存在",
                    {
                        "asset": f"{family}/{asset_name}",
                        "entrypoint": manifest.spec.entrypoint,
                    },
                )
        else:
            manifest = build_manifest(kind, family, asset_name, source_dir)

        if source is not None:
            manifest = manifest.model_copy(
                update={
                    "metadata": manifest.metadata.model_copy(
                        update={"source": source, "sources": [source]},
                    )
                }
            )

        if destination.exists():
            remove_tree(destination)
        copy_tree(source_dir, destination)
        write_manifest(destination / MANIFEST_FILENAME, manifest)

        return AssetRecord(
            asset_id=f"{family}/{asset_name}",
            kind=FAMILY_TO_TYPE[family],
            path=destination,
            manifest=manifest,
            hash=hash_dir(destination),
        )

    # ------------------------------------------------------------------ 收编

    def _find_skill(self, name: str) -> AssetRecord | None:
        """按目录名找工作区里已有的 skill 资产。"""
        for record in self.scan():
            if record.asset_id == f"skills/{name}":
                return record
        return None

    def claim_target_path(self, target: str, name: str) -> None:
        """认领目标侧那个目录。

        收编之后 CapNest 就**管**这份能力了：目标侧那一路径记进归属表，
        指纹就是它现在的内容哈希。没有这条记录，后续 `apply` 会因为
        「路径已存在且不由 CapNest 管理」拒绝写入——同步就永远做不成。
        """
        from capnest.deployment.ownership import OwnershipRegistry

        path = default_target_paths(target).skills_path / name
        if not path.is_dir():
            return
        registry = OwnershipRegistry(self.workspace.ownership_file)
        registry.claim(path, hash_dir(path))
        registry.save()

    def merge_source(self, record: AssetRecord, source: SourceInfo) -> AssetRecord:
        """把一个来源并进资产的 manifest。

        同一份能力在两个 Agent 侧都有时，收编第二次**不该再复制一份**，
        只该把第二个来源记上去。
        """
        manifest = record.manifest
        sources = list(manifest.metadata.sources)
        if not sources and manifest.metadata.source is not None:
            sources.append(manifest.metadata.source)
        if not any(item.target == source.target and item.name == source.name for item in sources):
            sources.append(source)
        updated = manifest.model_copy(
            update={
                "metadata": manifest.metadata.model_copy(
                    update={"source": sources[0], "sources": sources}
                )
            }
        )
        write_manifest(record.path / MANIFEST_FILENAME, updated)
        return AssetRecord(
            asset_id=record.asset_id,
            kind=record.kind,
            path=record.path,
            manifest=updated,
            hash=hash_dir(record.path),
        )

    def adopt_from_target(
        self,
        target: str,
        name: str,
        *,
        force: bool = False,
    ) -> AssetRecord:
        """从某个 Agent 的 skills 目录收编一个既有能力。

        只**读取**源目录——Agent 侧的文件一个字节都不动。

        工作区里已经有同名资产时：

        - 内容相同 → 不复制，只把来源并进去（这就是去重）；
        - 内容不同 → 报冲突（退出码 7），除非 `--force`。
        """
        paths = default_target_paths(target)
        source_dir = paths.skills_path / name
        if not source_dir.is_dir():
            raise NotFound(
                f"{target} 侧没有名为 {name} 的 skill",
                {"target": target, "name": name, "path": str(source_dir)},
            )
        existing = self._find_skill(name)
        if existing is not None and not force:
            if content_hash(existing.path) == content_hash(source_dir):
                merged = self.merge_source(existing, SourceInfo(target=target, name=name))
                self.claim_target_path(target, name)
                return merged
            raise Conflict(
                f"工作区里已有同名资产且内容不同：skills/{name}",
                {
                    "asset": f"skills/{name}",
                    "target": target,
                    "workspaceHash": content_hash(existing.path),
                    "targetHash": content_hash(source_dir),
                },
            )
        record = self.import_path(
            source_dir,
            "skill",
            name=name,
            force=force,
            # 不记时间戳：时间戳会让内容哈希每次都变，
            # 而 CapNest 的哈希必须**可复现**——同一份来源，两次收编得到同一个哈希。
            source=SourceInfo(target=target, name=name),
        )
        self.claim_target_path(target, name)
        return record

    def adopt_candidates(self, target: str) -> tuple[list[str], list[dict[str, str]]]:
        """列出目标侧**可以收编**的 skill 名字，以及被跳过的那些。

        v1 只支持单层 skill 目录：顶层没有 `SKILL.md` 的容器目录、
        以及目录里还套着别的 skill 的，都跳过并说明原因。
        """
        from capnest.adapters import make_adapter

        adapter = make_adapter(target)
        state = adapter.read()
        nested = set(state.nested)
        adoptable: list[str] = []
        skipped: list[dict[str, str]] = []
        for name in sorted(state.skills):
            path = adapter.skill_path(name)
            if name in nested:
                skipped.append({"name": name, "reason": "目录里套着别的 skill，v1 不支持"})
                continue
            if not (path / "SKILL.md").is_file():
                skipped.append({"name": name, "reason": "顶层没有 SKILL.md，是容器目录"})
                continue
            adoptable.append(name)
        return adoptable, skipped

    def adopt_all_from_target(self, target: str, *, force: bool = False) -> dict[str, object]:
        """把目标侧**所有**能收编的 skill 一次性收编进来。

        三步走：

        1. 列出可收编的，跳过容器目录与嵌套目录并说明原因；
        2. 逐个扫描隐藏 Unicode，**命中的那一个被跳过**并记录——
        不因为一份奇怪的文档挡住其余全部；
        3. 逐个收编，单个失败（同名冲突等）只跳过并记录，不影响其余。

        与单个收编的差别：``add --from <target>:<name>`` 命中隐藏 Unicode
        会整体中止（退出码 6），而批量收编只跳过命中的那一个。

        每个候选分四种去向：

        - **adopted**：收编进来；
        - **duplicates**：工作区里已有同名且内容相同的资产——不复制，只并来源；
        - **conflicts**：工作区里已有同名但内容不同的资产——不覆盖，记成冲突；
        - **skipped / failed**：容器目录、嵌套目录、隐藏 Unicode，或导入失败。
        """
        adoptable, skipped = self.adopt_candidates(target)
        paths = default_target_paths(target)

        unsafe: list[str] = []
        for name in adoptable:
            if scan_tree(paths.skills_path / name):
                unsafe.append(name)

        adopted: list[dict[str, object]] = []
        duplicates: list[dict[str, object]] = []
        conflicts: list[dict[str, object]] = []
        failed: list[dict[str, str]] = []
        for name in adoptable:
            if name in unsafe:
                skipped.append({"name": name, "reason": "含隐藏 Unicode 字符，已跳过"})
                continue
            source_dir = paths.skills_path / name
            existing = self._find_skill(name)
            if existing is not None and not force:
                if content_hash(existing.path) == content_hash(source_dir):
                    merged = self.merge_source(existing, SourceInfo(target=target, name=name))
                    self.claim_target_path(target, name)
                    duplicates.append(
                        {
                            "name": name,
                            "id": merged.asset_id,
                            "target": target,
                            "reason": "工作区里已有同一份内容，只并来源",
                        }
                    )
                else:
                    conflicts.append(
                        {
                            "name": name,
                            "id": existing.asset_id,
                            "target": target,
                            "workspaceHash": content_hash(existing.path),
                            "targetHash": content_hash(source_dir),
                            "reason": "同名但内容不同，未覆盖",
                        }
                    )
                continue
            try:
                record = self.adopt_from_target(target, name, force=force)
            except Conflict:
                failed.append({"name": name, "reason": "工作区里已有同名资产"})
                continue
            except ValidationFailed as exc:
                failed.append({"name": name, "reason": exc.message})
                continue
            adopted.append(record.to_dict())

        return {
            "target": target,
            "adopted": adopted,
            "duplicates": duplicates,
            "conflicts": conflicts,
            "skipped": skipped,
            "failed": failed,
            "unsafe": unsafe,
            "count": len(adopted),
        }

    def adopt_all_from_targets(
        self,
        targets: list[str],
        *,
        force: bool = False,
    ) -> dict[str, object]:
        """从多个目标一次性收编。

        每个目标各收各的：同名同内容自动去重，同名不同内容记成冲突，
        一个目标上的冲突不影响另一个目标。
        """
        results = [self.adopt_all_from_target(target, force=force) for target in targets]
        return {
            "targets": list(targets),
            "adopted": [item for result in results for item in result["adopted"]],
            "duplicates": [item for result in results for item in result["duplicates"]],
            "conflicts": [item for result in results for item in result["conflicts"]],
            "skipped": [item for result in results for item in result["skipped"]],
            "failed": [item for result in results for item in result["failed"]],
            "count": sum(int(result["count"]) for result in results),
        }

    # ------------------------------------------------------------------ 查重

    def find_duplicates(self) -> list[dict[str, object]]:
        """**内容相同、名字不同**的资产组。"""
        groups: dict[str, list[AssetRecord]] = {}
        for record in self.scan():
            groups.setdefault(content_hash(record.path), []).append(record)
        duplicates: list[dict[str, object]] = []
        for digest, members in groups.items():
            if len(members) < 2:
                continue
            duplicates.append(
                {
                    "hash": digest,
                    "assets": [item.asset_id for item in members],
                    "names": [item.name for item in members],
                }
            )
        return duplicates

    # ------------------------------------------------------------------ 拉回

    def pull_from_target(
        self,
        asset_id: str,
        target: str,
        name: str,
    ) -> AssetRecord:
        """把目标侧的内容**拉回**工作区。

        这是「以目标为准」的裁决：目标侧那份内容成为工作区里的版本。
        工作区自己的 `capability.yaml` 保留——它是 CapNest 的说明书，
        不是能力内容的一部分。
        """
        from capnest.util.fs import copy_file, copy_tree

        record = self.get(asset_id)
        source_dir = default_target_paths(target).skills_path / name
        if not source_dir.is_dir():
            raise NotFound(
                f"{target} 侧没有名为 {name} 的 skill",
                {"target": target, "name": name, "path": str(source_dir)},
            )
        for item in list(record.path.iterdir()):
            if item.name == MANIFEST_FILENAME:
                continue
            if item.is_dir():
                remove_tree(item)
            else:
                item.unlink()
        for item in source_dir.iterdir():
            if item.name == MANIFEST_FILENAME:
                continue
            destination = record.path / item.name
            if item.is_dir():
                copy_tree(item, destination)
            else:
                copy_file(item, destination)
        return AssetRecord(
            asset_id=record.asset_id,
            kind=record.kind,
            path=record.path,
            manifest=record.manifest,
            hash=hash_dir(record.path),
        )
