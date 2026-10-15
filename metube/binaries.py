"""Engine binaries: resolution order, validation and in-app bootstrap.

Resolution order (Section 3):
  1. <app_dir>\\bin\\<name>
  2. <data_dir>\\bin\\<name>
  3. missing -> bootstrap or manual instructions
"""

from __future__ import annotations

import errno
import http.client
import logging
import os
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from . import config
from .utils import NO_WINDOW, human_mb, free_space_bytes, safe_move

log = logging.getLogger("metube.binaries")

YTDLP_NAME = "yt-dlp.exe"
FFMPEG_NAME = "ffmpeg.exe"
FFPROBE_NAME = "ffprobe.exe"
BINARY_NAMES = (YTDLP_NAME, FFMPEG_NAME, FFPROBE_NAME)

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
# The yt-dlp fork of FFmpeg-Builds keeps a rolling "latest" tag with stable
# asset names; BtbN's rolling tag was retired, so its old URL now 404s (B4:
# GitHub release assets only, verified live).
FFMPEG_URL = (
    "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)

_USER_AGENT = "MeTube/2.0 (+https://example.invalid/metube)"

# One 200 MB zip over a busy CDN will occasionally see a 5xx or a dropped
# socket; those are worth another try, a bad URL or a TLS failure is not.
DOWNLOAD_ATTEMPTS = 4
RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}
RETRY_BACKOFF_SECONDS = 2.0

MANUAL_INSTRUCTIONS = (
    'Create a folder named "bin" next to MeTube.exe and place these three '
    "files inside it, named exactly: yt-dlp.exe, ffmpeg.exe, ffprobe.exe.\n\n"
    f"Get them from:\n  yt-dlp: {YTDLP_URL}\n  ffmpeg: {FFMPEG_URL}\n\n"
    "Then restart MeTube."
)


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------
def _candidates(name: str) -> list[Path]:
    return [config.bundled_bin_dir() / name, config.data_bin_dir() / name]


def resolve_binary(name: str) -> Path | None:
    for candidate in _candidates(name):
        if candidate.is_file():
            return candidate
    return None


def resolve_all() -> dict[str, Path | None]:
    return {name: resolve_binary(name) for name in BINARY_NAMES}


def is_complete() -> bool:
    return all(resolve_binary(name) is not None for name in BINARY_NAMES)


def ffmpeg_location() -> str:
    """Directory handed to yt-dlp's --ffmpeg-location."""
    found = resolve_binary(FFMPEG_NAME)
    if found is not None:
        return str(found.parent)
    return str(config.bundled_bin_dir())


def _run(exe: Path, args: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            [str(exe), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def validate_all() -> dict[str, tuple[bool, str]]:
    """Run the real version commands; non-zero exit / missing file = invalid."""
    results: dict[str, tuple[bool, str]] = {}
    checks = {
        YTDLP_NAME: ["--version"],
        FFMPEG_NAME: ["-version"],
        FFPROBE_NAME: ["-version"],
    }
    for name, args in checks.items():
        path = resolve_binary(name)
        if path is None:
            results[name] = (False, "not found")
            continue
        code, output = _run(path, args)
        first = output.strip().splitlines()[0] if output.strip() else ""
        results[name] = (code == 0, first)
    return results


# --------------------------------------------------------------------------
# download + bootstrap
# --------------------------------------------------------------------------
def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in RETRYABLE_HTTP_CODES
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, ssl.SSLCertVerificationError):
            return False
        return True
    return isinstance(
        exc, (socket.timeout, http.client.HTTPException, ConnectionError, TimeoutError)
    )


def _download(url: str, target: Path, on_progress: Callable[[str], None]) -> None:
    """Download ``url`` to ``target``, retrying transient network failures."""
    first_error: BaseException | None = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            _download_once(url, target, on_progress)
            return
        except Exception as exc:  # noqa: BLE001 - re-raised below when final
            if first_error is None:
                first_error = exc
            if attempt == DOWNLOAD_ATTEMPTS or not _is_retryable(exc):
                raise
            delay = RETRY_BACKOFF_SECONDS * attempt
            log.warning(
                "download of %s failed (attempt %d/%d): %s; retrying in %.0fs",
                url,
                attempt,
                DOWNLOAD_ATTEMPTS,
                exc,
                delay,
            )
            on_progress(f"Download interrupted, retrying ({attempt + 1}/{DOWNLOAD_ATTEMPTS})…")
            time.sleep(delay)
    raise first_error  # pragma: no cover - loop always returns or raises


def _download_once(url: str, target: Path, on_progress: Callable[[str], None]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response, open(target, "wb") as fh:
        total = int(response.headers.get("Content-Length") or 0)
        read = 0
        on_progress(f"Downloading {target.name}…")
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            fh.write(chunk)
            read += len(chunk)
            if total:
                on_progress(
                    f"Downloading {target.name}… {read * 100 // total}%"
                )


def _extract_ffmpeg(zip_path: Path, dest_dir: Path) -> None:
    """Extract ffmpeg.exe/ffprobe.exe by basename, never assuming a layout."""
    wanted = {FFMPEG_NAME, FFPROBE_NAME}
    found: set[str] = set()
    with zipfile.ZipFile(zip_path) as archive:
        for entry in archive.namelist():
            base = os.path.basename(entry)
            if base in wanted and base not in found:
                dest_dir.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as src, open(dest_dir / base, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                found.add(base)
    missing = wanted - found
    if missing:
        raise RuntimeError(f"Archive did not contain: {', '.join(sorted(missing))}")


# The gpl zip is ~200 MB and unpacks to ~340 MB of exe, so a bootstrap that
# starts with less than this free cannot finish.
MIN_BOOTSTRAP_FREE_BYTES = 400 * 1024 * 1024
# Room for the zip itself plus a little slack, in the system temp directory.
ZIP_FREE_BYTES = 300 * 1024 * 1024


def download_engine_into(
    dest_dir: Path, on_progress: Callable[[str], None]
) -> None:
    """Download yt-dlp + ffmpeg into ``dest_dir`` using cross-drive-safe moves."""
    dest_dir = Path(dest_dir)
    free = free_space_bytes(dest_dir if dest_dir.exists() else dest_dir.parent)
    if free is not None and free < MIN_BOOTSTRAP_FREE_BYTES:
        raise RuntimeError(
            "Not enough free disk space: "
            f"{human_mb(free)} left on {dest_dir.drive or dest_dir}, the engine "
            f"needs about {human_mb(MIN_BOOTSTRAP_FREE_BYTES)}. Free some space, "
            "then use Settings -> Re-download components."
        )
    temp_dir = Path(tempfile.mkdtemp(prefix="metube_boot_"))
    # The zip lands in the system temp directory first, which is usually on a
    # different volume from the app - check that one too.
    temp_free = free_space_bytes(temp_dir)
    if temp_free is not None and temp_free < ZIP_FREE_BYTES:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(
            "Not enough free disk space in the temporary folder "
            f"({human_mb(temp_free)} left on {temp_dir.drive or temp_dir}): the "
            f"download needs about {human_mb(ZIP_FREE_BYTES)} there. Free some "
            "space, then use Settings -> Re-download components."
        )
    try:
        ytdlp_tmp = temp_dir / YTDLP_NAME
        _download(YTDLP_URL, ytdlp_tmp, on_progress)
        safe_move(ytdlp_tmp, dest_dir / YTDLP_NAME)

        zip_tmp = temp_dir / "ffmpeg.zip"
        _download(FFMPEG_URL, zip_tmp, on_progress)
        on_progress("Extracting ffmpeg…")
        extract_dir = temp_dir / "extract"
        _extract_ffmpeg(zip_tmp, extract_dir)
        for name in (FFMPEG_NAME, FFPROBE_NAME):
            safe_move(extract_dir / name, dest_dir / name)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def bootstrap(on_progress: Callable[[str], None], on_done: Callable[[bool, str], None]) -> threading.Thread:
    """Run the bootstrap on a daemon thread. Never blocks or kills window setup."""

    def _worker() -> None:
        ok = False
        message = ""
        try:
            on_progress("Preparing engine…")
            download_engine_into(config.data_bin_dir(), on_progress)
            results = validate_all()
            ok = all(passed for passed, _ in results.values())
            message = "Engine ready" if ok else "One or more engine files failed validation."
            log.info("bootstrap finished ok=%s results=%s", ok, results)
        except Exception as exc:  # noqa: BLE001 - reported to the UI
            if isinstance(exc, urllib.error.HTTPError):
                message = f"Download failed (HTTP {exc.code})."
            elif isinstance(exc, ssl.SSLError):
                message = "Download failed (TLS/SSL error)."
            elif isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
                message = (
                    "Not enough free disk space to unpack the engine. Free some "
                    "space, then use Settings -> Re-download components."
                )
            elif isinstance(exc, OSError):
                message = f"Disk/network error: {exc}"
            else:
                message = str(exc) or exc.__class__.__name__
            log.error("bootstrap failed: %s", message, exc_info=True)
        finally:
            try:
                on_done(ok, message)
            except Exception:  # noqa: BLE001
                log.exception("bootstrap on_done callback failed")

    thread = threading.Thread(target=_worker, name="BootstrapThread", daemon=True)
    thread.start()
    return thread
