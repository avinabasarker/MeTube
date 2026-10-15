"""Keep-awake guard.

Acquired ONLY when a download actually starts, released when the queue goes
fully idle (regression B8).  Every transition is logged; the calls are
idempotent and safe on non-Windows.
"""

from __future__ import annotations

import ctypes
import logging

log = logging.getLogger("metube.keepawake")

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

_acquired = False
_enabled = True


def set_enabled(enabled: bool) -> None:
    global _enabled
    _enabled = bool(enabled)


def is_acquired() -> bool:
    return _acquired


def _call(flags: int) -> None:
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:  # pragma: no cover - non Windows dev
        pass


def acquire() -> None:
    global _acquired
    if _acquired or not _enabled:
        return
    _acquired = True
    _call(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    log.info("keep-awake ACQUIRED (queue active)")


def release() -> None:
    global _acquired
    if not _acquired:
        return
    _acquired = False
    _call(ES_CONTINUOUS)
    log.info("keep-awake RELEASED (queue idle)")
