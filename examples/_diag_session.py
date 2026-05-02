"""Minimal diagnostic — open session, read SaveTo, try various write orders.

Usage:
    pipenv run python -u examples/_diag_session.py
"""

from __future__ import annotations

import signal
import sys
import time

import edsdk
from edsdk import PropID, SaveTo


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]

    def _interrupt(*_: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _interrupt)

    with edsdk.SDK():
        cam = edsdk.list_cameras()[0]
        log(f"Camera: {cam.device_info().device_description}")

        with cam:
            log("session opened, sleeping 0.5s")
            time.sleep(0.5)

            log("step 1: set_capacity()")
            t0 = time.monotonic()
            cam.set_capacity()
            log(f"  ok in {time.monotonic() - t0:.2f}s")
            time.sleep(0.2)

            log("step 2: read SaveTo")
            t0 = time.monotonic()
            current = int(cam.get_property(PropID.SaveTo))
            log(f"  SaveTo={current} in {time.monotonic() - t0:.2f}s")

            if current != int(SaveTo.Host):
                log("step 3: set SaveTo=Host")
                t0 = time.monotonic()
                cam.set_property(PropID.SaveTo, int(SaveTo.Host))
                log(f"  ok in {time.monotonic() - t0:.2f}s")
            else:
                log("step 3: SaveTo already Host, skipping set")

            log("step 4: read AEMode (no-write probe)")
            t0 = time.monotonic()
            ae = cam.get_property(PropID.AEMode)
            log(f"  AEMode={ae} in {time.monotonic() - t0:.2f}s")

        log("session closed cleanly")
    log("SDK terminated cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
