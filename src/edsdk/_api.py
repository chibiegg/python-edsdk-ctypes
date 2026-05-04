"""Bound EDSDK function prototypes.

Functions are looked up lazily on first attribute access via PEP 562 module
``__getattr__``, so importing this module — or anything that re-exports it,
including ``edsdk`` itself — does not require the shared library to be
present. The loader is only invoked when a real call is made.
"""

from __future__ import annotations

from ctypes import CFUNCTYPE, POINTER, c_char_p, c_void_p
from typing import Any

from ._loader import load_edsdk
from ._types import (
    EdsBaseRef,
    EdsCameraListRef,
    EdsCameraRef,
    EdsCapacity,
    EdsDeviceInfo,
    EdsDirectoryItemInfo,
    EdsDirectoryItemRef,
    EdsError,
    EdsEvfImageRef,
    EdsImageInfo,
    EdsImageRef,
    EdsInt32,
    EdsPropertyDesc,
    EdsStreamRef,
    EdsUInt32,
    EdsUInt64,
)

# Callback function pointer types (CFUNCTYPE applies the C calling convention).
# All EDSDK callbacks return EdsError (uint32).
EdsObjectEventHandler = CFUNCTYPE(EdsUInt32, EdsUInt32, c_void_p, c_void_p)
EdsPropertyEventHandler = CFUNCTYPE(EdsUInt32, EdsUInt32, EdsUInt32, EdsUInt32, c_void_p)
EdsStateEventHandler = CFUNCTYPE(EdsUInt32, EdsUInt32, EdsUInt32, c_void_p)
EdsCameraAddedHandler = CFUNCTYPE(EdsUInt32, c_void_p)
EdsProgressCallback = CFUNCTYPE(EdsUInt32, EdsUInt32, c_void_p, POINTER(EdsUInt32))

# Map of public name → (argtypes, restype). The shared library is loaded
# the first time one of these is dereferenced.
_PROTOTYPES: dict[str, tuple[list[Any], Any]] = {
    "EdsInitializeSDK": ([], EdsError),
    "EdsTerminateSDK": ([], EdsError),
    "EdsGetEvent": ([], EdsError),
    "EdsRetain": ([EdsBaseRef], EdsUInt32),
    "EdsRelease": ([EdsBaseRef], EdsUInt32),
    "EdsGetChildCount": ([EdsBaseRef, POINTER(EdsUInt32)], EdsError),
    "EdsGetChildAtIndex": ([EdsBaseRef, EdsInt32, POINTER(c_void_p)], EdsError),
    "EdsGetParent": ([EdsBaseRef, POINTER(c_void_p)], EdsError),
    "EdsGetCameraList": ([POINTER(EdsCameraListRef)], EdsError),
    "EdsGetDeviceInfo": ([EdsCameraRef, POINTER(EdsDeviceInfo)], EdsError),
    "EdsOpenSession": ([EdsCameraRef], EdsError),
    "EdsCloseSession": ([EdsCameraRef], EdsError),
    # Property operations
    "EdsGetPropertySize": (
        [EdsBaseRef, EdsUInt32, EdsInt32, POINTER(EdsUInt32), POINTER(EdsUInt32)],
        EdsError,
    ),
    "EdsGetPropertyData": (
        [EdsBaseRef, EdsUInt32, EdsInt32, EdsUInt32, c_void_p],
        EdsError,
    ),
    "EdsSetPropertyData": (
        [EdsBaseRef, EdsUInt32, EdsInt32, EdsUInt32, c_void_p],
        EdsError,
    ),
    "EdsGetPropertyDesc": (
        [EdsBaseRef, EdsUInt32, POINTER(EdsPropertyDesc)],
        EdsError,
    ),
    # Camera commands
    "EdsSendCommand": ([EdsCameraRef, EdsUInt32, EdsInt32], EdsError),
    "EdsSendStatusCommand": ([EdsCameraRef, EdsUInt32, EdsInt32], EdsError),
    "EdsSetCapacity": ([EdsCameraRef, EdsCapacity], EdsError),
    # Directory item / download
    "EdsGetDirectoryItemInfo": (
        [EdsDirectoryItemRef, POINTER(EdsDirectoryItemInfo)],
        EdsError,
    ),
    "EdsDeleteDirectoryItem": ([EdsDirectoryItemRef], EdsError),
    "EdsDownload": ([EdsDirectoryItemRef, EdsUInt64, EdsStreamRef], EdsError),
    "EdsDownloadComplete": ([EdsDirectoryItemRef], EdsError),
    "EdsDownloadCancel": ([EdsDirectoryItemRef], EdsError),
    "EdsDownloadThumbnail": ([EdsDirectoryItemRef, EdsStreamRef], EdsError),
    # Stream operations
    "EdsCreateFileStream": (
        [c_char_p, EdsUInt32, EdsUInt32, POINTER(EdsStreamRef)],
        EdsError,
    ),
    "EdsCreateMemoryStream": ([EdsUInt64, POINTER(EdsStreamRef)], EdsError),
    "EdsCreateMemoryStreamFromPointer": (
        [c_void_p, EdsUInt64, POINTER(EdsStreamRef)],
        EdsError,
    ),
    "EdsGetPointer": ([EdsStreamRef, POINTER(c_void_p)], EdsError),
    "EdsGetLength": ([EdsStreamRef, POINTER(EdsUInt64)], EdsError),
    "EdsGetPosition": ([EdsStreamRef, POINTER(EdsUInt64)], EdsError),
    "EdsCopyData": ([EdsStreamRef, EdsUInt64, c_void_p], EdsError),
    # Image operations
    "EdsCreateImageRef": ([EdsStreamRef, POINTER(EdsImageRef)], EdsError),
    "EdsGetImageInfo": (
        [EdsImageRef, EdsUInt32, POINTER(EdsImageInfo)],
        EdsError,
    ),
    # Live view (Evf)
    "EdsCreateEvfImageRef": ([EdsStreamRef, POINTER(EdsEvfImageRef)], EdsError),
    "EdsDownloadEvfImage": ([EdsCameraRef, EdsEvfImageRef], EdsError),
    # Event handler registration
    "EdsSetCameraAddedHandler": ([EdsCameraAddedHandler, c_void_p], EdsError),
    "EdsSetPropertyEventHandler": (
        [EdsCameraRef, EdsUInt32, EdsPropertyEventHandler, c_void_p],
        EdsError,
    ),
    "EdsSetObjectEventHandler": (
        [EdsCameraRef, EdsUInt32, EdsObjectEventHandler, c_void_p],
        EdsError,
    ),
    "EdsSetCameraStateEventHandler": (
        [EdsCameraRef, EdsUInt32, EdsStateEventHandler, c_void_p],
        EdsError,
    ),
}

_cache: dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    if name in _cache:
        return _cache[name]
    if name not in _PROTOTYPES:
        raise AttributeError(name)
    argtypes, restype = _PROTOTYPES[name]
    fn = getattr(load_edsdk(), name)
    fn.argtypes = argtypes
    fn.restype = restype
    _cache[name] = fn
    return fn
