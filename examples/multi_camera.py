"""Open all connected cameras and grab one live-view frame from each.

Demonstrates: multi-camera enumeration, per-camera session/live-view contexts.

Usage:
    EDSDK_LIBRARY_PATH=/path/to/EDSDK pipenv run python examples/multi_camera.py [out_dir]
"""

from __future__ import annotations

import sys
import time
from contextlib import ExitStack
from pathlib import Path

import edsdk


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("multicam")
    out_dir.mkdir(parents=True, exist_ok=True)

    with edsdk.SDK():
        cameras = edsdk.list_cameras()
        if not cameras:
            print("No cameras detected.")
            return 1
        print(f"Detected {len(cameras)} camera(s).")

        with ExitStack() as stack:
            sessions = [stack.enter_context(c) for c in cameras]
            live_views = [stack.enter_context(edsdk.LiveView(c)) for c in sessions]
            time.sleep(0.7)

            for i, (cam, lv) in enumerate(zip(sessions, live_views, strict=True)):
                info = cam.device_info()
                jpeg = lv.frame()
                path = out_dir / f"cam{i:02d}_{info.device_sub_type}.jpg"
                path.write_bytes(jpeg)
                print(f"  [{i}] {info.device_description} -> {path} ({len(jpeg)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
