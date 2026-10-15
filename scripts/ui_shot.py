"""Launch the app, focus its window, and screenshot just that window.

Usage:
    python scripts/ui_shot.py OUT.png [delay_seconds] [data_dir]

This drives the real window (not a mock) and captures only the MeTube window
rectangle, which is the evidence used for the UI test rows.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Match the app: without this, GetWindowRect and ImageGrab disagree on a
# scaled desktop and the captured rectangle is wrong.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:  # noqa: BLE001
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:  # noqa: BLE001
        pass

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_uint,
]
SW_RESTORE = 9
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
WINDOW_TITLE = "MeTube"


def find_window(timeout: float = 25.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        handle = user32.FindWindowW(None, WINDOW_TITLE)
        if handle:
            return handle
        time.sleep(0.4)
    return None


def focus_window(handle) -> None:
    user32.ShowWindow(handle, SW_RESTORE)
    user32.SetWindowPos(handle, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE)
    user32.BringWindowToTop(handle)
    user32.SetForegroundWindow(handle)
    time.sleep(0.8)


def window_rect(handle) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    user32.GetWindowRect(handle, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("delay", nargs="?", type=float, default=3.0)
    parser.add_argument("data_dir", nargs="?", default=str(ROOT / ".testdata"))
    parser.add_argument("--hold", type=float, default=0.0, help="seconds to keep the app alive after the shot")
    args = parser.parse_args()

    env = dict(os.environ)
    env["METUBE_DATA_DIR"] = args.data_dir
    proc = subprocess.Popen([sys.executable, str(ROOT / "app.py")], cwd=str(ROOT), env=env)
    try:
        handle = find_window()
        if handle is None:
            print("ERROR: MeTube window never appeared")
            return 2
        time.sleep(args.delay)
        focus_window(handle)
        left, top, right, bottom = window_rect(handle)
        from PIL import ImageGrab

        image = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
        user32.SetWindowPos(handle, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        image.save(out)
        print(f"saved {out} size={image.size} rect=({left},{top},{right},{bottom}) pid={proc.pid}")
        if args.hold:
            time.sleep(args.hold)
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
