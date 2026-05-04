"""Type-aware property get/set marshalling.

Wraps ``EdsGetPropertySize`` / ``EdsGetPropertyData`` / ``EdsSetPropertyData``
so callers can deal in plain Python values (``int``, ``str``, ``datetime``,
``tuple``, etc.) instead of raw byte buffers.
"""

from __future__ import annotations

import ctypes
from ctypes import (
    addressof,
    byref,
    c_char,
    c_double,
    c_float,
    c_int8,
    c_int16,
    c_int32,
    c_int64,
    c_uint8,
    c_uint16,
    c_uint32,
    c_uint64,
    cast,
    create_string_buffer,
    sizeof,
)
from datetime import datetime
from typing import Any

from . import _api
from ._types import (
    EdsFocusInfo,
    EdsPictureStyleDesc,
    EdsPoint,
    EdsPropertyDesc,
    EdsRational,
    EdsRect,
    EdsSize,
    EdsTime,
    EdsUInt32,
)
from .constants import DataType
from .errors import check

# Scalar EdsDataType → (ctypes scalar, python type)
_SCALAR_MAP: dict[int, type] = {
    DataType.Bool: c_int32,
    DataType.Int8: c_int8,
    DataType.UInt8: c_uint8,
    DataType.Int16: c_int16,
    DataType.UInt16: c_uint16,
    DataType.Int32: c_int32,
    DataType.UInt32: c_uint32,
    DataType.Int64: c_int64,
    DataType.UInt64: c_uint64,
    DataType.Float: c_float,
    DataType.Double: c_double,
}

# Array EdsDataType → element ctype
_ARRAY_MAP: dict[int, type] = {
    DataType.Bool_Array: c_int32,
    DataType.Int8_Array: c_int8,
    DataType.UInt8_Array: c_uint8,
    DataType.Int16_Array: c_int16,
    DataType.UInt16_Array: c_uint16,
    DataType.Int32_Array: c_int32,
    DataType.UInt32_Array: c_uint32,
}


def _eds_time_to_datetime(t: EdsTime) -> datetime:
    return datetime(
        t.year, t.month, t.day, t.hour, t.minute, t.second, t.milliseconds * 1000
    )


def _datetime_to_eds_time(dt: datetime) -> EdsTime:
    return EdsTime(
        year=dt.year,
        month=dt.month,
        day=dt.day,
        hour=dt.hour,
        minute=dt.minute,
        second=dt.second,
        milliseconds=dt.microsecond // 1000,
    )


def get_property_size(ref: ctypes.c_void_p, property_id: int, param: int = 0) -> tuple[int, int]:
    """Return ``(data_type, size_bytes)`` for the given property."""
    data_type = EdsUInt32(0)
    size = EdsUInt32(0)
    check(
        _api.EdsGetPropertySize(ref, property_id, param, byref(data_type), byref(size)),
        "EdsGetPropertySize",
    )
    return int(data_type.value), int(size.value)


def get_property(ref: ctypes.c_void_p, property_id: int, param: int = 0) -> Any:
    """Read a property and decode it into a Python value.

    Returns:
        - ``int`` for integer scalar types
        - ``float`` for Float / Double
        - ``bool`` for Bool
        - ``str`` for String
        - ``bytes`` for ByteBlock
        - ``datetime`` for Time
        - ``tuple[int, int]`` (point), ``tuple[int, int, int, int]`` (rect),
          or ``tuple[int, int]`` (rational)
        - ``list[int]`` for integer array types
        - ``dict`` for FocusInfo / PictureStyleDesc
    """
    data_type, size = get_property_size(ref, property_id, param)
    return _decode(ref, property_id, param, data_type, size)


def _decode(
    ref: ctypes.c_void_p, property_id: int, param: int, data_type: int, size: int
) -> Any:
    if data_type == DataType.String:
        buf = create_string_buffer(size if size > 0 else 1)
        check(
            _api.EdsGetPropertyData(ref, property_id, param, size, buf),
            "EdsGetPropertyData",
        )
        return buf.value.decode("utf-8", errors="replace")

    if data_type == DataType.ByteBlock:
        buf = (c_char * size)()
        check(
            _api.EdsGetPropertyData(ref, property_id, param, size, buf),
            "EdsGetPropertyData",
        )
        return bytes(buf)

    if data_type in _SCALAR_MAP:
        ctype = _SCALAR_MAP[data_type]
        value = ctype()
        check(
            _api.EdsGetPropertyData(ref, property_id, param, size, byref(value)),
            "EdsGetPropertyData",
        )
        v = value.value
        if data_type == DataType.Bool:
            return bool(v)
        return v

    if data_type == DataType.Time:
        t = EdsTime()
        check(
            _api.EdsGetPropertyData(ref, property_id, param, size, byref(t)),
            "EdsGetPropertyData",
        )
        return _eds_time_to_datetime(t)

    if data_type == DataType.Rational:
        r = EdsRational()
        check(
            _api.EdsGetPropertyData(ref, property_id, param, size, byref(r)),
            "EdsGetPropertyData",
        )
        return (int(r.numerator), int(r.denominator))

    if data_type == DataType.Point:
        p = EdsPoint()
        check(
            _api.EdsGetPropertyData(ref, property_id, param, size, byref(p)),
            "EdsGetPropertyData",
        )
        return (int(p.x), int(p.y))

    if data_type == DataType.Rect:
        rect = EdsRect()
        check(
            _api.EdsGetPropertyData(ref, property_id, param, size, byref(rect)),
            "EdsGetPropertyData",
        )
        return (
            int(rect.point.x),
            int(rect.point.y),
            int(rect.size.width),
            int(rect.size.height),
        )

    if data_type in _ARRAY_MAP:
        element_ctype = _ARRAY_MAP[data_type]
        element_size = sizeof(element_ctype)
        n = size // element_size
        arr = (element_ctype * n)()
        check(
            _api.EdsGetPropertyData(ref, property_id, param, size, arr),
            "EdsGetPropertyData",
        )
        return [int(x) for x in arr]

    if data_type == DataType.FocusInfo:
        info = EdsFocusInfo()
        check(
            _api.EdsGetPropertyData(ref, property_id, param, size, byref(info)),
            "EdsGetPropertyData",
        )
        points = []
        for i in range(info.pointNumber):
            fp = info.focusPoint[i]
            points.append(
                {
                    "valid": int(fp.valid),
                    "selected": int(fp.selected),
                    "justFocus": int(fp.justFocus),
                    "rect": (
                        int(fp.rect.point.x),
                        int(fp.rect.point.y),
                        int(fp.rect.size.width),
                        int(fp.rect.size.height),
                    ),
                }
            )
        return {
            "imageRect": (
                int(info.imageRect.point.x),
                int(info.imageRect.point.y),
                int(info.imageRect.size.width),
                int(info.imageRect.size.height),
            ),
            "pointNumber": int(info.pointNumber),
            "focusPoints": points,
            "executeMode": int(info.executeMode),
        }

    if data_type == DataType.PictureStyleDesc:
        desc = EdsPictureStyleDesc()
        check(
            _api.EdsGetPropertyData(ref, property_id, param, size, byref(desc)),
            "EdsGetPropertyData",
        )
        return {
            "contrast": int(desc.contrast),
            "sharpness": int(desc.sharpness),
            "saturation": int(desc.saturation),
            "colorTone": int(desc.colorTone),
            "filterEffect": int(desc.filterEffect),
            "toningEffect": int(desc.toningEffect),
            "sharpFineness": int(desc.sharpFineness),
            "sharpThreshold": int(desc.sharpThreshold),
        }

    raise NotImplementedError(
        f"Unsupported EdsDataType {data_type} for property 0x{property_id:08X}"
    )


def set_property(
    ref: ctypes.c_void_p, property_id: int, value: Any, param: int = 0
) -> None:
    """Write a Python value to a camera/image property.

    The data type is inferred from ``EdsGetPropertySize`` and ``value`` is
    converted accordingly.
    """
    data_type, size = get_property_size(ref, property_id, param)

    if data_type == DataType.String:
        encoded = str(value).encode("utf-8")
        buf = create_string_buffer(encoded, size if size > 0 else len(encoded) + 1)
        check(
            _api.EdsSetPropertyData(ref, property_id, param, size, buf),
            "EdsSetPropertyData",
        )
        return

    if data_type == DataType.ByteBlock:
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise TypeError("ByteBlock requires bytes-like value")
        data = bytes(value)
        if len(data) != size:
            raise ValueError(f"ByteBlock value must be exactly {size} bytes")
        buf = (c_char * size).from_buffer_copy(data)
        check(
            _api.EdsSetPropertyData(ref, property_id, param, size, buf),
            "EdsSetPropertyData",
        )
        return

    if data_type in _SCALAR_MAP:
        ctype = _SCALAR_MAP[data_type]
        v = ctype(int(value) if data_type != DataType.Bool else int(bool(value)))
        if data_type in (DataType.Float, DataType.Double):
            v = ctype(float(value))
        check(
            _api.EdsSetPropertyData(ref, property_id, param, size, byref(v)),
            "EdsSetPropertyData",
        )
        return

    if data_type == DataType.Time:
        if not isinstance(value, datetime):
            raise TypeError("Time property requires a datetime value")
        t = _datetime_to_eds_time(value)
        check(
            _api.EdsSetPropertyData(ref, property_id, param, size, byref(t)),
            "EdsSetPropertyData",
        )
        return

    if data_type == DataType.Rational:
        num, den = value
        r = EdsRational(numerator=int(num), denominator=int(den))
        check(
            _api.EdsSetPropertyData(ref, property_id, param, size, byref(r)),
            "EdsSetPropertyData",
        )
        return

    if data_type == DataType.Point:
        x, y = value
        p = EdsPoint(x=int(x), y=int(y))
        check(
            _api.EdsSetPropertyData(ref, property_id, param, size, byref(p)),
            "EdsSetPropertyData",
        )
        return

    if data_type == DataType.Rect:
        x, y, w, h = value
        rect = EdsRect(
            point=EdsPoint(x=int(x), y=int(y)),
            size=EdsSize(width=int(w), height=int(h)),
        )
        check(
            _api.EdsSetPropertyData(ref, property_id, param, size, byref(rect)),
            "EdsSetPropertyData",
        )
        return

    if data_type in _ARRAY_MAP:
        element_ctype = _ARRAY_MAP[data_type]
        element_size = sizeof(element_ctype)
        seq = list(value)
        if len(seq) * element_size != size:
            raise ValueError(
                f"Array property requires exactly {size // element_size} elements"
            )
        arr = (element_ctype * len(seq))(*[element_ctype(int(x)).value for x in seq])
        check(
            _api.EdsSetPropertyData(ref, property_id, param, size, arr),
            "EdsSetPropertyData",
        )
        return

    if data_type == DataType.PictureStyleDesc:
        if not isinstance(value, dict):
            raise TypeError("PictureStyleDesc requires a dict")
        desc = EdsPictureStyleDesc(**{k: int(v) for k, v in value.items()})
        check(
            _api.EdsSetPropertyData(ref, property_id, param, size, byref(desc)),
            "EdsSetPropertyData",
        )
        return

    raise NotImplementedError(
        f"Unsupported EdsDataType {data_type} for property 0x{property_id:08X}"
    )


def get_property_desc(ref: ctypes.c_void_p, property_id: int) -> dict[str, Any]:
    """Return the allowed values descriptor for a shooting-related property."""
    desc = EdsPropertyDesc()
    check(_api.EdsGetPropertyDesc(ref, property_id, byref(desc)), "EdsGetPropertyDesc")
    return {
        "form": int(desc.form),
        "access": int(desc.access),
        "values": [int(desc.propDesc[i]) for i in range(desc.numElements)],
    }


# Suppress an unused-import warning while keeping the helpers available for
# callers that want raw addresses (e.g. zero-copy live-view buffers).
__all__ = [
    "addressof",
    "cast",
    "get_property",
    "get_property_desc",
    "get_property_size",
    "set_property",
]
