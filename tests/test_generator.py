"""Smoke tests for the constants generator.

We don't ship the EDSDK header in the repo, so these tests use a tiny
inline header snippet to exercise both ``#define`` and ``typedef enum``
parsing paths.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import gen_constants  # type: ignore[import-not-found]  # noqa: E402

SAMPLE_HEADER = """
#define kEdsPropID_ProductName       0x00000002
#define kEdsPropID_OwnerName         0x00000004
#define kEdsObjectEvent_All          0x00000200
#define kEdsObjectEvent_DirItemRequestTransfer 0x00000208
#define kEdsCameraCommand_TakePicture 0x00000000

typedef enum
{
    kEdsDataType_Unknown   = 0,
    kEdsDataType_Bool      = 1,
    kEdsDataType_String    = 2,
} EdsDataType;

typedef enum
{
    kEdsSaveTo_Camera = 1,
    kEdsSaveTo_Host   = 2,
    kEdsSaveTo_Both   = kEdsSaveTo_Camera | kEdsSaveTo_Host,
} EdsSaveTo;
"""


def _parse(source: str) -> dict[str, dict[str, int]]:
    enum_defs = gen_constants.parse_defines(source) + gen_constants.parse_typedef_enums(source)
    out: dict[str, dict[str, int]] = {}
    for enum in enum_defs:
        if enum.name in gen_constants.DEFINE_GROUP_RENAMES:
            py_name = gen_constants.DEFINE_GROUP_RENAMES[enum.name]
            members = enum.members
        else:
            py_name = gen_constants._strip_common_prefix(enum.name, enum.members)
            members = gen_constants._normalise_member_names(enum.members, enum.name)
        out[py_name] = dict(members)
    return out


def test_define_groups_recognised() -> None:
    parsed = _parse(SAMPLE_HEADER)
    assert parsed["PropID"]["ProductName"] == 0x2
    assert parsed["PropID"]["OwnerName"] == 0x4
    assert parsed["ObjectEvent"]["DirItemRequestTransfer"] == 0x208
    assert parsed["CameraCommand"]["TakePicture"] == 0


def test_typedef_enum_with_implicit_values() -> None:
    parsed = _parse(SAMPLE_HEADER)
    assert parsed["DataType"] == {"Unknown": 0, "Bool": 1, "String": 2}


def test_typedef_enum_with_bitwise_expression() -> None:
    parsed = _parse(SAMPLE_HEADER)
    assert parsed["SaveTo"] == {"Camera": 1, "Host": 2, "Both": 3}


def test_emit_round_trip_is_executable_python() -> None:
    enum_defs = gen_constants.parse_defines(SAMPLE_HEADER) + gen_constants.parse_typedef_enums(
        SAMPLE_HEADER
    )
    rendered = gen_constants._emit(enum_defs, Path("EDSDKTypes.h"))
    namespace: dict[str, object] = {}
    exec(compile(rendered, "<generated>", "exec"), namespace)
    assert namespace["PropID"].ProductName == 0x2  # type: ignore[attr-defined]
    assert namespace["SaveTo"].Both == 3  # type: ignore[attr-defined]


def test_unknown_define_groups_are_ignored() -> None:
    src = "#define kEdsCustomPrefix_Foo 0x10\n"
    parsed = _parse(src)
    assert parsed == {}


def test_refuses_unsafe_expressions() -> None:
    # `'os'` contains characters outside the safelist (quotes, single
    # letters), so the evaluator must refuse it.
    with pytest.raises(ValueError, match="Refusing"):
        gen_constants._eval_enum_value("__import__('os')", [])
