"""异常体系：每个异常对应一个错误码与一个进程退出码。

错误码与退出码是同一份表：`error.code` 的字符串即 `docs/006-cli.md` 里的名字，
`exit_code` 即进程退出码，方便脚本只用退出码判断。
"""

from __future__ import annotations

from typing import Any


class CapNestError(Exception):
    """所有 CapNest 异常的基类。"""

    code: str = "ERROR"
    exit_code: int = 1

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class UsageError(CapNestError):
    """命令行用法错误。"""

    code = "USAGE"
    exit_code = 2


class ValidationFailed(CapNestError):
    """校验不通过。"""

    code = "VALIDATION_FAILED"
    exit_code = 3


class DriftDetected(CapNestError):
    """目标配置与 CapNest 记录不一致。"""

    code = "DRIFT_DETECTED"
    exit_code = 4


class ConfirmationRequired(CapNestError):
    """存在破坏性变更但未确认。"""

    code = "CONFIRMATION_REQUIRED"
    exit_code = 5


class UnsafeContent(CapNestError):
    """隐藏 Unicode 扫描命中。"""

    code = "UNSAFE_CONTENT"
    exit_code = 6


class Conflict(CapNestError):
    """目标冲突或归属证明失败。"""

    code = "CONFLICT"
    exit_code = 7


class NotFound(CapNestError):
    """资产、Profile 或部署记录不存在。"""

    code = "NOT_FOUND"
    exit_code = 8


#: 退出码 → 异常类，供文档与测试引用。
EXIT_CODES: dict[int, type[CapNestError]] = {
    1: CapNestError,
    2: UsageError,
    3: ValidationFailed,
    4: DriftDetected,
    5: ConfirmationRequired,
    6: UnsafeContent,
    7: Conflict,
    8: NotFound,
}
