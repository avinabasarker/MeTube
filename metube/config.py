"""Central path resolution.

This module is the ONE place that decides where the app lives and where its
data lives.  Nothing else in the codebase may build a ``data`` path itself
(regression guarantee B12: two competing data folders).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Project root when running from source (this file is <root>/metube/config.py).
PROJECT_ROOT = Path(__file__).resolve().parent.parent

SINGLE_INSTANCE_MUTEX = "MeTube_SingleInstance_Mutex"
SINGLE_INSTANCE_EVENT = "MeTube_ShowInstance_Event"

_cached_data_dir: Path | None = None
_cached_data_dir_reason = ""


def is_frozen() -> bool:
    """True when running from a PyInstaller build."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Folder containing MeTube.exe (frozen) or the project root (source)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def resource_path(relative: str) -> Path:
    """Locate a file bundled *inside* the exe, or in the source tree.

    PyInstaller onefile unpacks bundled data into ``sys._MEIPASS``; running
    from source there is no such directory, so fall back to the project root.
    """
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / relative
    return PROJECT_ROOT / relative


def _is_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    probe = directory / ".metube_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _resolve_data_dir() -> tuple[Path, str]:
    override = os.environ.get("METUBE_DATA_DIR")
    if override:
        return Path(override).expanduser(), "METUBE_DATA_DIR override"
    primary = app_dir() / "data"
    if _is_writable(primary):
        return primary, "app_dir/data"
    fallback_root = Path(os.environ.get("APPDATA") or Path.home())
    fallback = fallback_root / "MeTube"
    try:
        fallback.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return fallback, "appdata fallback (app_dir not writable)"


def data_dir() -> Path:
    """Resolved, cached data directory."""
    global _cached_data_dir, _cached_data_dir_reason
    if _cached_data_dir is None:
        _cached_data_dir, _cached_data_dir_reason = _resolve_data_dir()
    return _cached_data_dir


def data_dir_reason() -> str:
    data_dir()  # force resolution
    return _cached_data_dir_reason


def settings_path() -> Path:
    return data_dir() / "settings.json"


def queue_path() -> Path:
    return data_dir() / "queue.json"


def history_path() -> Path:
    return data_dir() / "history.json"


def thumbs_dir() -> Path:
    return data_dir() / "thumbs"


def logs_dir() -> Path:
    return data_dir() / "logs"


def data_bin_dir() -> Path:
    """Auto-downloaded engine binaries."""
    return data_dir() / "bin"


def bundled_bin_dir() -> Path:
    """Shipped engine binaries, next to MeTube.exe."""
    return app_dir() / "bin"


def default_download_folder() -> Path:
    return Path.home() / "Downloads" / "MeTube"


def resolve_download_folder(folder: str | Path) -> Path:
    """Return the absolute download folder for whatever the user supplied.

    A relative value (``downloads``, ``.media``, typed into the Settings box)
    must never reach yt-dlp as a relative ``-o`` template: yt-dlp resolves that
    against its own working directory and drops a leading dot, so the files
    land in a folder the user never chose while the chosen folder stays empty
    (measured: ``.e2e\\ladder\\rel`` -> ``e2e\\ladder\\rel``).  Relative paths
    are therefore read as relative to the MeTube folder, which is where a
    portable copy keeps everything else.
    """
    path = Path(str(folder or "").strip()).expanduser()
    if not str(path):
        return default_download_folder()
    if not path.is_absolute():
        path = app_dir() / path
    return Path(os.path.normpath(str(path)))


def folder_is_usable(directory: Path | str) -> bool:
    """True when ``directory`` exists (or can be created) and is writable.

    Used before the app commits to a download folder, so a path that cannot
    work on this machine is caught while the user is still looking at the
    Settings screen instead of when a download is already running.
    """
    return _is_writable(Path(directory))


def portable_download_folder() -> Path:
    """The download folder that travels with the app.

    Used when the remembered folder cannot be reached - the classic case is a
    ``data\\settings.json`` copied from another PC, whose folder was on a drive
    letter or user profile that does not exist here. The app stays usable and
    keeps its downloads inside its own folder instead of failing every
    download. Falls back to the data folder when the app folder is read-only
    (e.g. run from a CD or a locked-down Program Files).
    """
    candidate = app_dir() / "downloads"
    if _is_writable(candidate):
        return candidate
    return data_dir() / "downloads"


def crash_log_path() -> Path:
    return logs_dir() / "crash.log"
