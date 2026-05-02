"""Methodical R3 capture diagnostic.

Tries multiple variants of the capture sequence in order, stopping at the
first one that succeeds. Run from a fresh power-cycled camera. Each
attempt is isolated — failure of one doesn't taint subsequent ones because
we exit the SDK between scenarios.

Usage:
    pipenv run python -u examples/_diag_capture.py
"""

from __future__ import annotations

import signal
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import edsdk
from edsdk import (
    Camera,
    CameraCommand,
    CameraStatusCommand,
    LiveView,
    ObjectEvent,
    PropID,
    SaveTo,
    ShutterButton,
)


def log(msg: str) -> None:
    print(msg, flush=True)


@contextmanager
def session():
    """One isolated SDK init / open / close / terminate cycle."""
    with edsdk.SDK():
        cameras = edsdk.list_cameras()
        if not cameras:
            raise RuntimeError("no cameras")
        cam = cameras[0]
        with cam:
            yield cam


def common_setup(cam: Camera, transfer_done: list[bool]) -> None:
    def on_object(event: ObjectEvent, handle: int) -> None:
        log(f"     event: {event.name} handle=0x{handle:x}")
        if event == ObjectEvent.DirItemRequestTransfer:
            try:
                Camera.download_to_file(handle, Path("captures"))
            finally:
                Camera.release_handle(handle)
                transfer_done[0] = True

    cam.on_object_event(on_object)
    cam.set_capacity()
    if int(cam.get_property(PropID.SaveTo)) != int(SaveTo.Host):
        cam.set_property(PropID.SaveTo, int(SaveTo.Host))


def try_press(cam: Camera, label: str, status: int, with_uilock: bool) -> bool:
    log(f"=== {label}  (UILock={with_uilock}, status=0x{status:x}) ===")
    transfer_done = [False]
    try:
        common_setup(cam, transfer_done)
    except edsdk.EdsError as e:
        log(f"  setup failed: {e}")
        return False

    try:
        if with_uilock:
            log("  UILock(0)")
            cam.send_status_command(CameraStatusCommand.UILock, 0)
        log(f"  PressShutter(0x{status:x})")
        cam.send_command(CameraCommand.PressShutterButton, status)
        log("  PressShutter(OFF)")
        cam.send_command(CameraCommand.PressShutterButton, int(ShutterButton.OFF))
    except edsdk.EdsError as e:
        log(f"  FAIL: {e}")
        if with_uilock:
            try:
                cam.send_status_command(CameraStatusCommand.UIUnLock, 0)
            except Exception:  # noqa: BLE001
                pass
        return False

    if with_uilock:
        try:
            cam.send_status_command(CameraStatusCommand.UIUnLock, 0)
        except Exception:  # noqa: BLE001
            pass

    log("  waiting up to 8s for transfer event")
    if edsdk.wait_until(lambda: transfer_done[0], timeout_s=8.0):
        log("  ✅ TRANSFER OK")
        return True
    log("  ❌ no transfer event")
    return False


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))
    Path("captures").mkdir(exist_ok=True)

    scenarios = [
        ("scen-1: NonAF, UILock", int(ShutterButton.Completely_NonAF), True),
        ("scen-2: NonAF, no UILock", int(ShutterButton.Completely_NonAF), False),
        ("scen-3: with-AF, UILock", int(ShutterButton.Completely), True),
    ]

    for label, status, with_uilock in scenarios:
        log(f"\n--- starting {label} ---")
        try:
            with session() as cam:
                log(f"  Camera: {cam.device_info().device_description}")
                ok = try_press(cam, label, status, with_uilock)
                if ok:
                    return 0
        except Exception as e:  # noqa: BLE001
            log(f"  scenario aborted: {e}")
        time.sleep(1.0)

    # Last resort: live view active.
    log("\n--- starting scen-4: NonAF + UILock + live view active ---")
    try:
        with session() as cam:
            log(f"  Camera: {cam.device_info().device_description}")
            transfer_done = [False]
            common_setup(cam, transfer_done)
            with LiveView(cam):
                time.sleep(0.7)
                edsdk.pump_events(0.3)
                log("  UILock(0)")
                cam.send_status_command(CameraStatusCommand.UILock, 0)
                try:
                    cam.send_command(
                        CameraCommand.PressShutterButton,
                        int(ShutterButton.Completely_NonAF),
                    )
                    cam.send_command(
                        CameraCommand.PressShutterButton, int(ShutterButton.OFF)
                    )
                finally:
                    try:
                        cam.send_status_command(CameraStatusCommand.UIUnLock, 0)
                    except Exception:  # noqa: BLE001
                        pass
                if edsdk.wait_until(lambda: transfer_done[0], timeout_s=8.0):
                    log("  ✅ TRANSFER OK (live view path)")
                    return 0
                log("  ❌ no transfer (live view path)")
    except edsdk.EdsError as e:
        log(f"  scen-4 EdsError: {e}")
    except Exception as e:  # noqa: BLE001
        log(f"  scen-4 aborted: {e}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
