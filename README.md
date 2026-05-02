# python-edsdk-ctypes

Pure-`ctypes` Python wrapper for the **Canon EDSDK** (EOS Digital Software Development Kit).

- **Cross-platform**: macOS, Linux, Windows — single codebase, no C++ extension to compile.
- **Python 3.12+**.
- **No build step**: ships as a normal pure-Python package.
- Designed for use cases like live-view streaming, QR / fiducial detection, remote shooting, exposure control, and multi-camera setups.

> **Status**: alpha. Public API is subject to change until 0.1.0.

> **Distribution**: PyPI as [`edsdk-ctypes`](https://pypi.org/project/edsdk-ctypes/) — `import edsdk`.

## Why another EDSDK wrapper?

The existing [`edsdk-python`](https://github.com/jiloc/edsdk-python) is a CPython C++ extension and works on Windows only. This project takes a different approach:

| | `edsdk-python` | `edsdk-ctypes` (this) |
|---|---|---|
| Implementation | C++ extension (`Python.h`) | Pure Python via `ctypes` |
| Platforms | Windows | macOS, Linux, Windows |
| Install | Requires compiler + EDSDK headers/libs at build time | `pip install`; EDSDK loaded at runtime |
| Python ABI | Per-version wheel | Any 3.12+ |

The Python-side `IntEnum` constants under `src/edsdk/constants/_generated.py` are produced mechanically from the EDSDK header by `tools/gen_constants.py`. Re-run that script when upgrading to a newer EDSDK release.

## EDSDK is NOT included

Canon distributes the EDSDK under NDA. **You must obtain it yourself** via the Canon Developer Program for your region:

- [Canon Japan](https://cweb.canon.jp/eos/info/api-package/)
- [Canon Europe](https://www.canon-europe.com/business/imaging-solutions/sdk/)
- [Canon Americas](https://developercommunity.usa.canon.com)
- [Canon Asia](https://asia.canon/en/campaign/developerresources)

This package only ships Python bindings. No EDSDK headers, libraries, or binaries are redistributed.

## Installation

```bash
pip install edsdk-ctypes
```

Then place the EDSDK library where the loader can find it. The loader searches in this order:

1. `EDSDK_LIBRARY_PATH` environment variable (path to the shared library file or its containing directory)
2. Standard system search paths (`LD_LIBRARY_PATH` on Linux, `DYLD_LIBRARY_PATH` on macOS, `PATH` on Windows)

Per-platform expectations:

| OS | File | Typical placement |
|---|---|---|
| Linux | `libEDSDK.so` (+ siblings under `Library/<arch>/`) | `EDSDK_LIBRARY_PATH=/opt/edsdk/Library/x86_64` |
| macOS | `EDSDK.framework/EDSDK` | `EDSDK_LIBRARY_PATH=/Library/Frameworks/EDSDK.framework/EDSDK` |
| Windows | `EDSDK.dll` | place next to your script, or set `EDSDK_LIBRARY_PATH` |

## Quick start

```python
import edsdk
from edsdk import PropID, SaveTo

with edsdk.SDK():
    cameras = edsdk.list_cameras()
    print(f"Found {len(cameras)} camera(s)")
    for cam in cameras:
        info = cam.device_info()
        print(f"  {info.device_description} via {info.port_name}")
        with cam:
            print("  ISO:", cam.get_property(PropID.ISOSpeed))
            cam.set_property(PropID.SaveTo, int(SaveTo.Host))
            cam.set_capacity()
```

### Live view + capture

```python
with edsdk.SDK():
    cam = edsdk.list_cameras()[0]
    with cam, edsdk.LiveView(cam) as lv:
        jpeg_bytes = lv.frame()      # returns a JPEG frame
```

```python
def on_object(event, handle):
    if event == edsdk.ObjectEvent.DirItemRequestTransfer:
        edsdk.Camera.download_to_file(handle, "captures/")
        edsdk.Camera.release_handle(handle)

with edsdk.SDK():
    cam = edsdk.list_cameras()[0]
    with cam:
        cam.on_object_event(on_object)
        cam.set_property(edsdk.PropID.SaveTo, int(edsdk.SaveTo.Host))
        cam.set_capacity()
        cam.take_picture()
```

See [`examples/`](examples/) for full runnable samples:

| Script | What it shows |
|---|---|
| `list_cameras.py` | Enumerate connected cameras |
| `show_properties.py` | Read common properties + ISO descriptor |
| `take_picture.py` | Single-shot capture with host-side download |
| `liveview_save.py` | Stream live view to N JPEG files |
| `liveview_qrcode.py` | Live view → OpenCV → QR detection (positions) |
| `multi_camera.py` | Open multiple cameras and grab one frame each |

## Notes for R-series bodies (R / RP / R3 / R5 / R6 / R8 / ...)

Verified against an EOS R3 (firmware 1.7.1), some quirks worth knowing:

- **Capture requires live view to be active.** Without ``Evf_OutputDevice``
  having the PC bit set, ``PressShutterButton`` is rejected with
  ``EDS_ERR_PARTIAL_DELETION``. The high-level ``Camera.take_picture``
  drives ``UILock → PressShutter → UIUnLock``, but you must wrap the
  call in a :class:`LiveView` context (see ``examples/take_picture.py``).
- **The legacy ``CameraCommand.TakePicture`` opcode is not accepted** —
  R-bodies require ``PressShutterButton``. ``Camera.take_picture()`` uses
  the modern flow.
- **An SD card must be inserted** even with ``SaveTo.Host`` — the body
  stages the file on card before transfer. Without a card, capture fails
  with ``PARTIAL_DELETION``.
- **``UILock`` must use ``param=0``.** ``param=1`` (TFT off) drops the USB
  connection on R3 (subsequent calls return ``DEVICE_NOT_FOUND``).
- **Property changes need a small settle delay** (~500 ms) before the
  next ``PressShutterButton``. Without it, R3 returns ``PARTIAL_DELETION``.
- **All EDSDK calls must run on the same thread.** Don't pump events
  from a worker thread while the main thread issues commands — that
  corrupts SDK state. Use ``edsdk.pump_events(...)`` /
  ``edsdk.wait_until(...)`` from the thread that owns the SDK.

## Roadmap

- [x] Library loader (Linux / macOS / Windows) with `EDSDK_LIBRARY_PATH` override
- [x] `EdsInitializeSDK` / `EdsTerminateSDK` / `EdsGetEvent` + `pump_events` / `wait_until` (single-thread)
- [x] Camera enumeration, `OpenSession` / `CloseSession`, `GetDeviceInfo`
- [x] Property get/set with type-aware marshalling (incl. Time, Rational, Rect, FocusInfo, PictureStyleDesc)
- [x] Object / Property / State / CameraAdded event handlers
- [x] `TakePicture` + download flow (`Camera.download_to_file`)
- [x] Live-view (`EvfImageRef`) → `bytes`
- [x] High-level `Camera` class encapsulating the above
- [ ] Numpy / OpenCV zero-copy decoding helper
- [ ] Property descriptor → human-readable shutter / aperture / ISO mapping
- [ ] Windows COM message-pump helper (parallel to `pump_events`)
- [ ] Smoke-test suite that runs against an attached body in CI

## Regenerating constants for a new SDK

`src/edsdk/constants/_generated.py` is produced mechanically from the
EDSDK header by `tools/gen_constants.py`. Re-run it whenever you bump to
a newer SDK release.

```bash
pipenv run python tools/gen_constants.py \
    /path/to/EDSDK/Header/EDSDKTypes.h \
    -o src/edsdk/constants/_generated.py
git diff src/edsdk/constants/_generated.py   # review additions / removals
pipenv run pytest -q                         # confirm nothing broke
```

That single output file is everything that ships — `edsdk.constants`
re-exports its `IntEnum` classes automatically, so the public API
(`edsdk.PropID`, `edsdk.CameraCommand`, …) updates with no further edits.

### How the conversion works

`gen_constants.py` reads `EDSDKTypes.h` directly (no preprocessor) and
recognises two header conventions:

| Header form | Example | Generated Python |
|---|---|---|
| **Macro group** — many `#define`s sharing a `kEds<Group>_` prefix | `#define kEdsPropID_ProductName 0x00000002` | `class PropID(IntEnum): ProductName = 0x00000002` |
| **Typedef enum** | `typedef enum { kEdsSaveTo_Camera = 1, kEdsSaveTo_Host = 2, kEdsSaveTo_Both = kEdsSaveTo_Camera \| kEdsSaveTo_Host } EdsSaveTo;` | `class SaveTo(IntEnum): Camera = 0x1; Host = 0x2; Both = 0x3` |

Naming rules:

- **Macro groups** are emitted under the bare group name (`PropID`,
  `CameraCommand`, `CameraStatusCommand`, `ObjectEvent`, `PropertyEvent`,
  `StateEvent`). Member names keep the suffix after the prefix
  (`kEdsPropID_Evf_OutputDevice` → `PropID.Evf_OutputDevice`).
- **Typedef enums** drop the leading `Eds` from the type name
  (`EdsSaveTo` → `SaveTo`, `EdsAccess` → `Access`). The longest common
  prefix shared by all members is stripped to leave clean names
  (`kEdsAccess_Read` → `Access.Read`).
- Members starting with a digit are prefixed with `_`; members that
  collide with Python keywords get a trailing `_`. Duplicate names
  (occasionally produced by header aliasing) are de-duplicated, keeping
  the first occurrence.

Constant-expression support during parsing:

- Integer literals in decimal or hex, optionally with the `L` suffix.
- References to **earlier members** in the same enum
  (`Both = Camera | Host`).
- Bitwise operators (`|`, `&`, `^`, `<<`, `>>`), arithmetic (`+`, `-`,
  `*`, `/`), and parentheses. Anything outside this safelist (string
  literals, function calls, etc.) is rejected with a clear error.
- Members without an explicit `= value` continue from the previous
  member +1 — matching C `enum` semantics.

### Things the generator does NOT cover

- **Av / Tv / ISO speed value tables** — these aren't in the header.
  They live in `Document/EDSDK_API_*.pdf`. Use
  [`Camera.get_property_desc(PropID.ISOSpeed)`](src/edsdk/properties.py)
  on a real body to enumerate the values supported by that camera.
- **Error code names** — handled separately in `src/edsdk/errors.py`
  (parsed from `EDSDKErrors.h` mentally, not from a generator).
- **Struct layouts** — defined by hand in `src/edsdk/_types.py` since
  they need ctypes-specific scalar choices.

## License

MIT — see [`LICENSE`](LICENSE).
