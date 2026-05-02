"""Smoke tests that don't require the EDSDK shared library."""

from __future__ import annotations


def test_constants_importable() -> None:
    # The constants subpackage must not depend on the loaded shared library.
    from edsdk.constants import CameraCommand, ObjectEvent, PropID

    assert CameraCommand.TakePicture == 0
    assert ObjectEvent.DirItemRequestTransfer == 0x208
    assert PropID.SaveTo == 0x0B


def test_errors_module() -> None:
    from edsdk.errors import EdsError, check

    check(0)  # OK code: no raise.
    try:
        check(0x81, "EdsOpenSession")
    except EdsError as e:
        assert e.code == 0x81
        assert "DEVICE_NOT_FOUND" in e.name
        assert "EdsOpenSession" in str(e)
    else:
        raise AssertionError("EdsError was not raised")
