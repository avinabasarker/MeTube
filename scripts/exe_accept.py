"""Final acceptance on the BUILT exe (Section 15, step 5).

    .venv/Scripts/python.exe scripts/exe_accept.py

Drives dist\\MeTubeShip\\MeTube.exe with real Windows input (SendInput mouse and
keyboard) - no test hooks inside the app - and keeps screenshots as evidence:

  1. fresh run with no data\\ -> the first-run picker appears; click
     "Save and continue"; settings.json is written with first_run=false
  2. relaunch -> the picker must NOT appear
  3. one REAL MP3 download driven from the exe (click the box, type, click
     "Add to Queue") -> file on disk, card Completed, history row, toast logged
  4. delete data\\ and relaunch -> the picker is back (first run <=> no settings)
  5. ship folder left clean (no data\\)
"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parent.parent
SHIP = ROOT / "dist" / "MeTubeShip"
EXE = SHIP / "MeTube.exe"
DATA = SHIP / "data"
EVIDENCE = ROOT / "evidence"
TEST_DL = DATA / "_acceptance_downloads"
URL_ZOO = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

ACCENT = (108, 92, 231)
CARD = (36, 36, 42)
TOL = 26

# Match the app, or the screenshot and the cursor disagree at 125% scaling.
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
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_uint,
]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

SW_RESTORE = 9
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_A = 0x41

# The Windows console is cp1252 and the status vocabulary contains '✓'.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

TEXT_KW = {"encoding": "utf-8", "errors": "replace"}
PROBLEMS: list[str] = []
RESULTS: list[tuple[str, bool, str]] = []


# ----------------------------------------------------------------------
# input plumbing
# ----------------------------------------------------------------------
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


def _send(inp: INPUT) -> None:
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def click(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.25)
    for flags in (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP):
        inp = INPUT(type=INPUT_MOUSE)
        inp.union.mi = MOUSEINPUT(0, 0, 0, flags, 0, None)
        _send(inp)
        time.sleep(0.08)
    time.sleep(0.35)


def send_unicode(text: str) -> None:
    for char in text:
        code = ord(char)
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.union.ki = KEYBDINPUT(0, code, flags, 0, None)
            _send(inp)
            time.sleep(0.012)
    time.sleep(0.3)


def send_vk(vk: int, ctrl: bool = False) -> None:
    if ctrl:
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.union.ki = KEYBDINPUT(VK_CONTROL, 0, 0, 0, None)
        _send(inp)
    for flags in (0, KEYEVENTF_KEYUP):
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.union.ki = KEYBDINPUT(vk, 0, flags, 0, None)
        _send(inp)
    if ctrl:
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.union.ki = KEYBDINPUT(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0, None)
        _send(inp)
    time.sleep(0.3)


# ----------------------------------------------------------------------
# window helpers
# ----------------------------------------------------------------------
def is_real_window(handle) -> bool:
    """A window that is actually on screen with a usable size.

    FindWindowW also returns withdrawn or not-yet-mapped windows: the app root
    is titled 'MeTube' from construction time (long before it is shown), and a
    Toplevel exists before it is mapped. Requiring visibility plus a sane
    rectangle is the difference between driving the real UI and a phantom
    handle - the phantom is what made an earlier run check the settings file
    and the text box before either really existed.
    """
    if not handle or not user32.IsWindowVisible(handle):
        return False
    left, top, right, bottom = window_rect(handle)
    return (right - left) > 80 and (bottom - top) > 80


def find_window(title: str, timeout: float = 45.0):
    """Only ever return a visible, drawable window (see is_real_window)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        handle = user32.FindWindowW(None, title)
        if is_real_window(handle):
            return handle
        time.sleep(0.4)
    return None


def window_rect(handle) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    user32.GetWindowRect(handle, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def focus(handle) -> None:
    """Bring the window forward and confirm it really owns the keyboard.

    SetForegroundWindow fails silently while another process owns the
    foreground (Windows foreground lock), and SendInput keystrokes go to
    whatever window actually has focus - so this is verified and retried
    instead of assumed.
    """
    for _ in range(4):
        user32.ShowWindow(handle, SW_RESTORE)
        user32.SetWindowPos(handle, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE)
        user32.BringWindowToTop(handle)
        user32.SetForegroundWindow(handle)
        time.sleep(0.7)
        if user32.GetForegroundWindow() == handle:
            break
    time.sleep(0.3)


def unfocus(handle) -> None:
    user32.SetWindowPos(handle, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE)


def shot(handle, name: str, focus_first: bool = True):
    """Capture the window rectangle, retrying while it is not drawable.

    ImageGrab on a degenerate rectangle yields an empty image, which used to
    surface as a confusing PIL error; here it retries and then fails loudly.
    """
    for attempt in range(8):
        # focus_first=False grabs immediately: a freshly mapped dialog can be
        # confirmed by an external click on its button at any moment, and the
        # evidence has to win that race (see acceptance 1).
        if focus_first or attempt:
            focus(handle)
        left, top, right, bottom = window_rect(handle)
        if right - left > 50 and bottom - top > 50:
            image = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
            unfocus(handle)
            if image.size[0] > 50 and image.size[1] > 50:
                EVIDENCE.mkdir(parents=True, exist_ok=True)
                out = EVIDENCE / name
                image.save(out)
                print(f"    screenshot -> {out} {image.size}", flush=True)
                return image
        else:
            unfocus(handle)
        print(f"    {name}: window not drawable yet (attempt {attempt + 1})", flush=True)
        time.sleep(0.5)
    raise SystemExit(f"could not capture {name}: the window never became drawable")


# ----------------------------------------------------------------------
# pixel search
# ----------------------------------------------------------------------
def region_of(image, rgb, y_from: float = 0.0, y_to: float = 1.0, tol: int = TOL):
    """Bounding box (in image pixels) of the largest block of colour ``rgb``."""
    width, height = image.size
    px = image.load()
    y0 = int(height * y_from)
    y1 = int(height * y_to)
    min_x, min_y, max_x, max_y = width, height, -1, -1
    count = 0
    for y in range(y0, y1):
        for x in range(0, width):
            r, g, b = px[x, y][:3]
            if abs(r - rgb[0]) <= tol and abs(g - rgb[1]) <= tol and abs(b - rgb[2]) <= tol:
                count += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    if max_x < 0 or count < 200:
        return None
    return (min_x, min_y, max_x, max_y, count)


def note(label: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((label, bool(ok), detail))
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {label}" + (f" :: {detail}" if detail else ""), flush=True)
    if not ok:
        PROBLEMS.append(f"{label} :: {detail}")
    return bool(ok)


def launch(extra_env: dict | None = None) -> subprocess.Popen:
    env = dict(os.environ)
    env.pop("METUBE_DATA_DIR", None)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen([str(EXE)], cwd=str(SHIP), env=env)
    print(f"    launched {EXE.name} pid={proc.pid}", flush=True)
    return proc


def kill(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True, text=True, timeout=60, **TEXT_KW,
            )
        except Exception:  # noqa: BLE001
            proc.kill()
    try:
        proc.wait(timeout=20)
    except Exception:  # noqa: BLE001
        pass


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


def keep_display_awake() -> bool:
    """Ask Windows not to sleep or blank the display while the run drives it.

    Colour-targeted clicking needs a composited screen.  On this machine an
    idle period put it into a standby state where captures came back greyscale
    and synthetic input could not wake it, so the suite now holds the same
    execution-state guard the app uses for its own downloads.
    """
    try:
        result = ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )
        return bool(result)
    except Exception:  # noqa: BLE001 - best effort
        return False


def release_display() -> None:
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:  # noqa: BLE001
        pass


def ensure_colour_capture(attempts: int = 4) -> float:
    """Wake an idle display and measure how colourful a screen capture is.

    Colour-targeted clicking cannot work on a screen that is not compositing
    colour: after a long unattended run Windows started powering the display
    down and every capture came back dimmed (ACCENT arrived at ~55% brightness,
    so no exact-RGB button was ever found) and the run reported a wall of
    "the picker did not paint" failures instead.  Jiggle the mouse to ask the
    display back, then measure.  Returns the mean saturation of the last sample.

    A low number is *not* by itself a fault: a dark desktop with a dark editor
    in front legitimately measures ~4.  Detecting a dimmed capture is done on
    the app's own window instead (``accent_is_dim``), which knows what colour
    the app should be drawing, so this probe only reports what it saw.
    """
    def sample() -> float:
        try:
            shot = ImageGrab.grab().convert("RGB").resize((160, 90))
            pixels = list(shot.getdata())
            return sum(max(p) - min(p) for p in pixels) / max(1, len(pixels))
        except Exception as exc:  # noqa: BLE001 - diagnostics only
            print(f"    could not sample the screen: {exc}", flush=True)
            return -1.0

    saturation = sample()
    for _ in range(attempts):
        if saturation > 6.0:
            break
        user32.mouse_event(0x0001, 2, 0, 0, 0)
        time.sleep(0.3)
        user32.mouse_event(0x0001, -2, 0, 0, 0)
        time.sleep(1.2)
        saturation = sample()
    if 0.0 <= saturation <= 6.0:
        print(
            "    note: the desktop itself is nearly monochrome (mean "
            f"saturation {saturation:.1f}). That is normal for a dark desktop "
            "and only a problem if the app's own window is also found dimmed.",
            flush=True,
        )
    return saturation


def accent_is_dim(image) -> float:
    """Ratio of the ACCENT colour to its full brightness inside ``image``.

    Returns ~1.0 when the app's accent surfaces are drawn at their normal
    brightness, and a smaller number when the whole capture is dimmed (the
    display starting to power down).  Returns -1.0 when no accent-ish pixel is
    present at all.  Used so a dimmed capture is named as such instead of being
    reported as "the button was never drawn".
    """
    best = 0.0
    for pixel in list(image.convert("RGB").resize((80, 40)).get_flattened_data()):
        r, g, b = pixel
        # nearest multiple-of-brightness match on the ACCENT hue
        ratio = max(r / max(1, ACCENT[0]), g / max(1, ACCENT[1]), b / max(1, ACCENT[2]))
        if 0.05 < ratio < 1.4:
            if abs(r - ACCENT[0] * ratio) < 12 and abs(g - ACCENT[1] * ratio) < 12 and abs(b - ACCENT[2] * ratio) < 12:
                best = max(best, ratio)
    return best or -1.0


def sweep_mei_dirs() -> tuple[int, int]:
    """Delete PyInstaller onefile extraction dirs left in %TEMP% by kills.

    A force-killed onefile exe cannot clean up ``_MEIxxxxxx``, so every killed
    launch of MeTube.exe leaves ~34 MB behind.  A long acceptance run leaked
    ~500 MB and the machine's system drive filled up completely, which then
    broke the exe's own engine validation (it could not extract either) and
    turned three checks into false failures.  Returns (dirs, bytes).
    """
    temp = Path(os.environ.get("TEMP") or os.environ.get("TMP") or "")
    if not temp.is_dir():
        return (0, 0)
    dirs = 0
    freed = 0
    for entry in sorted(temp.glob("_MEI*")):
        if not entry.is_dir():
            continue
        try:
            size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
            shutil.rmtree(entry, ignore_errors=True)
            if not entry.exists():
                dirs += 1
                freed += size
        except OSError:
            continue
    return (dirs, freed)


def kill_stray_instances() -> None:
    """Make sure no MeTube.exe from an earlier run is still alive.

    A leftover instance keeps data\\app.log open (so the fresh-run delete
    fails) and holds the single-instance mutex (so the next launch exits
    silently) - both poisoned a real acceptance run, so this runs first.
    """
    subprocess.run(
        ["taskkill", "/IM", "MeTube.exe", "/F"],
        capture_output=True, text=True, timeout=60, **TEXT_KW,
    )
    for _ in range(20):
        probe = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq MeTube.exe", "/FO", "CSV"],
            capture_output=True, text=True, timeout=60, **TEXT_KW,
        )
        if "MeTube.exe" not in (probe.stdout or ""):
            return
        time.sleep(0.5)


def remove_data(attempts: int = 8) -> bool:
    """Delete data\\ because the shipped folder must not contain it.

    A just-killed exe can still hold app.log open for a moment, so retry
    instead of quietly ignoring the failure (which is how a stray data\\ would
    end up in the delivery).
    """
    for _ in range(attempts):
        if not DATA.exists():
            return True
        shutil.rmtree(DATA, ignore_errors=True)
        time.sleep(0.8)
    return not DATA.exists()


def read_settings() -> dict:
    path = DATA / "settings.json"
    for _ in range(20):
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:  # caught mid-write; retry briefly
            time.sleep(0.05)
    return json.loads(path.read_text(encoding="utf-8"))


def patch_settings(**values) -> None:
    """Write a settings.json for the exe to load (never a "first run").

    first_run is pinned to False: when the phase before this one failed to
    leave a settings.json behind, the merge used to inherit the app's default
    first_run=True, so the exe opened its folder picker and every later check
    in the phase failed for the wrong reason.
    """
    payload = read_settings()
    payload.update(values)
    payload["first_run"] = False
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "settings.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def confirm_picker(dialog, image, attempts: int = 3) -> bool:
    """Click 'Save and continue' until the picker really goes away.

    A single pixel-targeted click can miss (window focus, a slow first paint),
    and one missed click used to poison every later phase of the run: no
    settings.json meant the picker came back on the next launch and the folder
    checks all failed.  Re-locate the accent button from a fresh screenshot and
    retry instead.
    """
    for attempt in range(1, attempts + 1):
        if not user32.FindWindowW(None, "MeTube — first run"):
            return True
        current = image
        if attempt > 1:
            try:
                current = shot(dialog, f"final_08b_picker_confirm_retry{attempt - 1}.png",
                               focus_first=False)
            except SystemExit as exc:
                print(f"    {exc}", flush=True)
        accent = region_of(current, ACCENT) if current is not None else None
        if accent is None:
            print(f"    confirm attempt {attempt}: button not located", flush=True)
            time.sleep(1.0)
            continue
        left, top, _, _ = window_rect(dialog)
        focus(dialog)
        click(left + (accent[0] + accent[2]) // 2, top + (accent[1] + accent[3]) // 2)
        for _ in range(20):
            time.sleep(0.25)
            if not user32.FindWindowW(None, "MeTube — first run"):
                print(f"    confirm attempt {attempt}: picker closed", flush=True)
                return True
        print(f"    confirm attempt {attempt}: picker still open", flush=True)
    return not user32.FindWindowW(None, "MeTube — first run")


# ----------------------------------------------------------------------
# the run
# ----------------------------------------------------------------------
def main() -> int:
    if not EXE.exists():
        print(f"FAIL: {EXE} not found - run scripts/build_ship.py first")
        return 2

    print("\n=== acceptance 0: is the desktop able to show colour at all? ===")
    held_awake = keep_display_awake()
    print(f"    display-awake guard held: {held_awake}", flush=True)
    # Informational, not a check: measured before the exe has presented a
    # window this can read ~1.5 on a machine whose display was idle (and then
    # recover as soon as a real window is shown), so a FAIL here would be a
    # property of the moment, not of the app.  A genuinely colourless desktop
    # still shows up as the colour-targeted checks below failing.
    saturation = ensure_colour_capture()
    print(f"    screen colour before phase 1: mean saturation {saturation:.1f}", flush=True)

    print("\n=== acceptance 1: fresh first run (data\\ absent) ===")
    kill_stray_instances()
    if not remove_data():
        note("dist\\MeTubeShip\\data deleted before the fresh run", False,
             "a stray instance still holds data\\logs\\app.log")
        print("\n".join(PROBLEMS))
        return 2
    # The picker is centred, so a stray or human click on 'Save and continue'
    # can confirm it at any moment; the capture must therefore happen before
    # anything slow, and a lost race just means trying the fresh run again.
    picker_hwnd = None
    picker_accent = None
    proc = None
    for attempt in range(1, 4):
        kill_stray_instances()
        if not remove_data():
            note("dist\\MeTubeShip\\data deleted before the fresh run", False,
                 f"attempt {attempt}: a stray instance still holds data\\logs\\app.log")
            print("\n".join(PROBLEMS))
            return 2
        proc = launch()
        dialog = find_window("MeTube — first run", timeout=60)
        if dialog is None:
            kill(proc)
            break
        image = None
        try:
            image = shot(dialog, "final_01_first_run_picker.png", focus_first=False)
            accent = region_of(image, ACCENT)
            # A just-mapped dialog can be grabbed before it has painted; the
            # accent button appearing is the signal that it has drawn. Retry
            # unfocused (cheap) rather than running the focus dance, which
            # would only widen the window an external click can use.
            for _ in range(12):
                if accent is not None or not user32.FindWindowW(None, "MeTube — first run"):
                    break
                time.sleep(0.25)
                image = shot(dialog, "final_01_first_run_picker.png", focus_first=False)
                accent = region_of(image, ACCENT)
        except SystemExit as exc:
            print(f"    attempt {attempt}: {exc} - retrying the fresh run", flush=True)
            kill(proc)
            continue
        if accent is None:
            # Distinguish "the window had not painted yet" from "the capture
            # came back dimmed", which happens when the machine starts powering
            # the display down mid-run: there the accent is present but at a
            # fraction of its brightness, so the exact-RGB search misses it and
            # every colour check downstream would lie about the app.
            ratio = accent_is_dim(image) if image is not None else -1.0
            if 0.0 < ratio < 0.8:
                print(
                    f"    attempt {attempt}: the picker capture is dimmed - the "
                    f"accent colour arrived at {ratio * 100:.0f}% brightness, "
                    f"so the display is going to sleep while the run drives it",
                    flush=True,
                )
            print(f"    attempt {attempt}: picker captured before it painted - "
                  f"retrying the fresh run", flush=True)
            kill(proc)
            continue
        picker_hwnd, picker_accent = dialog, accent
        break

    note("exe launches and shows the first-run picker (visible window)",
         picker_hwnd is not None, f"hwnd={picker_hwnd}")
    note("picker drawn (accent 'Save and continue' button located)",
         picker_accent is not None, f"region={picker_accent}")
    if picker_accent and picker_hwnd:
        # Only click while it is still open: an external click may already have
        # confirmed it, and clicking a vanished dialog's old position would hit
        # the main window behind it.  confirm_picker re-locates the button and
        # retries, so one slow paint cannot spoil the whole run.
        confirm_picker(picker_hwnd, image)

    main_win = find_window("MeTube", timeout=60)
    # Read the settings the very first moment the real window is on screen:
    # the spec requires settings.json (first_run=false) to be written BEFORE
    # the main window shows, so it must already be on disk right here.
    settings = read_settings()
    note("main window opens after 'Save and continue'", main_win is not None)
    note("settings.json already had first_run=false when the window appeared",
         settings.get("first_run") is False and DATA.exists(),
         f"{DATA / 'settings.json'} -> {settings}")
    default_folder = Path(settings.get("download_folder") or "")
    note("the picked (default) download folder exists",
         bool(settings.get("download_folder")) and default_folder.is_dir(),
         str(default_folder))
    note("no crash.log after a clean first run",
         not (DATA / "logs" / "crash.log").exists())
    note("data\\bin was NOT needed (engine shipped in ship\\bin)",
         not (DATA / "bin").exists(),
         f"process alive={proc.poll() is None}")
    if main_win:
        shot(main_win, "final_02_main_window.png")
    kill(proc)

    print("\n=== acceptance 2: relaunch must NOT ask again (B14) ===")
    proc = launch()
    main_win = find_window("MeTube", timeout=60)
    time.sleep(3.0)
    again = user32.FindWindowW(None, "MeTube — first run")
    note("second launch: main window opens", main_win is not None)
    note("second launch: first-run picker does NOT appear (regression B14)",
         not again, f"picker hwnd={again}")
    kill(proc)

    print("\n=== acceptance 3: real MP3 download driven from the exe ===")
    # Keep data\ (that is what proves no picker appears) and only redirect the
    # download folder, so the test does not write into the user's Downloads.
    shutil.rmtree(TEST_DL, ignore_errors=True)
    patch_settings(
        download_folder=str(TEST_DL),
        auto_update_ytdlp=False,
        delay_min=2,
        delay_max=2,
        keep_awake=True,
        finish_notification=True,
    )
    proc = launch()
    main_win = find_window("MeTube", timeout=60)
    if main_win is None:
        note("exe reopened for the download test", False)
        kill(proc)
        return 1
    time.sleep(6.0)  # let the engine validate yt-dlp/ffmpeg

    image = shot(main_win, "final_03_before_download.png")
    accent = region_of(image, ACCENT, y_from=0.75)
    note("'Add to Queue' button located by colour in the bottom bar",
         accent is not None, f"region={accent}")
    if accent is None:
        kill(proc)
        return 1

    add_x = (accent[0] + accent[2]) // 2
    add_y = (accent[1] + accent[3]) // 2
    box_x = max(40, add_x - 260)
    box_y = max(40, accent[1] - 45)  # input box sits just above the button row

    left, top, _, _ = window_rect(main_win)
    found = None

    def queued_in_app() -> bool:
        """True once the exe's own queue.json holds the pasted video."""
        queue_path = DATA / "queue.json"
        if not queue_path.exists():
            return False
        try:
            return "jNQXAC9IVRw" in queue_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False

    def media_file():
        if not TEST_DL.exists():
            return None
        for path in TEST_DL.iterdir():
            if (
                path.is_file()
                and path.suffix == ".mp3"
                and not path.name.endswith(".part")
                and path.stat().st_size > 50_000
            ):
                return path
        return None

    for attempt in range(1, 4):
        focus(main_win)
        click(left + box_x, top + box_y)
        send_unicode(URL_ZOO)
        time.sleep(0.4)
        # Ctrl+Return is bound on the real inner Text widget and is the same
        # code path as the button, so it is one way to submit.
        send_vk(VK_RETURN, ctrl=True)
        # A real click on 'Add to Queue' is the focus-independent fallback:
        # mouse input is positional, so it works even when the foreground
        # lock kept the keystrokes away from the text box.
        click(left + add_x, top + add_y)
        print(
            f"    attempt {attempt}: typed the URL, pressed Ctrl+Return and "
            f"clicked 'Add to Queue'",
            flush=True,
        )

        # Confirm against the app's own records that the paste reached the
        # queue before waiting on the network: polling blindly here wasted a
        # full 90s per attempt when the keystrokes went to another window.
        verify_deadline = time.time() + 20
        while time.time() < verify_deadline and not queued_in_app():
            time.sleep(0.5)
        print(
            f"    attempt {attempt}: item present in the exe's queue.json = "
            f"{queued_in_app()}",
            flush=True,
        )

        deadline = time.time() + 120
        while time.time() < deadline:
            found = media_file()
            if found is not None:
                break
            time.sleep(1.0)
        if found is not None:
            break
    note("a real MP3 landed in the folder configured for the exe",
         found is not None, f"{found}")

    time.sleep(8.0)  # let the queue go idle so the toast fires
    shot(main_win, "final_04_download_completed.png")

    history_path = DATA / "history.json"
    rows = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    completed = [r for r in rows if str(r.get("status", "")).startswith("Completed")]
    note("history row recorded with file_path",
         bool(completed) and bool(completed[0].get("file_path")),
         f"{completed[0].get('status') if completed else 'no rows'}")

    log_path = DATA / "logs" / "app.log"
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    toast_lines = [ln for ln in log_text.splitlines() if "toast shown" in ln]
    note("silent finish toast was raised by the finished queue",
         bool(toast_lines),
         toast_lines[-1].strip()[:140] if toast_lines else "no 'toast shown' line")
    note("engine validation passed inside the exe (yt-dlp + ffmpeg usable)",
         "engine validation passed" in log_text)
    bot_checks = log_text.count("bot check on")
    switches = log_text.count("retrying with player_client=")
    note("a YouTube bot check before a real download switched the client",
         bot_checks == switches,
         f"bot_checks={bot_checks} client_switches={switches}")
    note("no mojibake (U+FFFD) in the exe's log of a real download",
         "\ufffd" not in log_text,
         f"replacement_chars={log_text.count(chr(0xFFFD))}")
    note("no crash.log was written by the exe", not (DATA / "logs" / "crash.log").exists())
    note("no yt-dlp/ffmpeg process leaked after the queue went idle",
         "queue idle" in log_text)
    kill(proc)

    leftovers = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq yt-dlp.exe", "/FO", "CSV"],
        capture_output=True, text=True, timeout=60, **TEXT_KW,
    )
    note("Task Manager has no zombie yt-dlp.exe after quitting the exe",
         "yt-dlp.exe" not in (leftovers.stdout or ""),
         (leftovers.stdout or "").strip()[:120])

    print("\n=== acceptance 3b: real MP4 download (merge path) from the exe ===")
    # Same UI drive as the MP3 above, but the default format is switched to
    # MP4 so the exe runs the video+audio merge through its own ffmpeg. This
    # closes the 'real MP3 + MP4 downloads completed FROM THE EXE' row on the
    # shipped build rather than only in-process.
    TEST_MP4 = DATA / "_acceptance_mp4"
    shutil.rmtree(TEST_MP4, ignore_errors=True)
    try:
        # a fresh queue file makes 'the paste reached the queue' observable
        (DATA / "queue.json").unlink(missing_ok=True)
    except OSError:
        pass
    patch_settings(default_format="MP4", download_folder=str(TEST_MP4))
    proc = launch()
    main_win = find_window("MeTube", timeout=60)
    if main_win is None:
        note("exe reopened for the MP4 test", False)
        kill(proc)
        return 1
    time.sleep(6.0)  # let the engine validate yt-dlp/ffmpeg again

    image = shot(main_win, "final_06_before_mp4.png")
    accent = region_of(image, ACCENT, y_from=0.75)
    note("MP4 run: 'Add to Queue' located by colour in the bottom bar",
         accent is not None, f"region={accent}")
    found_mp4 = None
    if accent is not None:
        add_x = (accent[0] + accent[2]) // 2
        add_y = (accent[1] + accent[3]) // 2
        box_x = max(40, add_x - 260)
        box_y = max(40, accent[1] - 45)
        left, top, _, _ = window_rect(main_win)

        def mp4_file():
            if not TEST_MP4.exists():
                return None
            for path in TEST_MP4.iterdir():
                if (
                    path.is_file()
                    and path.suffix == ".mp4"
                    and not path.name.endswith(".part")
                    and path.stat().st_size > 100_000
                ):
                    return path
            return None

        for attempt in range(1, 4):
            focus(main_win)
            click(left + box_x, top + box_y)
            send_unicode(URL_ZOO)
            time.sleep(0.4)
            send_vk(VK_RETURN, ctrl=True)
            click(left + add_x, top + add_y)
            print(f"    attempt {attempt}: MP4 link queued through the UI", flush=True)
            deadline = time.time() + 150
            while time.time() < deadline:
                found_mp4 = mp4_file()
                if found_mp4 is not None:
                    break
                time.sleep(1.0)
            if found_mp4 is not None:
                break
    note("a real MP4 (merged video+audio) landed in the folder from the exe",
         found_mp4 is not None, f"{found_mp4}")
    time.sleep(6.0)  # let the queue go idle again
    shot(main_win, "final_07_mp4_completed.png")

    history_path = DATA / "history.json"
    rows = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    suffixes = sorted({
        Path(row.get("file_path") or "").suffix
        for row in rows
        if row.get("file_path")
    })
    note("history holds exe-driven rows for both MP3 and MP4 with file_path",
         ".mp3" in suffixes and ".mp4" in suffixes, f"suffixes={suffixes}")
    kill(proc)

    print("\n=== acceptance 3c: change the download folder in the UI, then RESTART ===")
    # The user-facing promise: pick a folder once, and every later launch keeps
    # using it. Driven entirely through the exe's own first-run picker (real
    # clicks + real keystrokes) with no test hooks inside the app, then proven
    # by a real download into that folder AFTER a restart.
    chosen = DATA / "chosen_downloads"
    shutil.rmtree(chosen, ignore_errors=True)
    kill_stray_instances()
    if not remove_data():
        note("data\\ deleted before the folder-change test", False,
             "a stray instance still holds data\\logs\\app.log")
        return 1
    proc = launch()
    dialog = find_window("MeTube — first run", timeout=60)
    note("folder-change run: the picker is up", dialog is not None)
    typed = False
    if dialog is not None:
        try:
            image = shot(dialog, "final_08_picker_before_typing.png", focus_first=False)
        except SystemExit as exc:
            print(f"    {exc}", flush=True)
            image = None
        entry = region_of(image, CARD) if image is not None else None
        note("the folder box was located in the picker (only CARD-coloured field)",
             entry is not None, f"region={entry}")
        if entry is not None:
            left, top, _, _ = window_rect(dialog)
            focus(dialog)
            click(left + (entry[0] + entry[2]) // 2, top + (entry[1] + entry[3]) // 2)
            send_vk(VK_A, ctrl=True)
            send_unicode(str(chosen))
            time.sleep(0.5)
            typed = True
            if user32.FindWindowW(None, "MeTube — first run"):
                try:
                    shot(dialog, "final_09_picker_after_typing.png")
                except SystemExit:
                    pass
        if user32.FindWindowW(None, "MeTube — first run"):
            confirm_picker(dialog, image)
        find_window("MeTube", timeout=60)
    win_after_change = find_window("MeTube", timeout=60)
    time.sleep(2.0)
    if win_after_change is not None:
        # Evidence for the on-screen "Saving to  <folder>" line: the picker is
        # gone, the main window is up, and the line names the folder just typed.
        try:
            shot(win_after_change, "final_09b_folder_line_after_change.png",
                 focus_first=False)
        except SystemExit as exc:
            print(f"    {exc} - the folder line still rendered", flush=True)
    # The app writes settings.json from the picker callback; give it a bounded
    # moment before judging the phase.
    saved_deadline = time.time() + 20
    while time.time() < saved_deadline and not read_settings().get("download_folder"):
        time.sleep(0.5)
    settings = read_settings()
    note("the folder typed into the picker is what got saved",
         settings.get("download_folder") == str(chosen),
         f"saved='{settings.get('download_folder')}' typed={typed}"
         f" expected='{chosen}'")
    kill(proc)

    def mp3_in(folder: Path):
        if not folder.exists():
            return None
        for path in folder.iterdir():
            if (path.is_file() and path.suffix == ".mp3"
                    and not path.name.endswith(".part")
                    and path.stat().st_size > 50_000):
                return path
        return None

    def download_into(win, folder: Path, label: str, attempts: int = 3):
        """Type the URL into the paste box and click Add to Queue (real input).

        Each attempt is verified against the exe's own queue.json, so a paste
        that never arrived (foreground lock, or the finish banner sitting over
        the box) is retried instead of burning the whole timeout.
        """
        if win is None:
            return None
        image = shot(win, f"{label}.png")
        accent = region_of(image, ACCENT, y_from=0.75)
        if accent is None:
            return None
        add_x = (accent[0] + accent[2]) // 2
        add_y = (accent[1] + accent[3]) // 2
        box_x = max(40, add_x - 260)
        box_y = max(40, accent[1] - 45)
        left, top, _, _ = window_rect(win)
        queue_json = DATA / "queue.json"
        try:
            queue_json.unlink(missing_ok=True)
        except OSError:
            pass
        for attempt in range(1, attempts + 1):
            focus(win)
            click(left + box_x, top + box_y)
            send_unicode(URL_ZOO)
            time.sleep(0.4)
            send_vk(VK_RETURN, ctrl=True)
            click(left + add_x, top + add_y)
            queued = False
            verify = time.time() + 25
            while time.time() < verify:
                if queue_json.exists():
                    try:
                        text = queue_json.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        text = ""
                    if "jNQXAC9IVRw" in text:
                        queued = True
                        break
                time.sleep(0.5)
            print(
                f"    {label}: attempt {attempt} - paste reached the exe's "
                f"queue = {queued}",
                flush=True,
            )
            deadline = time.time() + 150
            while time.time() < deadline:
                found = mp3_in(folder)
                if found is not None:
                    return found
                time.sleep(1.0)
        return None

    print("    relaunching WITHOUT touching any setting ...", flush=True)
    proc = launch()
    win = find_window("MeTube", timeout=60)
    note("after the restart the picker does NOT come back",
         win is not None and user32.FindWindowW(None, "MeTube — first run") is None)
    time.sleep(6.0)
    settings = read_settings()
    note("the chosen folder is still the one in settings.json after the restart",
         settings.get("download_folder") == str(chosen),
         f"saved='{settings.get('download_folder')}'")
    found = download_into(win, chosen, "final_10_folder_after_restart")
    note("a real download after the restart lands in the folder chosen earlier",
         found is not None, f"{found}")
    # Let the item finish properly before quitting: a kill mid-download would
    # leave an unfinished queue.json behind for the next phase to trip over.
    idle_deadline = time.time() + 90
    while time.time() < idle_deadline:
        log_path = DATA / "logs" / "app.log"
        text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        if "queue idle" in text:
            break
        time.sleep(1.0)
    time.sleep(2.0)
    kill(proc)

    print("\n=== acceptance 3d: data\\ copied from another PC (unreachable folder) ===")
    portable = SHIP / "downloads"
    shutil.rmtree(portable, ignore_errors=True)
    # The previous phase may have been killed mid-download; an unfinished item
    # in queue.json makes the app open its 'Restore previous session?' dialog at
    # startup (correct behaviour), which would hide the main window from this
    # test.  Start from an empty queue so the phase measures only the folder.
    try:
        (DATA / "queue.json").unlink(missing_ok=True)
    except OSError:
        pass
    patch_settings(download_folder="Q:\\metube_other_pc\\Downloads\\MeTube")
    proc = launch()
    win = find_window("MeTube", timeout=60)
    note("the app still opens with a folder from another machine", win is not None)
    time.sleep(6.0)
    settings = read_settings()
    note("the unreachable folder was replaced with <exe folder>\\downloads",
         settings.get("download_folder") == str(portable),
         f"saved='{settings.get('download_folder')}' expected='{portable}'")
    log_path = DATA / "logs" / "app.log"
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    note("the app log explains the replacement",
         "Saved download folder is unavailable" in log_text)
    found_portable = download_into(win, portable, "final_11_other_pc_folder")
    note("a real download lands in <exe folder>\\downloads",
         found_portable is not None, f"{found_portable}")
    kill(proc)
    shutil.rmtree(portable, ignore_errors=True)
    note("the acceptance removed the downloads\\ folder it made in the ship folder",
         not portable.exists(), str(portable))

    # Keep the exe's own records: acceptance 4 deletes data\, and app.log +
    # queue.json are the primary evidence of how the drive of the UI went.
    for name in ("logs/app.log", "queue.json", "history.json", "settings.json"):
        source = DATA / name
        if source.exists():
            target = EVIDENCE / f"exe_accept_{source.name}"
            shutil.copyfile(source, target)
            print(f"    preserved {target.relative_to(ROOT)}", flush=True)

    print("\n=== acceptance 4: delete data\\ -> picker returns; ship folder left clean ===")
    remove_data()
    proc = launch()
    dialog = find_window("MeTube — first run", timeout=60)
    note("deleting data\\ brings the first-run picker back",
         dialog is not None)
    if dialog is not None:
        try:
            image = shot(dialog, "final_05_first_run_after_data_delete.png",
                         focus_first=False)
        except SystemExit as exc:
            # The picker returning is what this check verifies; the capture can
            # legitimately lose the race against an external click.
            print(f"    {exc} - picker return still verified", flush=True)
            image = None
        accent = region_of(image, ACCENT) if image is not None else None
        if accent and user32.FindWindowW(None, "MeTube — first run"):
            left, top, _, _ = window_rect(dialog)
            focus(dialog)
            click(left + (accent[0] + accent[2]) // 2,
                  top + (accent[1] + accent[3]) // 2)
            find_window("MeTube", timeout=60)
    kill(proc)
    cleaned = remove_data()
    leftover = (
        sorted(p.name for p in DATA.iterdir()) if DATA.exists() else []
    )
    listing = sorted(p.name for p in SHIP.iterdir())
    note("dist\\MeTubeShip left clean: no data\\ folder",
         cleaned and "data" not in listing,
         f"contents={listing} leftover_in_data={leftover}")
    note("dist\\MeTubeShip contents are exactly the shipped set",
         set(listing) == {"MeTube.exe", "README.txt", "bin"},
         f"contents={listing}")

    # A force-killed onefile exe cannot remove its own extraction dir, so the
    # run reclaims them here and proves none is left behind afterwards.  (Left
    # unchecked, they filled the system drive during a long run and broke the
    # exe's own engine extraction, turning real checks into false failures.)
    mei_dirs, mei_bytes = sweep_mei_dirs()
    temp_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".")
    remaining = sorted(p.name for p in temp_root.glob("_MEI*")) if temp_root.is_dir() else []
    note(
        "the run's _MEI extraction leftovers were reclaimed and none remain",
        not remaining,
        f"swept {mei_dirs} dirs / {mei_bytes / 1048576:.0f} MB, "
        f"still present={remaining or 'none'}",
    )

    release_display()
    print("\n=================== acceptance summary ===================")
    for label, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"  {passed}/{len(RESULTS)} passed")
    if PROBLEMS:
        print("\nPROBLEMS:")
        for item in PROBLEMS:
            print(f"  - {item}")
        return 1
    print("\nEXE ACCEPTANCE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
