"""edsdk-ctypes: pure-ctypes Python wrapper for the Canon EDSDK."""

from __future__ import annotations

from ._loader import EDSDKNotFoundError
from .camera import Camera, DeviceInfo, DirectoryItemInfo
from .constants import *  # noqa: F401, F403
from .errors import EdsError
from .events import (
    pump_events,
    set_camera_added_handler,
    set_object_handler,
    set_property_handler,
    set_state_handler,
    wait_until,
)
from .liveview import LiveView
from .properties import get_property, get_property_desc, set_property
from .sdk import SDK, get_event, initialize, list_cameras, terminate
from .streams import Stream

__version__ = "0.0.1"

__all__ = [
    "EDSDKNotFoundError",
    "EdsError",
    "Camera",
    "DeviceInfo",
    "DirectoryItemInfo",
    "LiveView",
    "SDK",
    "Stream",
    "__version__",
    "get_event",
    "get_property",
    "get_property_desc",
    "initialize",
    "list_cameras",
    "pump_events",
    "set_camera_added_handler",
    "set_object_handler",
    "set_property",
    "set_property_handler",
    "set_state_handler",
    "terminate",
    "wait_until",
]
