"""High-level entry points: SDK lifetime and camera enumeration."""

from __future__ import annotations

from ctypes import byref, c_void_p
from types import TracebackType

from . import _api
from ._types import EdsCameraListRef, EdsUInt32
from .camera import Camera
from .errors import check


class SDK:
    """Context manager wrapping ``EdsInitializeSDK`` / ``EdsTerminateSDK``.

    Example:
        >>> with edsdk.SDK():
        ...     for cam in edsdk.list_cameras():
        ...         print(cam.device_info())
    """

    def __init__(self) -> None:
        self._initialized = False

    def __enter__(self) -> SDK:
        check(_api.EdsInitializeSDK(), "EdsInitializeSDK")
        self._initialized = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._initialized:
            self._initialized = False
            check(_api.EdsTerminateSDK(), "EdsTerminateSDK")


def initialize() -> None:
    """Initialize the SDK (manual lifecycle; prefer :class:`SDK`)."""
    check(_api.EdsInitializeSDK(), "EdsInitializeSDK")


def terminate() -> None:
    """Terminate the SDK (manual lifecycle; prefer :class:`SDK`)."""
    check(_api.EdsTerminateSDK(), "EdsTerminateSDK")


def get_event() -> None:
    """Pump one queued SDK event.

    Required on Linux/macOS console apps to deliver registered callbacks.
    Call this periodically (e.g. from a background thread) while a session
    is open.
    """
    check(_api.EdsGetEvent(), "EdsGetEvent")


def list_cameras() -> list[Camera]:
    """Enumerate currently attached cameras.

    The returned :class:`Camera` instances own their refs and release them
    on garbage-collection.
    """
    cam_list = EdsCameraListRef()
    check(_api.EdsGetCameraList(byref(cam_list)), "EdsGetCameraList")
    try:
        count = EdsUInt32(0)
        check(_api.EdsGetChildCount(cam_list, byref(count)), "EdsGetChildCount")
        cameras: list[Camera] = []
        for i in range(count.value):
            cam_ref = c_void_p()
            check(
                _api.EdsGetChildAtIndex(cam_list, i, byref(cam_ref)),
                "EdsGetChildAtIndex",
            )
            cameras.append(Camera(cam_ref))
        return cameras
    finally:
        _api.EdsRelease(cam_list)
