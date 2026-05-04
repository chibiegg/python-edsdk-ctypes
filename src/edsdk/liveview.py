"""Live-view (Evf) frame acquisition.

EDSDK live view consists of three pieces:

1. Enable live view by setting ``PropID.Evf_OutputDevice`` to a value with the
   PC bit set (``EvfOutputDevice.PC = 2``).
2. For each frame: create a memory stream + an ``EvfImageRef`` bound to it,
   then call ``EdsDownloadEvfImage`` to populate the stream with a JPEG.
3. Disable live view by clearing the PC bit.

This module provides a high-level ``LiveView`` context manager that handles
(1) and (3) and yields JPEG bytes from each ``frame()`` call.
"""

from __future__ import annotations

from ctypes import byref, c_void_p
from types import TracebackType

from . import _api
from ._types import EdsEvfImageRef
from .constants import PropID
from .errors import check
from .properties import get_property, set_property
from .streams import Stream

# EvfOutputDevice bit flags (from EDSDKTypes.h)
EVF_OUTPUT_NONE = 0
EVF_OUTPUT_TFT = 1  # camera back-screen
EVF_OUTPUT_PC = 2  # streamed to host
EVF_OUTPUT_MOBILE = 4
EVF_OUTPUT_MOBILE2 = 8


class LiveView:
    """Context manager that toggles live view on entry/exit.

    Example::

        with edsdk.SDK():
            cam = edsdk.list_cameras()[0]
            with cam, LiveView(cam) as lv:
                jpeg = lv.frame()
    """

    def __init__(self, camera: Camera) -> None:  # type: ignore[name-defined] # noqa: F821
        self._camera = camera
        self._previous: int | None = None

    def __enter__(self) -> LiveView:
        # Remember the current device flag so we can restore it on exit.
        try:
            self._previous = int(get_property(self._camera.ref, int(PropID.Evf_OutputDevice)))
        except Exception:
            self._previous = None
        target = (self._previous or 0) | EVF_OUTPUT_PC
        set_property(self._camera.ref, int(PropID.Evf_OutputDevice), target)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            target = (self._previous if self._previous is not None else 0) & ~EVF_OUTPUT_PC
            set_property(self._camera.ref, int(PropID.Evf_OutputDevice), target)
        except Exception:
            pass

    def frame(self) -> bytes:
        """Pull one JPEG frame from the camera. Returns the raw JPEG bytes."""
        with Stream.memory(0) as stream:
            evf = EdsEvfImageRef()
            check(_api.EdsCreateEvfImageRef(stream.ref, byref(evf)), "EdsCreateEvfImageRef")
            try:
                check(
                    _api.EdsDownloadEvfImage(self._camera.ref, evf),
                    "EdsDownloadEvfImage",
                )
                return stream.read_all()
            finally:
                _api.EdsRelease(evf)


__all__ = [
    "EVF_OUTPUT_MOBILE",
    "EVF_OUTPUT_MOBILE2",
    "EVF_OUTPUT_NONE",
    "EVF_OUTPUT_PC",
    "EVF_OUTPUT_TFT",
    "LiveView",
]


# Re-import to silence unused-import lint when ``c_void_p`` is unused after edits.
_ = c_void_p
