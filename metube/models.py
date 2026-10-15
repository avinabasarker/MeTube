"""Queue item model and the exact status vocabulary."""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any, Optional

# Exact status strings from the spec (Section 6).
STATUS_QUEUED = "Queued"
STATUS_PAUSED = "Paused"
STATUS_COMPLETED = "Completed ✓"
STATUS_CANCELLED = "Cancelled"

AUDIO_FORMATS = ("MP3", "M4A")
VIDEO_FORMATS = ("MP4",)
ALL_FORMATS = ("MP3", "M4A", "MP4")

QUALITIES = (
    "Best Available",
    "360p",
    "480p",
    "720p",
    "1080p",
    "1440p",
    "2160p",
)

QUALITY_HEIGHT = {
    "360p": 360,
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "1440p": 1440,
    "2160p": 2160,
}

# States in which an item is finished and the queue may advance past it.
TERMINAL_STATUSES = (STATUS_COMPLETED, STATUS_CANCELLED)


def is_terminal(status: str) -> bool:
    return status == STATUS_COMPLETED or status == STATUS_CANCELLED or status.startswith("Failed")


def status_starting_in(seconds: int) -> str:
    return f"Starting in {seconds}s"


def status_downloading(percent: str, speed: str, eta: str) -> str:
    speed = (speed or "").strip()
    if speed.endswith("/s"):
        speed = speed[:-2]
    eta = (eta or "").strip() or "--:--"
    return f"Downloading… {percent}% · {speed}/s · ETA {eta}"


def status_retrying(attempt: int, total: int = 2) -> str:
    return f"Retrying ({attempt}/{total})…"


def status_cooldown(seconds: int) -> str:
    return f"Cooling down… retrying in {seconds}s"


def status_failed(reason: str) -> str:
    return f"Failed: {reason}"


@dataclasses.dataclass
class QueueItem:
    url: str
    fmt: str = "MP3"
    quality: str = "Best Available"
    id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex[:12])
    video_id: Optional[str] = None
    title: str = ""
    channel: str = ""
    duration: Optional[int] = None
    thumbnail: str = ""
    status: str = STATUS_QUEUED
    file_path: str = ""
    failure_reason: str = ""
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    message: str = ""

    # ------------------------------------------------------------------
    @property
    def display_title(self) -> str:
        return self.title or "Title unavailable — will verify at download time"

    @property
    def meta_line(self) -> str:
        bits = []
        if self.channel:
            bits.append(self.channel)
        from .utils import humanize_duration

        if self.duration:
            bits.append(humanize_duration(self.duration))
        if self.fmt == "MP4":
            bits.append(self.quality)
        else:
            bits.append("Audio 320K" if self.fmt == "MP3" else "Audio")
        return " · ".join(bits)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueueItem":
        known = {f.name for f in dataclasses.fields(cls)}
        payload = {k: v for k, v in (data or {}).items() if k in known}
        item = cls(url=payload.pop("url", ""))
        for key, value in payload.items():
            setattr(item, key, value)
        if not item.id:
            item.id = uuid.uuid4().hex[:12]
        return item
