"""Generate ``src/edsdk/constants/_generated.py`` from ``EDSDKTypes.h``.

The output is a pure mechanical transcription of the public API symbols
declared in the EDSDK header (PropID values, command IDs, enum members).
These values are facts about the EDSDK contract, not creative expression —
the generation script and its output are original work of this project.

Usage::

    python tools/gen_constants.py path/to/EDSDKTypes.h \
        > src/edsdk/constants/_generated.py

The script handles two header conventions:

1. ``#define`` groups: e.g. ``#define kEdsPropID_ProductName 0x00000002``.
   All members sharing a ``kEds<Group>_`` prefix become ``IntEnum`` members
   of one ``IntEnum`` named ``<Group>`` (with ``PropID`` rather than
   ``PropertyID``).

2. ``typedef enum { kEds<Group>_Member = value, ... } EdsName;``: members
   are extracted, the longest common prefix is stripped from each member
   name, and the result is exposed under ``IntEnum`` named ``EdsName``
   with the leading ``Eds`` removed.

Reserved Python words and identifiers starting with a digit are guarded by
prefixing with ``_``.
"""

from __future__ import annotations

import argparse
import keyword
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from os import linesep
from pathlib import Path

# ``PropID`` is the canonical Python name; the C prefix is ``kEdsPropID_``.
# Other ``#define`` groups keep the same name they have in the header.
DEFINE_GROUP_RENAMES: dict[str, str] = {
    "PropID": "PropID",
    "CameraCommand": "CameraCommand",
    "CameraStatusCommand": "CameraStatusCommand",
    "ObjectEvent": "ObjectEvent",
    "PropertyEvent": "PropertyEvent",
    "StateEvent": "StateEvent",
}


@dataclass
class EnumDef:
    name: str
    members: list[tuple[str, int]]


_DEFINE_RE = re.compile(
    r"""^\s*\#define\s+
        kEds(?P<group>[A-Za-z0-9]+)_(?P<member>[A-Za-z0-9_]+)
        \s+(?P<value>0[xX][0-9A-Fa-f]+L?|-?\d+L?)
    """,
    re.VERBOSE,
)


def parse_int(literal: str) -> int:
    s = literal.rstrip("Ll")
    if s.lower().startswith("0x"):
        return int(s, 16)
    return int(s, 10)


def parse_defines(source: str) -> list[EnumDef]:
    """Group ``#define kEds<Group>_<Member> <value>`` lines by ``<Group>``."""
    groups: dict[str, list[tuple[str, int]]] = {}
    for line in source.splitlines():
        m = _DEFINE_RE.match(line)
        if not m:
            continue
        group = m.group("group")
        if group not in DEFINE_GROUP_RENAMES:
            continue
        member = m.group("member")
        value = parse_int(m.group("value"))
        groups.setdefault(DEFINE_GROUP_RENAMES[group], []).append((member, value))
    return [EnumDef(name, members) for name, members in groups.items()]


_TYPEDEF_ENUM_OPEN_RE = re.compile(r"^\s*typedef\s+enum\b")
_TYPEDEF_ENUM_CLOSE_RE = re.compile(r"^\s*\}\s*(?P<name>[A-Za-z_][A-Za-z_0-9]*)\s*;\s*$")
_ENUM_MEMBER_RE = re.compile(
    r"""^\s*
        (?P<name>[A-Za-z_][A-Za-z_0-9]*)
        \s*(?:=\s*(?P<value>[^,/]+?))?
        \s*,?\s*(?://.*)?$
    """,
    re.VERBOSE,
)


def parse_typedef_enums(source: str) -> list[EnumDef]:
    """Walk ``typedef enum { ... } EdsName;`` blocks and extract members.

    Members without an explicit value receive ``previous + 1`` (C semantics).
    The first unannotated member starts at zero.
    """
    out: list[EnumDef] = []
    lines = source.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        if _TYPEDEF_ENUM_OPEN_RE.match(lines[i]):
            # Advance to the opening brace if it's on a later line.
            j = i
            while j < n and "{" not in lines[j]:
                j += 1
            if j == n:
                i += 1
                continue
            # Read members until we see a line that closes with `} Name;`.
            buf: list[str] = []
            j += 1
            while j < n:
                close = _TYPEDEF_ENUM_CLOSE_RE.match(lines[j])
                if close:
                    members = _interpret_members(buf)
                    if members:
                        out.append(EnumDef(close.group("name"), members))
                    i = j + 1
                    break
                buf.append(lines[j])
                j += 1
            else:
                # Unterminated typedef enum — bail.
                i = j
        else:
            i += 1
    return out


def _interpret_members(body_lines: Iterable[str]) -> list[tuple[str, int]]:
    members: list[tuple[str, int]] = []
    last_value: int = -1
    # Collapse the body to logical statements split by commas.
    text = " ".join(_strip_comments(ln) for ln in body_lines)
    for raw in text.split(","):
        stmt = raw.strip()
        if not stmt:
            continue
        m = _ENUM_MEMBER_RE.match(stmt + ",")  # tail comma to keep the regex happy
        if not m:
            continue
        name = m.group("name")
        if not name:
            continue
        raw_value = m.group("value")
        if raw_value is None:
            value = last_value + 1
        else:
            value = _eval_enum_value(raw_value.strip(), members)
        members.append((name, value))
        last_value = value
    return members


def _strip_comments(line: str) -> str:
    # Remove trailing // comments and /* ... */ on a single line.
    line = re.sub(r"/\*.*?\*/", "", line)
    line = re.sub(r"//.*", "", line)
    return line


def _eval_enum_value(expr: str, prior: list[tuple[str, int]]) -> int:
    """Evaluate a tiny subset of C constant expressions.

    Supports integer literals (decimal / hex / with ``L`` suffix), references
    to earlier members in the same enum, and the bitwise ``|`` / ``&`` /
    ``<<`` / ``>>`` / ``+`` / ``-`` operators via Python ``eval`` over a
    sanitised symbol table.
    """
    expr = expr.strip().rstrip("Ll")
    # Replace 0xFFFFFFFFL etc.
    expr = re.sub(r"(0[xX][0-9A-Fa-f]+)L", r"\1", expr)
    # Reference resolution: any bare identifier is looked up in ``prior``.
    symbols = {name: value for name, value in prior}
    safe = re.compile(r"^[\sA-Za-z0-9_+\-|&^()<>x*/]+$")
    if not safe.match(expr):
        raise ValueError(f"Refusing to evaluate enum expression: {expr!r}")
    try:
        return int(eval(expr, {"__builtins__": {}}, symbols))  # noqa: S307
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Could not evaluate enum value {expr!r}: {e}") from e


def _longest_common_prefix(words: list[str]) -> str:
    if not words:
        return ""
    short = min(words, key=len)
    for i, ch in enumerate(short):
        for w in words:
            if w[i] != ch:
                return short[:i]
    return short


def _strip_common_prefix(name: str, members: list[tuple[str, int]]) -> str:
    """Drop ``Eds`` prefix from typedef name and the largest common prefix
    from members. Falls back to truncating up to the last underscore in the
    common prefix to preserve readability.
    """
    if name.startswith("Eds"):
        name = name[3:]
    return name


def _normalise_member_names(
    members: list[tuple[str, int]],
    type_name: str | None = None,
) -> list[tuple[str, int]]:
    if len(members) <= 1:
        return _sanitise(members)

    names = [m for m, _ in members]

    # Prefer stripping the typedef name itself when it appears as a prefix
    # in every member (case-insensitively). Header convention varies — some
    # families use `kEds<Type>_<Member>`, others use `k<Type><Member>`
    # without an underscore.
    if type_name:
        bare_type = type_name.removeprefix("Eds")
        type_lower = bare_type.lower()
        if all(type_lower in m.lower() for m in names):
            stripped = []
            for m in names:
                idx = m.lower().rfind(type_lower)
                stripped.append(m[idx + len(bare_type):].lstrip("_"))
            if all(stripped) and len(set(stripped)) == len(stripped):
                values = [v for _, v in members]
                return _sanitise(list(zip(stripped, values, strict=True)))

    # Fall back to longest common prefix, truncated at the last underscore
    # so we never split a token mid-word.
    prefix = _longest_common_prefix(names)
    if "_" in prefix:
        prefix = prefix[: prefix.rfind("_") + 1]
    elif prefix:
        prefix = ""
    return _sanitise([(m[len(prefix):] or m, v) for m, v in members])


def _sanitise(members: list[tuple[str, int]]) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for name, value in members:
        clean = name
        if clean[:1].isdigit():
            clean = "_" + clean
        if keyword.iskeyword(clean):
            clean = clean + "_"
        out.append((clean, value))
    return out


def _format_value(v: int) -> str:
    if v < 0:
        return str(v)
    return f"0x{v:08X}"


def _emit(enum_defs: list[EnumDef], header_path: Path) -> str:
    lines: list[str] = []
    lines.append('"""Auto-generated EDSDK constants.')
    lines.append("")
    lines.append("Generated by ``tools/gen_constants.py`` from")
    lines.append(f"``{header_path.name}``. Do not edit by hand — re-run the")
    lines.append("generator instead.")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from enum import IntEnum")
    lines.append("")
    lines.append("")

    # Stable order: define groups first (in the order in DEFINE_GROUP_RENAMES),
    # then typedef-enum groups alphabetically.
    define_keys = list(DEFINE_GROUP_RENAMES.values())
    define_defs = sorted(
        (d for d in enum_defs if d.name in define_keys),
        key=lambda d: define_keys.index(d.name),
    )
    enum_defs_only = sorted(
        (d for d in enum_defs if d.name not in define_keys),
        key=lambda d: d.name,
    )

    for enum in [*define_defs, *enum_defs_only]:
        py_name = (
            enum.name
            if enum.name in define_keys
            else _strip_common_prefix(enum.name, enum.members)
        )
        normalised_members = (
            enum.members
            if enum.name in define_keys
            else _normalise_member_names(enum.members, enum.name)
        )
        seen: set[str] = set()
        unique_members: list[tuple[str, int]] = []
        for name, value in normalised_members:
            if name in seen:
                continue
            seen.add(name)
            unique_members.append((name, value))
        if not unique_members:
            continue
        lines.append(f"class {py_name}(IntEnum):")
        for member_name, value in unique_members:
            lines.append(f"    {member_name} = {_format_value(value)}")
        lines.append("")
        lines.append("")

    # Build __all__ for re-export ergonomics.
    all_names = [
        enum.name if enum.name in define_keys else _strip_common_prefix(enum.name, enum.members)
        for enum in [*define_defs, *enum_defs_only]
    ]
    lines.append("__all__ = [")
    for name in sorted(all_names):
        lines.append(f'    "{name}",')
    lines.append("]")
    lines.append("")

    return linesep.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument(
        "header",
        type=Path,
        help="Path to EDSDKTypes.h from the Canon EDSDK distribution.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (defaults to stdout).",
    )
    args = parser.parse_args(argv)

    if not args.header.exists():
        print(f"error: {args.header} does not exist", file=sys.stderr)
        return 2

    source = args.header.read_text(encoding="utf-8", errors="replace")
    enum_defs = parse_defines(source) + parse_typedef_enums(source)
    rendered = _emit(enum_defs, args.header)

    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output} ({len(rendered)} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
