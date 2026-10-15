"""Single-instance guard via a named Windows mutex + wake-up event."""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes

from . import config

log = logging.getLogger("metube.single_instance")

ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0x00000000
EVENT_MODIFY_STATE = 0x0002
SYNCHRONIZE = 0x00100000

_mutex_handle = None
_event_handle = None

if hasattr(ctypes, "windll"):
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    _kernel32.CreateMutexW.restype = wintypes.HANDLE
    _kernel32.CreateEventW.argtypes = [
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    _kernel32.CreateEventW.restype = wintypes.HANDLE
    _kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    _kernel32.OpenEventW.restype = wintypes.HANDLE
    _kernel32.SetEvent.argtypes = [wintypes.HANDLE]
    _kernel32.SetEvent.restype = wintypes.BOOL
    _kernel32.ResetEvent.argtypes = [wintypes.HANDLE]
    _kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD
else:  # pragma: no cover - non Windows dev
    _kernel32 = None


def acquire() -> bool:
    """Return True when we are the first instance."""
    global _mutex_handle, _event_handle
    if _kernel32 is None:
        return True
    ctypes.set_last_error(0)
    _mutex_handle = _kernel32.CreateMutexW(None, True, config.SINGLE_INSTANCE_MUTEX)
    already = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
    _event_handle = _kernel32.CreateEventW(None, False, False, config.SINGLE_INSTANCE_EVENT)
    return not already


def signal_existing_instance() -> None:
    """Tell the running instance to show itself, then exit."""
    if _kernel32 is None:
        return
    handle = _kernel32.OpenEventW(EVENT_MODIFY_STATE | SYNCHRONIZE, False, config.SINGLE_INSTANCE_EVENT)
    if handle:
        try:
            _kernel32.SetEvent(handle)
        finally:
            _kernel32.CloseHandle(handle)


def poll_signal() -> bool:
    """Non-blocking check of the wake-up event (call from the Tk poller)."""
    if _kernel32 is None or not _event_handle:
        return False
    result = _kernel32.WaitForSingleObject(_event_handle, 0)
    if result == WAIT_OBJECT_0:
        _kernel32.ResetEvent(_event_handle)
        log.info("second-instance signal received")
        return True
    return False
