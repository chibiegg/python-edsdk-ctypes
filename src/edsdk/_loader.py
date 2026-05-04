"""EDSDK shared-library loader.

Locates and loads the Canon EDSDK at runtime. Supports macOS (framework),
Linux (.so), and Windows (.dll). The path can be overridden with the
``EDSDK_LIBRARY_PATH`` environment variable.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import CDLL
from pathlib import Path


class EDSDKNotFoundError(RuntimeError):
    """Raised when the EDSDK shared library cannot be located."""


_LOADED: CDLL | None = None


def _candidate_paths() -> list[Path]:
    env = os.environ.get("EDSDK_LIBRARY_PATH")
    candidates: list[Path] = []

    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            candidates.extend(_dir_candidates(p))
        else:
            candidates.append(p)

    if sys.platform == "darwin":
        candidates += [
            Path("/Library/Frameworks/EDSDK.framework/EDSDK"),
            Path.home() / "Library/Frameworks/EDSDK.framework/EDSDK",
        ]
    elif sys.platform.startswith("linux"):
        candidates += [
            Path("/usr/local/lib/libEDSDK.so"),
            Path("/usr/lib/libEDSDK.so"),
        ]
    elif sys.platform == "win32":
        candidates += [Path("EDSDK.dll")]
        # 同梱 Windows 用 DLL (worktable-watcher/vendor/edsdk-win-x64/) を
        # PyInstaller バンドル内 / リポジトリ内のどちらでも拾えるようにする。
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "edsdk-win-x64" / "EDSDK.dll")
        repo_vendor = (
            Path(__file__).resolve().parents[3] / "vendor" / "edsdk-win-x64" / "EDSDK.dll"
        )
        candidates.append(repo_vendor)

    return candidates


def _dir_candidates(directory: Path) -> list[Path]:
    if sys.platform == "darwin":
        return [
            directory / "EDSDK.framework/EDSDK",
            directory / "EDSDK",
            directory / "libEDSDK.dylib",
        ]
    if sys.platform.startswith("linux"):
        return [directory / "libEDSDK.so"]
    if sys.platform == "win32":
        return [directory / "EDSDK.dll"]
    return []


def load_edsdk() -> CDLL:
    """Load and cache the EDSDK shared library.

    Raises:
        EDSDKNotFoundError: when no candidate path resolves to a loadable library.
    """
    global _LOADED
    if _LOADED is not None:
        return _LOADED

    errors: list[str] = []
    for path in _candidate_paths():
        if not path.exists():
            errors.append(f"not found: {path}")
            continue
        try:
            _LOADED = ctypes.CDLL(str(path))
            return _LOADED
        except OSError as e:
            errors.append(f"failed to load {path}: {e}")

    raise EDSDKNotFoundError(
        "Could not locate the EDSDK shared library. "
        "Set EDSDK_LIBRARY_PATH to the EDSDK file or its directory.\n"
        "Tried:\n  " + "\n  ".join(errors or ["(no candidates)"])
    )
