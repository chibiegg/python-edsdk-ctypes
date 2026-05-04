"""ctypes-level type aliases and structures mirroring EDSDKTypes.h."""

from __future__ import annotations

import ctypes
from ctypes import (
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
    c_void_p,
)

EDS_MAX_NAME = 256

# Scalar aliases
EdsBool = c_int32
EdsChar = c_char
EdsInt8 = c_int8
EdsUInt8 = c_uint8
EdsInt16 = c_int16
EdsUInt16 = c_uint16
EdsInt32 = c_int32
EdsUInt32 = c_uint32
EdsInt64 = c_int64
EdsUInt64 = c_uint64
EdsFloat = c_float
EdsDouble = c_double

# Opaque handle types — all are void* under the hood.
EdsBaseRef = c_void_p
EdsCameraListRef = c_void_p
EdsCameraRef = c_void_p
EdsVolumeRef = c_void_p
EdsDirectoryItemRef = c_void_p
EdsStreamRef = c_void_p
EdsImageRef = c_void_p
EdsEvfImageRef = c_void_p

EdsError = c_uint32


class EdsPoint(ctypes.Structure):
    _fields_ = [("x", EdsInt32), ("y", EdsInt32)]


class EdsSize(ctypes.Structure):
    _fields_ = [("width", EdsInt32), ("height", EdsInt32)]


class EdsRect(ctypes.Structure):
    _fields_ = [("point", EdsPoint), ("size", EdsSize)]


class EdsRational(ctypes.Structure):
    _fields_ = [("numerator", EdsInt32), ("denominator", EdsUInt32)]


class EdsTime(ctypes.Structure):
    _fields_ = [
        ("year", EdsUInt32),
        ("month", EdsUInt32),
        ("day", EdsUInt32),
        ("hour", EdsUInt32),
        ("minute", EdsUInt32),
        ("second", EdsUInt32),
        ("milliseconds", EdsUInt32),
    ]


class EdsDeviceInfo(ctypes.Structure):
    _fields_ = [
        ("szPortName", EdsChar * EDS_MAX_NAME),
        ("szDeviceDescription", EdsChar * EDS_MAX_NAME),
        ("deviceSubType", EdsUInt32),
        ("reserved", EdsUInt32),
    ]


class EdsImageInfo(ctypes.Structure):
    _fields_ = [
        ("width", EdsUInt32),
        ("height", EdsUInt32),
        ("numOfComponents", EdsUInt32),
        ("componentDepth", EdsUInt32),
        ("effectiveRect", EdsRect),
        ("reserved1", EdsUInt32),
        ("reserved2", EdsUInt32),
    ]


class EdsDirectoryItemInfo(ctypes.Structure):
    _fields_ = [
        ("size", EdsUInt64),
        ("isFolder", EdsBool),
        ("groupID", EdsUInt32),
        ("option", EdsUInt32),
        ("szFileName", EdsChar * EDS_MAX_NAME),
        ("format", EdsUInt32),
        ("dateTime", EdsUInt32),
    ]


class EdsCapacity(ctypes.Structure):
    _fields_ = [
        ("numberOfFreeClusters", EdsInt32),
        ("bytesPerSector", EdsInt32),
        ("reset", EdsBool),
    ]


class EdsPropertyDesc(ctypes.Structure):
    _fields_ = [
        ("form", EdsInt32),
        ("access", EdsInt32),
        ("numElements", EdsInt32),
        ("propDesc", EdsInt32 * 128),
    ]


class EdsFocusPoint(ctypes.Structure):
    _fields_ = [
        ("valid", EdsUInt32),
        ("selected", EdsUInt32),
        ("justFocus", EdsUInt32),
        ("rect", EdsRect),
        ("reserved", EdsUInt32),
    ]


class EdsFocusInfo(ctypes.Structure):
    _fields_ = [
        ("imageRect", EdsRect),
        ("pointNumber", EdsUInt32),
        ("focusPoint", EdsFocusPoint * 1053),
        ("executeMode", EdsUInt32),
    ]


class EdsPictureStyleDesc(ctypes.Structure):
    _fields_ = [
        ("contrast", EdsInt32),
        ("sharpness", EdsUInt32),
        ("saturation", EdsInt32),
        ("colorTone", EdsInt32),
        ("filterEffect", EdsUInt32),
        ("toningEffect", EdsUInt32),
        ("sharpFineness", EdsUInt32),
        ("sharpThreshold", EdsUInt32),
    ]
