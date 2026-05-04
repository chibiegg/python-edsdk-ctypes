"""High-level camera handle."""

from __future__ import annotations

from ctypes import byref, c_void_p
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

from . import _api
from ._types import EdsCapacity, EdsDeviceInfo, EdsDirectoryItemInfo
from .constants import (
    CameraCommand,
    CameraStatusCommand,
    DcRemoteShootingMode,
    ObjectEvent,
    PropertyEvent,
    StateEvent,
)
from .errors import check
from .properties import (
    get_property,
    get_property_desc,
    get_property_size,
    set_property,
)
from .streams import Stream


@dataclass(frozen=True)
class DeviceInfo:
    """Plain-Python view of ``EdsDeviceInfo``."""

    port_name: str
    device_description: str
    device_sub_type: int


@dataclass(frozen=True)
class DirectoryItemInfo:
    """Plain-Python view of ``EdsDirectoryItemInfo``."""

    size: int
    is_folder: bool
    group_id: int
    option: int
    file_name: str
    format: int
    date_time: int


class Camera:
    """Wraps an ``EdsCameraRef``.

    Manages the underlying ref-count and the open-session state. Use as a
    context manager to scope a session::

        with cam:
            info = cam.device_info()
    """

    def __init__(self, ref: c_void_p) -> None:
        if not ref or ref.value is None:
            raise ValueError("Camera ref is null")
        self._ref: c_void_p | None = ref
        self._session_open = False

    @property
    def ref(self) -> c_void_p:
        if self._ref is None:
            raise RuntimeError("Camera has been released")
        return self._ref

    # -- Identity --------------------------------------------------------

    def device_info(self) -> DeviceInfo:
        info = EdsDeviceInfo()
        check(_api.EdsGetDeviceInfo(self.ref, byref(info)), "EdsGetDeviceInfo")
        return DeviceInfo(
            port_name=info.szPortName.decode("utf-8", errors="replace").rstrip("\x00"),
            device_description=info.szDeviceDescription.decode(
                "utf-8", errors="replace"
            ).rstrip("\x00"),
            device_sub_type=int(info.deviceSubType),
        )

    # -- Session lifecycle ----------------------------------------------

    def open_session(self) -> None:
        check(_api.EdsOpenSession(self.ref), "EdsOpenSession")
        self._session_open = True

    def close_session(self) -> None:
        if not self._session_open:
            return
        self._session_open = False
        # If CloseSession itself fails (e.g. body in odd state after a
        # crashed run), don't propagate — releasing the ref still helps.
        try:
            check(_api.EdsCloseSession(self.ref), "EdsCloseSession")
        except Exception:  # noqa: BLE001
            pass

    def release(self) -> None:
        if self._ref is None:
            return
        if self._session_open:
            try:
                self.close_session()
            except Exception:
                self._session_open = False
        ref, self._ref = self._ref, None
        _api.EdsRelease(ref)

    # -- Properties ------------------------------------------------------

    def get_property(self, property_id: int, param: int = 0) -> Any:
        return get_property(self.ref, int(property_id), param)

    def set_property(self, property_id: int, value: Any, param: int = 0) -> None:
        set_property(self.ref, int(property_id), value, param)

    def get_property_size(self, property_id: int, param: int = 0) -> tuple[int, int]:
        return get_property_size(self.ref, int(property_id), param)

    def get_property_desc(self, property_id: int) -> dict[str, Any]:
        return get_property_desc(self.ref, int(property_id))

    # -- Commands --------------------------------------------------------

    def send_command(self, command: int | CameraCommand, param: int = 0) -> None:
        check(_api.EdsSendCommand(self.ref, int(command), int(param)), "EdsSendCommand")

    def send_status_command(
        self, command: int | CameraStatusCommand, param: int = 0
    ) -> None:
        check(
            _api.EdsSendStatusCommand(self.ref, int(command), int(param)),
            "EdsSendStatusCommand",
        )

    def start_remote_shooting(self) -> None:
        """Enter PC-tethered shooting mode.

        Recent Canon mirrorless bodies (R3 / R5 / R5C / R6 / R7 / R8 /
        R10 / R50 / R100, etc.) refuse capture commands unless the host
        first sends ``SetRemoteShootingMode = Start``. Older DSLRs ignore
        this command — calling it is harmless either way, so the safe
        default is to issue it once after ``OpenSession``.
        """
        try:
            self.send_command(
                CameraCommand.SetRemoteShootingMode, int(DcRemoteShootingMode.Start)
            )
        except Exception:  # noqa: BLE001
            # Older bodies report ENUM_NA / NOT_SUPPORTED — that's fine.
            pass

    def stop_remote_shooting(self) -> None:
        try:
            self.send_command(
                CameraCommand.SetRemoteShootingMode, int(DcRemoteShootingMode.Stop)
            )
        except Exception:  # noqa: BLE001
            pass

    def ui_lock(self) -> None:
        """Lock the camera UI (``EdsSendStatusCommand(UILock)``).

        Required around shutter operations on recent EOS bodies. We pass
        ``param=0`` (TFT remains on); R-series bodies can drop the USB
        connection if asked to turn the TFT off via ``param=1`` —
        ``param=0`` is the safer default observed on R3.
        """
        self.send_status_command(CameraStatusCommand.UILock, 0)

    def ui_unlock(self) -> None:
        try:
            self.send_status_command(CameraStatusCommand.UIUnLock, 0)
        except Exception:  # noqa: BLE001
            pass

    def do_evf_autofocus(self) -> None:
        """Trigger autofocus during live view (``DoEvfAf = On``).

        While live view is active, the regular ``PressShutterButton``
        Halfway-press does **not** drive AF on R-series bodies — the
        proper way to focus is to send the ``DoEvfAf`` camera command.
        Call this just before :meth:`take_picture` (which should then
        be invoked with ``autofocus=False`` to avoid a redundant AF
        action) when working in tethered live-view mode.

        The camera focuses using the current ``Evf_AFMode`` (point /
        face / tracking, depending on body and configuration). The
        command returns once focus has been attempted; the host should
        give the camera a brief moment (≈ 100–500 ms) for the result
        to settle before issuing the shutter press.

        Note:
            On some R-series bodies (verified on R3 with current
            firmware) ``DoEvfAf`` returns ``EDS_ERR_DEVICE_NOT_FOUND``
            even with the lens in AF and live view streaming. Use
            :meth:`autofocus_via_halfpress` as a fallback in that case.
        """
        from .constants import EvfAf

        self.send_command(CameraCommand.DoEvfAf, int(EvfAf.ON))

    def autofocus_via_halfpress(self, settle_s: float = 0.4) -> None:
        """Drive AF by pressing the shutter halfway via the tethered
        shutter sequence (UILock + PressShutterButton.Halfway).

        This is the fallback when ``DoEvfAf`` is rejected by the body
        (e.g. R3 returning ``DEVICE_NOT_FOUND``). The half-press is
        wrapped in ``UILock``/``UIUnLock`` to match the body's tethered
        capture state machine; without it, the press is silently
        ignored on recent R-series firmware.
        """
        from .constants import ShutterButton

        self.ui_lock()
        try:
            self.send_command(
                CameraCommand.PressShutterButton, int(ShutterButton.Halfway)
            )
            if settle_s > 0:
                from . import _api  # noqa: F401  (ensure module loaded)
                from .events import pump_events

                pump_events(settle_s)
        finally:
            try:
                self.send_command(
                    CameraCommand.PressShutterButton, int(ShutterButton.OFF)
                )
            except Exception:  # noqa: BLE001
                pass
            self.ui_unlock()

    def take_picture(self, autofocus: bool = False) -> None:
        """Trigger a single still capture.

        Modern Canon bodies (EOS R / RP / R3 / R5 / R6 / R8 etc.) refuse the
        legacy ``CameraCommand.TakePicture`` opcode and instead require:

        1. ``UILock`` (status command, ``param=0``)
        2. ``PressShutterButton`` — full press (with or without AF)
        3. ``PressShutterButton`` — release (``OFF``)
        4. ``UIUnLock`` (status command)

        This is what Canon's official ``MultiCamCui`` sample does on R-series
        bodies, and what this method implements.

        Args:
            autofocus: When ``True``, engage AF during the press
                (``ShutterButton.Completely``). When ``False`` (default),
                use ``Completely_NonAF`` — most reliable for tethered
                machine-vision use where AF may hunt.

        Note:
            **Live view must be active.** R-series bodies (verified on R3)
            return ``EDS_ERR_PARTIAL_DELETION`` for tethered captures unless
            live view is enabled (``Evf_OutputDevice`` has the PC bit set).
            Wrap calls in an :class:`edsdk.LiveView` context, or call
            :meth:`enable_live_view` before this method.

            **Threading**: this must be called from the same thread that
            owns the SDK. Pair it with :func:`edsdk.wait_until` to wait
            for the resulting ``ObjectEvent.DirItemRequestTransfer``
            callback on the same thread.
        """
        from .constants import ShutterButton

        full = ShutterButton.Completely if autofocus else ShutterButton.Completely_NonAF
        self.ui_lock()
        try:
            self.send_command(CameraCommand.PressShutterButton, int(full))
        finally:
            try:
                self.send_command(
                    CameraCommand.PressShutterButton, int(ShutterButton.OFF)
                )
            except Exception:  # noqa: BLE001
                pass
            self.ui_unlock()

    def set_capacity(
        self,
        number_of_free_clusters: int = 0x7FFFFFFF,
        bytes_per_sector: int = 512,
        reset: bool = True,
    ) -> None:
        """Tell the camera how much host-side capacity is available.

        Required before ``SaveTo.Host`` transfers will work on most bodies.
        """
        cap = EdsCapacity(
            numberOfFreeClusters=int(number_of_free_clusters),
            bytesPerSector=int(bytes_per_sector),
            reset=int(bool(reset)),
        )
        check(_api.EdsSetCapacity(self.ref, cap), "EdsSetCapacity")

    # -- Event handlers --------------------------------------------------

    def on_object_event(
        self, callback, event: ObjectEvent = ObjectEvent.All
    ) -> None:
        from .events import set_object_handler

        set_object_handler(self.ref, callback, event)

    def on_property_event(
        self, callback, event: PropertyEvent = PropertyEvent.All
    ) -> None:
        from .events import set_property_handler

        set_property_handler(self.ref, callback, event)

    def on_state_event(self, callback, event: StateEvent = StateEvent.All) -> None:
        from .events import set_state_handler

        set_state_handler(self.ref, callback, event)

    # -- Directory item helpers (used from within object-event callbacks) --

    @staticmethod
    def get_directory_item_info(item_handle: int) -> DirectoryItemInfo:
        info = EdsDirectoryItemInfo()
        check(
            _api.EdsGetDirectoryItemInfo(c_void_p(item_handle), byref(info)),
            "EdsGetDirectoryItemInfo",
        )
        return DirectoryItemInfo(
            size=int(info.size),
            is_folder=bool(info.isFolder),
            group_id=int(info.groupID),
            option=int(info.option),
            file_name=info.szFileName.decode("utf-8", errors="replace").rstrip("\x00"),
            format=int(info.format),
            date_time=int(info.dateTime),
        )

    @staticmethod
    def download_to_file(item_handle: int, dest_path: str | Path) -> Path:
        """Download a directory item (typically a freshly captured image) to disk.

        Always release the directory item handle when you no longer need it.
        """
        info = Camera.get_directory_item_info(item_handle)
        path = Path(dest_path)
        if path.is_dir():
            path = path / info.file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        with Stream.file(path) as stream:
            check(
                _api.EdsDownload(c_void_p(item_handle), info.size, stream.ref),
                "EdsDownload",
            )
            check(
                _api.EdsDownloadComplete(c_void_p(item_handle)),
                "EdsDownloadComplete",
            )
        return path

    @staticmethod
    def release_handle(item_handle: int) -> None:
        """Release a raw EDSDK handle delivered via callbacks."""
        if item_handle:
            _api.EdsRelease(c_void_p(item_handle))

    # -- Context manager / lifecycle ------------------------------------

    def __enter__(self) -> Camera:
        self.open_session()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close_session()

    def __del__(self) -> None:
        try:
            self.release()
        except Exception:
            pass
