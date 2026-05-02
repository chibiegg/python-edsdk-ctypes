"""Trigger a single capture and download the resulting file to disk.

Demonstrates: object-event callback, capacity announcement, SaveTo.Host
download flow, single-thread event pumping (required by EDSDK), and the
**live-view-active + UILock** capture sequence required by R-series bodies.

Usage:
    EDSDK_LIBRARY_PATH=/path/to/EDSDK pipenv run python examples/take_picture.py [out_dir]

Image format: by default the camera's stored ``ImageQuality`` is left
alone. Pass ``--jpeg`` to force ``LJF`` (Large JPEG Fine) — useful when
downstream processing wants JPEG instead of RAW (CR3).
"""

from __future__ import annotations

import argparse
import signal
import sys
import traceback
from pathlib import Path

import edsdk
from edsdk import Camera, ImageQuality, ObjectEvent, PropID, SaveTo


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument(
        "out_dir",
        nargs="?",
        type=Path,
        default=Path("captures"),
        help="Directory to save the captured file in (default: ./captures)",
    )
    p.add_argument(
        "--jpeg",
        action="store_true",
        help="Force ImageQuality=Large JPEG Fine before capturing.",
    )
    p.add_argument(
        "--af",
        action="store_true",
        help="Engage autofocus during capture (default: NonAF — most reliable).",
    )
    return p.parse_args(argv)


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]

    def _on_sigterm(*_: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _on_sigterm)

    saved: list[Path] = []
    transfer_done = False

    def on_object(event: ObjectEvent, handle: int) -> None:
        nonlocal transfer_done
        log(f"  object event: {event.name} handle=0x{handle:x}")
        if event == ObjectEvent.DirItemRequestTransfer:
            try:
                path = Camera.download_to_file(handle, args.out_dir)
                saved.append(path)
                log(f"  saved: {path}")
            except Exception:  # noqa: BLE001
                log("  download failed:")
                traceback.print_exc()
            finally:
                Camera.release_handle(handle)
                transfer_done = True

    with edsdk.SDK():
        cameras = edsdk.list_cameras()
        if not cameras:
            log("No cameras detected.")
            return 1
        cam = cameras[0]
        log(f"Camera: {cam.device_info().device_description}")

        with cam:
            cam.on_object_event(on_object)
            cam.set_capacity()
            log("  capacity announced")

            settled = False
            if int(cam.get_property(PropID.SaveTo)) != int(SaveTo.Host):
                cam.set_property(PropID.SaveTo, int(SaveTo.Host))
                log("  SaveTo set to Host")
                settled = True

            if args.jpeg:
                target = int(ImageQuality.LJF)
                if int(cam.get_property(PropID.ImageQuality)) != target:
                    cam.set_property(PropID.ImageQuality, target)
                    log(f"  ImageQuality set to LJF (0x{target:08x})")
                    settled = True

            if settled:
                # R3 needs a moment to apply property changes before it
                # will accept a capture command — without this, the next
                # PressShutter returns EDS_ERR_PARTIAL_DELETION.
                edsdk.pump_events(0.5)

            # R-series bodies refuse PressShutter unless live view is on.
            with edsdk.LiveView(cam):
                log("  live view active, settling 0.7s")
                edsdk.pump_events(0.7)

                log(f"Triggering capture (autofocus={args.af})...")
                try:
                    cam.take_picture(autofocus=args.af)
                except edsdk.EdsError as e:
                    log(f"  PressShutterButton failed: {e}")
                    return 4
                log("  shutter sequence sent — waiting for transfer event")

                if not edsdk.wait_until(lambda: transfer_done, timeout_s=20.0):
                    log("Timed out waiting for transfer.")
                    return 2
                edsdk.pump_events(0.3)

    return 0 if saved else 3


if __name__ == "__main__":
    raise SystemExit(main())
