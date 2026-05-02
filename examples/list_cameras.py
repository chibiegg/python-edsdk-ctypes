"""Sanity check: load the EDSDK, enumerate cameras, print device info.

Usage:
    EDSDK_LIBRARY_PATH=/path/to/EDSDK python examples/list_cameras.py
"""

from __future__ import annotations

import edsdk


def main() -> int:
    with edsdk.SDK():
        cameras = edsdk.list_cameras()
        if not cameras:
            print("No cameras detected.")
            return 1
        print(f"Detected {len(cameras)} camera(s):")
        for i, cam in enumerate(cameras):
            info = cam.device_info()
            print(f"  [{i}] {info.device_description} via {info.port_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
