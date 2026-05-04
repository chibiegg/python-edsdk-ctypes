"""Event handler registration helpers.

**Threading model.** EDSDK is *not* thread-safe. All SDK calls — including
``EdsGetEvent`` — must happen on the same thread that called
``EdsInitializeSDK``. Mixing threads (e.g. sending ``PressShutterButton``
from the main thread while a background thread polls events) corrupts the
camera state and produces misleading errors such as
``EDS_ERR_DEVICE_NOT_FOUND``.

This module therefore exposes:

- ``set_*_handler`` / ``Camera.on_*_event`` to register callbacks.
- ``pump_events(duration_s)`` and ``wait_until(predicate, timeout_s)`` to
  drive the event loop **from the same thread that owns the SDK**.

Callbacks fire on the thread that calls ``EdsGetEvent``, so when the main
thread drives the loop, callbacks run on the main thread too — safe to
issue further EDSDK calls from inside them.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from ctypes import c_void_p

from . import _api
from ._api import (
    EdsCameraAddedHandler,
    EdsObjectEventHandler,
    EdsPropertyEventHandler,
    EdsStateEventHandler,
)
from .constants import ObjectEvent, PropertyEvent, StateEvent
from .errors import check
from .sdk import get_event

# ``object_handle`` arrives as a ``c_void_p`` for object events that carry one
# (e.g. DirItemRequestTransfer). The handle ownership is transferred to the
# callback — the application is expected to release it via ``EdsRelease`` once
# done. The high-level ``Camera`` API hides this; raw users get it as an int.
ObjectCallback = Callable[[ObjectEvent, int], None]
PropertyCallback = Callable[[PropertyEvent, int, int], None]
StateCallback = Callable[[StateEvent, int], None]
CameraAddedCallback = Callable[[], None]


# Module-level registry to keep callback wrappers alive. Indexed by camera ref
# value (or 0 for the global CameraAdded handler). Each entry is a list to
# permit overlapping registrations.
_keepalive: dict[int, list[object]] = {}


def _register(key: int, wrapper: object) -> None:
    _keepalive.setdefault(key, []).append(wrapper)


def _make_object_handler(callback: ObjectCallback) -> EdsObjectEventHandler:
    def trampoline(event: int, object_handle: int, _ctx: int) -> int:
        try:
            callback(ObjectEvent(event), int(object_handle or 0))
        except Exception:
            import traceback

            traceback.print_exc()
        return 0

    return EdsObjectEventHandler(trampoline)


def _make_property_handler(callback: PropertyCallback) -> EdsPropertyEventHandler:
    def trampoline(event: int, prop: int, param: int, _ctx: int) -> int:
        try:
            callback(PropertyEvent(event), int(prop), int(param))
        except Exception:
            import traceback

            traceback.print_exc()
        return 0

    return EdsPropertyEventHandler(trampoline)


def _make_state_handler(callback: StateCallback) -> EdsStateEventHandler:
    def trampoline(event: int, param: int, _ctx: int) -> int:
        try:
            callback(StateEvent(event), int(param))
        except Exception:
            import traceback

            traceback.print_exc()
        return 0

    return EdsStateEventHandler(trampoline)


def _make_added_handler(callback: CameraAddedCallback) -> EdsCameraAddedHandler:
    def trampoline(_ctx: int) -> int:
        try:
            callback()
        except Exception:
            import traceback

            traceback.print_exc()
        return 0

    return EdsCameraAddedHandler(trampoline)


def set_object_handler(
    camera_ref: c_void_p,
    callback: ObjectCallback,
    event: ObjectEvent = ObjectEvent.All,
) -> None:
    handler = _make_object_handler(callback)
    check(
        _api.EdsSetObjectEventHandler(camera_ref, int(event), handler, None),
        "EdsSetObjectEventHandler",
    )
    _register(camera_ref.value or 0, handler)


def set_property_handler(
    camera_ref: c_void_p,
    callback: PropertyCallback,
    event: PropertyEvent = PropertyEvent.All,
) -> None:
    handler = _make_property_handler(callback)
    check(
        _api.EdsSetPropertyEventHandler(camera_ref, int(event), handler, None),
        "EdsSetPropertyEventHandler",
    )
    _register(camera_ref.value or 0, handler)


def set_state_handler(
    camera_ref: c_void_p,
    callback: StateCallback,
    event: StateEvent = StateEvent.All,
) -> None:
    handler = _make_state_handler(callback)
    check(
        _api.EdsSetCameraStateEventHandler(camera_ref, int(event), handler, None),
        "EdsSetCameraStateEventHandler",
    )
    _register(camera_ref.value or 0, handler)


def set_camera_added_handler(callback: CameraAddedCallback) -> None:
    handler = _make_added_handler(callback)
    check(_api.EdsSetCameraAddedHandler(handler, None), "EdsSetCameraAddedHandler")
    _register(0, handler)


def pump_events(duration_s: float, interval_s: float = 0.05) -> None:
    """Drain queued SDK events for ``duration_s`` seconds.

    Must be called from the same thread that owns the SDK (the thread that
    initialised it and opened the sessions). Useful for "let the camera
    settle" delays after issuing a command.
    """
    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline:
        get_event()
        time.sleep(interval_s)


def wait_until(
    predicate: Callable[[], bool], timeout_s: float = 30.0, interval_s: float = 0.05
) -> bool:
    """Loop ``EdsGetEvent`` on the calling thread until ``predicate`` is true.

    Returns ``True`` if the predicate became truthy within ``timeout_s``,
    ``False`` on timeout. Use this from the main thread instead of
    ``threading.Event.wait`` when you need callbacks to fire — Python
    `Event.wait` blocks the main thread, but EDSDK requires that thread to
    call ``EdsGetEvent`` for callbacks to be delivered.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        get_event()
        if predicate():
            return True
        time.sleep(interval_s)
    return False
