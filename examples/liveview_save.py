"""Capture N JPEG frames from the live-view stream and save them to disk.

Usage:
    EDSDK_LIBRARY_PATH=/path/to/EDSDK pipenv run python examples/liveview_save.py [count] [out_dir]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import edsdk


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("liveview")
    out_dir.mkdir(parents=True, exist_ok=True)

    with edsdk.SDK():
        cameras = edsdk.list_cameras()
        if not cameras:
            print("No cameras detected.")
            return 1
        cam = cameras[0]
        print(f"Camera: {cam.device_info().device_description}")

        with cam, edsdk.LiveView(cam) as lv:
            # The first few frames may fail with DEVICE_BUSY while live view
            # spins up — give it a moment.
            time.sleep(0.5)

            saved = 0
            t0 = time.monotonic()
            # Codes seen during live-view warm-up on R-series bodies:
            #   0x8D44 EDS_ERR_OBJECT_NOTREADY — generic not-ready
            #   0xA101 / 0xA102 — EVF buffer not yet populated
            transient = {0x8D44, 0xA101, 0xA102}
            while saved < count:
                try:
                    jpeg = lv.frame()
                except edsdk.EdsError as e:
                    if e.code in transient:
                        time.sleep(0.05)
                        continue
                    raise
                path = out_dir / f"frame_{saved:04d}.jpg"
                path.write_bytes(jpeg)
                saved += 1
            dt = time.monotonic() - t0
            fps = saved / dt if dt > 0 else float("inf")
            print(f"Saved {saved} frames in {dt:.2f}s ({fps:.1f} fps avg)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
