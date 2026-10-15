"""Shared helpers: filename sanitising, cross-drive safe moves, URL parsing.

There is exactly ONE sanitizer in this codebase (regression B: "one
sanitizer"); the outtmpl builder, the collision pre-scan and the fallback
glob all call :func:`sanitize_filename`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

# --------------------------------------------------------------------------
# subprocess helpers
# --------------------------------------------------------------------------

NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def no_window_kwargs() -> dict:
    """Extra Popen kwargs that stop console windows flashing up on Windows."""
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = si
    return kwargs


# --------------------------------------------------------------------------
# filenames
# --------------------------------------------------------------------------

_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")

MAX_FILENAME_BASE = 100

MEDIA_EXTENSIONS = (
    ".mp3",
    ".m4a",
    ".mp4",
    ".webm",
    ".mkv",
    ".opus",
    ".ogg",
    ".wav",
    ".aac",
    ".flac",
)

JUNK_EXTENSIONS = (".part", ".ytdl", ".tmp", ".temp")


def sanitize_filename(name: str, max_length: int = MAX_FILENAME_BASE) -> str:
    """Strip characters Windows forbids and cap the length."""
    if not name:
        return "video"
    cleaned = _INVALID_CHARS.sub("", str(name))
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    cleaned = cleaned.rstrip(". ")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(". ")
    return cleaned or "video"


def unique_path(folder: Path, base: str, suffix: str) -> Path:
    """Return a non-colliding ``folder\\base.suffix`` (``base (1).suffix`` ...)."""
    folder = Path(folder)
    candidate = folder / f"{base}{suffix}"
    index = 1
    while candidate.exists():
        candidate = folder / f"{base} ({index}){suffix}"
        index += 1
    return candidate


# --------------------------------------------------------------------------
# cross-drive safe file operations  (regression B3: os.replace WinError 17)
# --------------------------------------------------------------------------


def safe_move(src: str | os.PathLike, dst: str | os.PathLike) -> Path:
    """Move ``src`` to ``dst`` even across volumes.

    ``os.replace`` raises WinError 17 across volumes, so we copy to a sibling
    ``.tmp`` on the destination volume, atomically replace, then drop the
    source.
    """
    src_path = Path(src)
    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    if src_path.resolve() == dst_path.resolve():
        return dst_path

    tmp_path = dst_path.with_name(dst_path.name + ".tmp")
    try:
        shutil.copy2(src_path, tmp_path)
        os.replace(tmp_path, dst_path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    try:
        src_path.unlink()
    except OSError:
        pass
    return dst_path


def atomic_write_text(path: str | os.PathLike, text: str) -> None:
    """Write a file atomically via a same-directory ``.tmp`` + os.replace."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)


def read_json(path: str | os.PathLike, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_json(path: str | os.PathLike, data) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------
# YouTube URLs
# --------------------------------------------------------------------------

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_SPLIT_RE = re.compile(r"[\s,;]+")


def split_links(text: str) -> list[str]:
    """Split pasted text on commas / newlines / semicolons / whitespace."""
    if not text:
        return []
    return [part.strip() for part in _SPLIT_RE.split(text) if part.strip()]


def extract_video_id(url: str) -> str | None:
    """Return the 11-character YouTube video id, or None."""
    if not url:
        return None
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return None

    host = (parsed.netloc or "").lower()
    path = parsed.path or ""

    if host.endswith("youtu.be"):
        first = path.strip("/").split("/")[0]
        return first if VIDEO_ID_RE.match(first) else None

    query = parse_qs(parsed.query)
    for key in ("v", "vi"):
        values = query.get(key)
        if values and VIDEO_ID_RE.match(values[0]):
            return values[0]

    segments = [seg for seg in path.split("/") if seg]
    if len(segments) >= 2 and segments[0] in ("shorts", "live", "embed", "v", "watch"):
        if VIDEO_ID_RE.match(segments[1]):
            return segments[1]
    return None


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def is_playlist_url(url: str) -> bool:
    """True for a playlist URL with no individual video attached."""
    if not url:
        return False
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return False
    query = parse_qs(parsed.query)
    has_list = bool(query.get("list"))
    return has_list and extract_video_id(url) is None


# --------------------------------------------------------------------------
# misc
# --------------------------------------------------------------------------


def humanize_duration(seconds) -> str:
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return "--:--"
    if total < 0:
        return "--:--"
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def free_space_bytes(path: str | os.PathLike) -> int | None:
    """Free bytes on the volume that holds ``path`` (None when unknown).

    Used before a download or an engine bootstrap starts, so the user gets a
    sentence they can act on instead of a raw ``[Errno 28]`` from deep inside
    a tool (measured the hard way: a full C: made yt-dlp and the app fail with
    messages nobody could act on).
    """
    try:
        return int(shutil.disk_usage(Path(path)).free)
    except OSError:
        return None


def human_mb(size: int) -> str:
    """Whole megabytes for user-facing text."""
    return f"{max(0, int(size)) // (1024 * 1024)} MB"


def open_in_explorer(path: str) -> None:
    """Reveal a file in Explorer with it selected (never silently no-op)."""
    target = Path(path)
    if os.name == "nt":
        subprocess.Popen(["explorer", "/select,", str(target)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target.parent)])


def open_file(path: str) -> None:
    target = Path(path)
    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])
