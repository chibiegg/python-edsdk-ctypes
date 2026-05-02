"""Stream live view, decode QR codes, print position rectangles.

Demonstrates pairing the EDSDK live-view stream with OpenCV's QR detector
to continuously locate QR codes in the camera's field of view.

Requirements:
    pipenv install --dev opencv-python-headless numpy pyzbar

Usage:
    EDSDK_LIBRARY_PATH=/path/to/EDSDK pipenv run python examples/liveview_qrcode.py
"""

from __future__ import annotations

import sys
import time

import edsdk

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover
    print("This example needs opencv-python-headless and numpy.")
    print("  pipenv install --dev opencv-python-headless numpy")
    sys.exit(2)


def main() -> int:
    detector = cv2.QRCodeDetector()
    duration_s = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0

    with edsdk.SDK():
        cameras = edsdk.list_cameras()
        if not cameras:
            print("No cameras detected.")
            return 1
        cam = cameras[0]
        print(f"Camera: {cam.device_info().device_description}")

        with cam, edsdk.LiveView(cam) as lv:
            time.sleep(0.5)
            t_end = time.monotonic() + duration_s
            frames = 0
            detections = 0

            while time.monotonic() < t_end:
                try:
                    jpeg = lv.frame()
                except edsdk.EdsError as e:
                    if e.name == "EDS_ERR_OBJECT_NOTREADY":
                        time.sleep(0.02)
                        continue
                    raise

                arr = np.frombuffer(jpeg, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is None:
                    continue
                frames += 1

                ok, decoded_info, points, _ = detector.detectAndDecodeMulti(img)
                if ok:
                    for text, pts in zip(decoded_info, points, strict=False):
                        if not text:
                            continue
                        detections += 1
                        cx = float(pts[:, 0].mean())
                        cy = float(pts[:, 1].mean())
                        print(f"  QR={text!r}  center=({cx:.1f}, {cy:.1f})")

            print(f"Scanned {frames} frames, {detections} QR detection(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
