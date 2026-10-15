"""yt-dlp engine: command construction, execution and stdout parsing.

The stdout contract (verified against yt-dlp 2026.08.19) with
``--quiet --no-warnings`` is:

    PROG|  51.6%|  24.55MiB/s|00:00
    <absolute path of the final file>

stderr is captured separately and never merged into stdout; it is used for
error classification only.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import binaries, config
from .models import QUALITY_HEIGHT, QueueItem
from .utils import (
    JUNK_EXTENSIONS,
    MEDIA_EXTENSIONS,
    NO_WINDOW,
    canonical_url,
    safe_move,
    sanitize_filename,
    unique_path,
)

log = logging.getLogger("metube.downloader")


def decode_output(data: bytes) -> str:
    """Decode a line of yt-dlp output without losing characters.

    yt-dlp on Windows writes messages such as "Sign in to confirm you’re not a
    bot" with a single 0x92 byte (the ANSI code page's curly apostrophe) even
    when ``PYTHONIOENCODING=utf-8`` is set, because the pipe was not opened by
    Python.  Decoding that strictly as UTF-8 produced U+FFFD, which hid the
    real message from the classifier and put a mojibake character on the queue
    card.  Try UTF-8 first, then fall back to the code page.
    """
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


# Typographic punctuation (and the replacement character, in case a stream was
# already damaged) is folded to ASCII before the classifiers match, so a
# bot-check sentence is recognised whatever the pipe did to its apostrophe.
_PUNCT_FOLD = str.maketrans(
    {
        "\u2019": "'",
        "\u2018": "'",
        "\u00b4": "'",
        "\ufffd": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
    }
)


def _fold(text: str) -> str:
    """Lower-case text with typographic punctuation normalised to ASCII."""
    return (text or "").translate(_PUNCT_FOLD).lower()

PROG_PREFIX = "PROG|"
PROGRESS_TEMPLATE = (
    "PROG|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s"
)
EXPECTED_EXT = {"MP3": ".mp3", "M4A": ".m4a", "MP4": ".mp4"}


# --------------------------------------------------------------------------
# command construction
# --------------------------------------------------------------------------
def _base_argv() -> list[str]:
    """Just the yt-dlp executable.

    The URL is added exactly once, at the *end* of the completed argument list.
    Passing it in the middle as well makes yt-dlp treat it as a second input
    and download the same video twice (verified: `--print` fired twice), which
    doubled every download's work.
    """
    ytdlp = binaries.resolve_binary(binaries.YTDLP_NAME)
    if ytdlp is None:
        raise FileNotFoundError("yt-dlp.exe not found")
    return [str(ytdlp)]


def build_command(item: QueueItem, folder: Path, player_client: str = "") -> tuple[list[str], str]:
    """Return (argv, base_title) for one download.

    The download folder is read at the moment the download starts, never
    cached (regression B5).  ``player_client`` overrides YouTube's client for
    this attempt only; empty means "use yt-dlp's own default clients".
    """
    # yt-dlp resolves a relative ``-o`` template against its own working
    # directory (and drops a leading dot), so the folder is made absolute here
    # as well - the downloader is safe to call from anywhere.
    folder = config.resolve_download_folder(folder)
    folder.mkdir(parents=True, exist_ok=True)

    raw_title = item.title or item.video_id or "video"
    title = sanitize_filename(raw_title)
    ext = EXPECTED_EXT.get(item.fmt, ".mp3")
    target = unique_path(folder, title, ext)
    base_title = target.stem

    argv = _base_argv()
    argv += [
        "--quiet",
        "--no-warnings",
        "--progress",
        "--newline",
        "--progress-template",
        PROGRESS_TEMPLATE,
        "--print",
        "after_move:%(filepath)s",
        "--windows-filenames",
        "--trim-filenames",
        "100",
        "--no-mtime",
        "--no-playlist",
        "--ffmpeg-location",
        binaries.ffmpeg_location(),
        "-o",
        str(folder / f"{base_title}.%(ext)s"),
    ]

    if item.fmt == "MP4":
        height = QUALITY_HEIGHT.get(item.quality)
        if height:
            argv += [
                "-f",
                f"bestvideo*[height<={height}]+bestaudio/best[height<={height}]/best",
            ]
        else:
            argv += ["-f", "bestvideo*+bestaudio/best"]
        argv += ["-S", "res,codec:h264:m4a", "--merge-output-format", "mp4"]
    elif item.fmt == "MP3":
        argv += [
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "320K",
            "--embed-thumbnail",
            "--embed-metadata",
            "--convert-thumbnails",
            "jpg",
        ]
    else:  # M4A
        argv += [
            "-x",
            "--audio-format",
            "m4a",
            "--embed-thumbnail",
            "--embed-metadata",
            "--convert-thumbnails",
            "jpg",
        ]

    argv.append(item.url)
    return _with_client(argv, player_client), base_title


# --------------------------------------------------------------------------
# result parsing helpers
# --------------------------------------------------------------------------
def find_fallback_file(folder: Path, base_title: str) -> str:
    """Glob for the produced media file, ignoring .part/.ytdl/.tmp junk."""
    folder = Path(folder)
    best: Optional[Path] = None
    try:
        entries = list(folder.iterdir())
    except OSError:
        return ""
    for entry in entries:
        if not entry.is_file():
            continue
        if entry.suffix.lower() in JUNK_EXTENSIONS:
            continue
        if entry.name.endswith(".tmp"):
            continue
        if entry.suffix.lower() not in MEDIA_EXTENSIONS:
            continue
        if not entry.stem.startswith(base_title):
            continue
        if best is None or entry.stat().st_mtime > best.stat().st_mtime:
            best = entry
    return str(best) if best else ""


_BOT_MARKERS = (
    "http error 429",
    "too many requests",
    "sign in to confirm you're not a bot",
    "sign in to confirm you’re not a bot",
    "confirm you're not a bot",
    "confirm you’re not a bot",
)

_PERMANENT_MARKERS = (
    "is not a valid url",
    "unsupported url",
    "incomplete youtube id",
    "private video",
    "this video is private",
    "video unavailable",
    "this video is unavailable",
    "has been removed",
    "has been deleted",
    "account has been terminated",
    "not available in your country",
    "video is not available",
    "no video formats found",
    "requested format is not available",
    "this live event will begin",
    "premieres in",
    "this live stream recording is not available",
    "members-only",
    "no such file or directory",
)

_TRANSIENT_MARKERS = (
    "timed out",
    "timeout",
    "temporary failure",
    "connection reset",
    "connection aborted",
    "connection refused",
    "unable to connect",
    "unable to download",
    "read timed out",
    "network is unreachable",
    "http error 5",
    "got error 5",
    "ssl",
    "tunnel connection failed",
    "remote end closed connection",
)

BOT = "bot"
PERMANENT = "permanent"
TRANSIENT = "transient"

# YouTube's default (web) clients answer an increasing share of requests with
# "Sign in to confirm you're not a bot" instead of media or metadata.  The
# request is fine and the link is fine - YouTube just wants a different
# ``player_client`` to ask.  These are the clients that still serve video
# without cookies, in the order they are tried; every step also keeps working
# if YouTube later blocks one of them.
BOT_CLIENT_FALLBACKS = ("android", "tv_embedded")


def _with_client(argv: list[str], player_client: str) -> list[str]:
    """Insert ``--extractor-args youtube:player_client=...`` before the URL.

    Every yt-dlp command in this module ends with the URL, so this is the one
    place that knows how to add a client override.
    """
    if not player_client:
        return list(argv)
    return (
        list(argv[:-1])
        + ["--extractor-args", f"youtube:player_client={player_client}"]
        + [argv[-1]]
    )


def classify_failure(stderr: str) -> tuple[str, str]:
    """Return (kind, human_reason)."""
    text = _fold(stderr)
    reason = extract_error_message(stderr)

    for marker in _BOT_MARKERS:
        if marker in text:
            return BOT, reason or "YouTube asked us to prove we are not a bot"
    for marker in _PERMANENT_MARKERS:
        if marker in text:
            return PERMANENT, reason
    for marker in _TRANSIENT_MARKERS:
        if marker in text:
            return TRANSIENT, reason
    return TRANSIENT, reason or "download failed"


def extract_error_message(stderr: str) -> str:
    """Pull one short, actionable sentence out of yt-dlp's stderr.

    yt-dlp wraps failures in a lot of machinery -- ``(caused by ...)`` chains,
    a bug-report footer, and a version reminder -- none of which belongs on a
    queue card.  Keep the first clause and cap the length.
    """
    lines = [ln.strip() for ln in (stderr or "").splitlines() if ln.strip()]
    message = ""
    for line in reversed(lines):
        if "ERROR:" in line:
            message = line.split("ERROR:", 1)[1].strip()
            break
    if not message and lines:
        message = lines[-1]

    for cut in (
        "please report this issue",
        "; please report",
        "(caused by",
        "Confirm you are on the latest version",
    ):
        message = message.split(cut, 1)[0]
    message = " ".join(message.split()).strip(" ;,.")
    if len(message) > 180:
        message = message[:177].rstrip() + "…"
    return message


# --------------------------------------------------------------------------
# running a download
# --------------------------------------------------------------------------
@dataclass
class DownloadResult:
    ok: bool
    file_path: str = ""
    base_title: str = ""
    exit_code: int = -1
    stderr: str = ""
    cancelled: bool = False
    player_client: str = ""
    filepaths_seen: list[str] = field(default_factory=list)


def _subprocess_env() -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_download(
    item: QueueItem,
    folder: Path,
    *,
    player_client: str = "",
    on_progress: Callable[[str, str, str], None] | None = None,
    on_filepath: Callable[[str], None] | None = None,
    register_proc: Callable[[subprocess.Popen], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> DownloadResult:
    """Run one yt-dlp download to completion (or cancellation)."""
    argv, base_title = build_command(item, folder, player_client)
    log.info(
        "download start: %s -> %s%s",
        item.url,
        folder,
        f"  (player_client={player_client})" if player_client else "",
    )
    log.debug("argv: %s", argv)

    creationflags = NO_WINDOW
    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            # Bytes, not text: yt-dlp mixes UTF-8 and ANSI code-page bytes in
            # the same pipe (see decode_output), and a single 0x92 would
            # otherwise turn a whole bot-check message into mojibake.  Line
            # buffering is not available in binary mode; both readers iterate
            # whole lines anyway.
            creationflags=creationflags,
            env=_subprocess_env(),
        )
    except OSError as exc:
        log.error("could not launch yt-dlp: %s", exc)
        return DownloadResult(ok=False, exit_code=-1, stderr=f"ERROR: {exc}")

    if register_proc is not None:
        register_proc(proc)

    filepaths: list[str] = []
    stderr_lines: list[str] = []

    def _read_stdout() -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = decode_output(raw).rstrip("\r\n")
            if not line:
                continue
            if line.startswith(PROG_PREFIX):
                parts = line.split("|")
                percent = parts[1].strip() if len(parts) > 1 else ""
                speed = parts[2].strip() if len(parts) > 2 else ""
                eta = parts[3].strip() if len(parts) > 3 else ""
                if on_progress is not None:
                    on_progress(percent, speed, eta)
            else:
                filepaths.append(line.strip())
                if on_filepath is not None:
                    on_filepath(line.strip())

    def _read_stderr() -> None:
        assert proc.stderr is not None
        for raw in proc.stderr:
            line = decode_output(raw).rstrip("\r\n")
            if line:
                stderr_lines.append(line)

    out_thread = threading.Thread(target=_read_stdout, name="ytdlp-stdout", daemon=True)
    err_thread = threading.Thread(target=_read_stderr, name="ytdlp-stderr", daemon=True)
    out_thread.start()
    err_thread.start()

    proc.wait()
    out_thread.join(timeout=5)
    err_thread.join(timeout=5)

    stderr_text = "\n".join(stderr_lines)
    cancelled = bool(should_cancel and should_cancel())

    result = DownloadResult(
        ok=proc.returncode == 0 and not cancelled,
        base_title=base_title,
        exit_code=proc.returncode if proc.returncode is not None else -1,
        stderr=stderr_text,
        cancelled=cancelled,
        player_client=player_client,
        filepaths_seen=list(filepaths),
    )

    if result.ok:
        candidate = ""
        for entry in reversed(filepaths):
            if Path(entry).is_file():
                candidate = entry
                break
        if not candidate and filepaths:
            candidate = filepaths[-1] if Path(filepaths[-1]).is_file() else ""
        if not candidate:
            candidate = find_fallback_file(folder, base_title)
        result.file_path = candidate
        if not candidate:
            result.ok = False
            result.stderr = (stderr_text + "\nERROR: file was not produced").strip()
        else:
            log.info("download finished: %s", candidate)
    else:
        log.warning(
            "download failed (exit=%s cancelled=%s): %s",
            result.exit_code,
            cancelled,
            stderr_text[-500:],
        )
    return result


# --------------------------------------------------------------------------
# metadata + playlist (low level)
# --------------------------------------------------------------------------
@dataclass
class YtdlpOutput:
    """Return code plus already-decoded streams of a one-shot yt-dlp call."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


def _run_ytdlp(argv: list[str], timeout: int) -> YtdlpOutput:
    proc = subprocess.run(
        argv,
        capture_output=True,
        timeout=timeout,
        creationflags=NO_WINDOW,
        env=_subprocess_env(),
    )
    return YtdlpOutput(
        returncode=proc.returncode,
        stdout=decode_output(proc.stdout or b""),
        stderr=decode_output(proc.stderr or b""),
    )


def _run_ytdlp_with_clients(argv: list[str], timeout: int) -> YtdlpOutput:
    """One-shot yt-dlp call that steps down the client ladder on a bot check.

    Metadata and playlist expansion hit the same bot check as a download; a
    title lookup that gives up would also rename the file after the bare video
    id, so the fallback matters here too.  A non-bot failure is returned as-is
    - switching clients cannot fix a private or deleted video.
    """
    last: YtdlpOutput | None = None
    for client in ("",) + BOT_CLIENT_FALLBACKS:
        proc = _run_ytdlp(_with_client(argv, client), timeout)
        if proc.returncode == 0:
            if client:
                log.info("yt-dlp succeeded with player_client=%s", client)
            return proc
        last = proc
        if classify_failure(proc.stderr or "")[0] != BOT:
            return proc
        log.info(
            "yt-dlp bot check with player_client=%s - trying the next client",
            client or "default",
        )
    assert last is not None
    return last


def probe_metadata(url: str, timeout: int = 60) -> dict:
    """``--dump-json --no-playlist`` for a single video."""
    ytdlp = binaries.resolve_binary(binaries.YTDLP_NAME)
    if ytdlp is None:
        raise FileNotFoundError("yt-dlp.exe not found")
    argv = [
        str(ytdlp),
        "--dump-json",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "--no-mtime",
        url,
    ]
    proc = _run_ytdlp_with_clients(argv, timeout)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "metadata lookup failed").strip()[-300:])
    line = (proc.stdout or "").strip().splitlines()
    if not line:
        raise RuntimeError("empty metadata response")
    return json.loads(line[0])


def expand_playlist(url: str, timeout: int = 120) -> list[str]:
    """``--flat-playlist --print id`` -> list of 11-char video ids."""
    ytdlp = binaries.resolve_binary(binaries.YTDLP_NAME)
    if ytdlp is None:
        raise FileNotFoundError("yt-dlp.exe not found")
    argv = [
        str(ytdlp),
        "--flat-playlist",
        "--print",
        "id",
        "--quiet",
        "--no-warnings",
        url,
    ]
    proc = _run_ytdlp_with_clients(argv, timeout)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "playlist expansion failed").strip()[-300:])
    ids: list[str] = []
    for line in (proc.stdout or "").splitlines():
        value = line.strip()
        if value and value not in ids:
            ids.append(value)
    return ids


def playlist_url_for(video_ids: list[str]) -> str:  # pragma: no cover - helper
    return canonical_url(video_ids[0]) if video_ids else ""


def download_thumbnail(url: str, destination: Path) -> bool:
    """Cache a thumbnail image locally; never raises."""
    if not url:
        return False
    try:
        import urllib.request

        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp = destination.with_name(destination.name + ".tmp")
        request = urllib.request.Request(url, headers={"User-Agent": "MeTube/2.0"})
        with urllib.request.urlopen(request, timeout=20) as response, open(tmp, "wb") as fh:
            fh.write(response.read())
        safe_move(tmp, destination)
        return True
    except Exception:  # noqa: BLE001 - thumbnails are best-effort
        log.debug("thumbnail download failed for %s", url, exc_info=True)
        return False
