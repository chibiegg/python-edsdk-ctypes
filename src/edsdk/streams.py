"""Wrappers around EdsStreamRef (file and memory streams)."""

from __future__ import annotations

from ctypes import byref, c_void_p, memmove, string_at
from pathlib import Path
from types import TracebackType

from . import _api
from ._types import EdsStreamRef, EdsUInt64
from .constants import Access, FileCreateDisposition
from .errors import check


class Stream:
    """Owning wrapper around an ``EdsStreamRef``.

    The underlying ref is released on :meth:`close`, on exiting the context
    manager, or on garbage collection.
    """

    def __init__(self, ref: c_void_p) -> None:
        if not ref or ref.value is None:
            raise ValueError("Stream ref is null")
        self._ref: c_void_p | None = ref

    @property
    def ref(self) -> c_void_p:
        if self._ref is None:
            raise RuntimeError("Stream has been released")
        return self._ref

    @classmethod
    def file(
        cls,
        path: str | Path,
        disposition: FileCreateDisposition = FileCreateDisposition.CreateAlways,
        access: Access = Access.ReadWrite,
    ) -> Stream:
        """Create a file stream.

        Uses the cross-platform ``EdsCreateFileStream`` (UTF-8 char path).
        """
        encoded = str(path).encode("utf-8")
        ref = EdsStreamRef()
        check(
            _api.EdsCreateFileStream(encoded, int(disposition), int(access), byref(ref)),
            "EdsCreateFileStream",
        )
        return cls(ref)

    @classmethod
    def memory(cls, size: int = 0) -> Stream:
        """Create an in-memory stream of the given initial size (auto-grows)."""
        ref = EdsStreamRef()
        check(
            _api.EdsCreateMemoryStream(EdsUInt64(size), byref(ref)),
            "EdsCreateMemoryStream",
        )
        return cls(ref)

    def length(self) -> int:
        n = EdsUInt64(0)
        check(_api.EdsGetLength(self.ref, byref(n)), "EdsGetLength")
        return int(n.value)

    def read_all(self) -> bytes:
        """Copy the entire stream contents into a Python ``bytes`` object."""
        n = self.length()
        if n == 0:
            return b""
        ptr = c_void_p()
        check(_api.EdsGetPointer(self.ref, byref(ptr)), "EdsGetPointer")
        if ptr.value:
            return string_at(ptr, n)
        # Fallback: stream without a contiguous buffer. Allocate and copy.
        buf = (c_void_p * 0)()  # placeholder; replaced below
        from ctypes import c_char

        out = (c_char * n)()
        check(_api.EdsCopyData(self.ref, EdsUInt64(n), out), "EdsCopyData")
        del buf
        return bytes(out)

    def copy_into(self, dest: memoryview) -> int:
        """Copy stream contents into a writable memoryview, returning bytes copied."""
        n = self.length()
        if n == 0:
            return 0
        if len(dest) < n:
            raise ValueError(f"Destination buffer too small ({len(dest)} < {n})")
        ptr = c_void_p()
        check(_api.EdsGetPointer(self.ref, byref(ptr)), "EdsGetPointer")
        if ptr.value:
            from ctypes import c_char

            src = (c_char * n).from_address(ptr.value)
            memmove(
                (c_char * len(dest)).from_buffer(dest),
                src,
                n,
            )
            return n
        from ctypes import c_char

        out = (c_char * len(dest)).from_buffer(dest)
        check(_api.EdsCopyData(self.ref, EdsUInt64(n), out), "EdsCopyData")
        return n

    def close(self) -> None:
        if self._ref is None:
            return
        ref, self._ref = self._ref, None
        _api.EdsRelease(ref)

    def __enter__(self) -> Stream:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
