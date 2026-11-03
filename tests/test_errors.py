"""错误码与退出码的对应关系。"""

from __future__ import annotations

import pytest

from capnest.errors import (
    EXIT_CODES,
    CapNestError,
    ConfirmationRequired,
    Conflict,
    DriftDetected,
    NotFound,
    UnsafeContent,
    UsageError,
    ValidationFailed,
)


@pytest.mark.parametrize(
    ("exc_type", "code", "exit_code"),
    [
        (CapNestError, "ERROR", 1),
        (UsageError, "USAGE", 2),
        (ValidationFailed, "VALIDATION_FAILED", 3),
        (DriftDetected, "DRIFT_DETECTED", 4),
        (ConfirmationRequired, "CONFIRMATION_REQUIRED", 5),
        (UnsafeContent, "UNSAFE_CONTENT", 6),
        (Conflict, "CONFLICT", 7),
        (NotFound, "NOT_FOUND", 8),
    ],
)
def test_error_code_and_exit_code(exc_type, code, exit_code):
    error = exc_type("出错了")
    assert error.code == code
    assert error.exit_code == exit_code
    assert EXIT_CODES[exit_code] is exc_type


def test_details_default_to_empty_dict():
    assert CapNestError("x").details == {}
    assert CapNestError("x", {"path": "p"}).details == {"path": "p"}


def test_message_is_kept():
    error = CapNestError("目标路径已存在")
    assert error.message == "目标路径已存在"
    assert str(error) == "目标路径已存在"
