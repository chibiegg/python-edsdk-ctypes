"""Read a few common properties from the first connected camera.

Demonstrates property get + property descriptor enumeration.

Usage:
    EDSDK_LIBRARY_PATH=/path/to/EDSDK pipenv run python examples/show_properties.py
"""

from __future__ import annotations

import edsdk
from edsdk import PropID

PROPS_TO_READ: list[tuple[str, int]] = [
    ("ProductName", PropID.ProductName),
    ("OwnerName", PropID.OwnerName),
    ("FirmwareVersion", PropID.FirmwareVersion),
    ("BatteryLevel", PropID.BatteryLevel),
    ("DateTime", PropID.DateTime),
    ("ISOSpeed", PropID.ISOSpeed),
    ("Av", PropID.Av),
    ("Tv", PropID.Tv),
    ("ExposureCompensation", PropID.ExposureCompensation),
    ("AEMode", PropID.AEMode),
    ("DriveMode", PropID.DriveMode),
    ("WhiteBalance", PropID.WhiteBalance),
    ("ImageQuality", PropID.ImageQuality),
    ("SaveTo", PropID.SaveTo),
]


def main() -> int:
    with edsdk.SDK():
        cameras = edsdk.list_cameras()
        if not cameras:
            print("No cameras detected.")
            return 1

        cam = cameras[0]
        print(f"Camera: {cam.device_info().device_description}")
        with cam:
            for name, pid in PROPS_TO_READ:
                try:
                    value = cam.get_property(pid)
                    print(f"  {name:24s} = {value!r}")
                except edsdk.EdsError as e:
                    print(f"  {name:24s} <unavailable: {e}>")

            # Show selectable values for ISO (if supported on this body).
            try:
                desc = cam.get_property_desc(PropID.ISOSpeed)
                print(f"\nISO selectable values ({len(desc['values'])}):")
                print("  " + ", ".join(f"0x{v:04x}" for v in desc["values"]))
            except edsdk.EdsError as e:
                print(f"\nISO descriptor unavailable: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
