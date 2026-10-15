"""Persistence of the queue snapshot and the download history."""

from __future__ import annotations

import datetime as _dt
from typing import Any

from . import config
from .models import QueueItem
from .utils import read_json, write_json


# --------------------------------------------------------------------- queue
def save_queue(items: list[QueueItem]) -> None:
    try:
        write_json(config.queue_path(), [item.to_dict() for item in items])
    except OSError:
        pass


def load_queue() -> list[QueueItem]:
    raw = read_json(config.queue_path(), [])
    if not isinstance(raw, list):
        return []
    items: list[QueueItem] = []
    for entry in raw:
        if isinstance(entry, dict) and entry.get("url"):
            items.append(QueueItem.from_dict(entry))
    return items


def clear_queue() -> None:
    try:
        config.queue_path().unlink(missing_ok=True)
    except OSError:
        pass


# ------------------------------------------------------------------- history
def append_history(
    item: QueueItem,
    *,
    status: str | None = None,
    file_path: str | None = None,
    failure_reason: str | None = None,
) -> None:
    """Append one outcome row.

    The outcome fields are passed in explicitly rather than read back off the
    live ``item``.  The queue item is shared with the engine and the UI, so a
    Retry clicked in the microseconds between setting the terminal status and
    writing the row would otherwise rewrite ``item.status`` back to 'Queued'
    and the history would record the wrong outcome.
    """
    rows = load_history()
    rows.append(
        {
            "timestamp": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "title": item.title or item.url,
            "url": item.url,
            "video_id": item.video_id,
            "fmt": item.fmt,
            "quality": item.quality,
            "status": item.status if status is None else status,
            "file_path": item.file_path if file_path is None else file_path,
            "failure_reason": (
                item.failure_reason if failure_reason is None else failure_reason
            ),
            "thumbnail": item.thumbnail,
        }
    )
    try:
        write_json(config.history_path(), rows)
    except OSError:
        pass


def load_history() -> list[dict[str, Any]]:
    raw = read_json(config.history_path(), [])
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def clear_history() -> None:
    try:
        write_json(config.history_path(), [])
    except OSError:
        pass
