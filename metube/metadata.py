"""Metadata preview fetcher: max 2 concurrent, throttled, never blocking.

Metadata/playlist calls never feed the download delay engine (Section 7.7);
they live on their own daemon threads and only ever push events.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path
from typing import Any

from . import config, downloader

log = logging.getLogger("metube.metadata")

MAX_CONCURRENT = 2
MIN_INTERVAL = 0.4  # throttle between yt-dlp metadata invocations


class MetadataFetcher:
    def __init__(self, events: "queue.Queue[dict[str, Any]]") -> None:
        self.events = events
        self._jobs: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self._gate = threading.Semaphore(MAX_CONCURRENT)
        self._pace_lock = threading.Lock()
        self._last_call = 0.0
        self._threads: list[threading.Thread] = []
        self._stopped = False

    # ------------------------------------------------------------------
    def start(self) -> None:
        for index in range(MAX_CONCURRENT):
            thread = threading.Thread(
                target=self._loop, name=f"MetadataFetcher-{index}", daemon=True
            )
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._stopped = True

    def submit(self, item_id: str, url: str) -> None:
        self._jobs.put((item_id, url))

    # ------------------------------------------------------------------
    def _loop(self) -> None:
        while not self._stopped:
            try:
                item_id, url = self._jobs.get(timeout=0.5)
            except queue.Empty:
                continue
            self._gate.acquire()
            try:
                self._fetch(item_id, url)
            finally:
                self._gate.release()
                self._jobs.task_done()

    def _pace(self) -> None:
        with self._pace_lock:
            gap = time.monotonic() - self._last_call
            if gap < MIN_INTERVAL:
                time.sleep(MIN_INTERVAL - gap)
            self._last_call = time.monotonic()

    def _fetch(self, item_id: str, url: str) -> None:
        self._pace()
        fields: dict[str, Any] = {"id": item_id}
        try:
            data = downloader.probe_metadata(url)
        except Exception as exc:  # noqa: BLE001 - previews are best effort
            log.info("metadata lookup failed for %s: %s", url, exc)
            return

        fields["title"] = data.get("title") or ""
        fields["channel"] = (
            data.get("uploader")
            or data.get("channel")
            or data.get("uploader_id")
            or ""
        )
        duration = data.get("duration")
        try:
            fields["duration"] = int(duration) if duration is not None else None
        except (TypeError, ValueError):
            fields["duration"] = None

        thumb_url = data.get("thumbnail")
        video_id = data.get("id") or item_id
        if thumb_url:
            destination = Path(config.thumbs_dir()) / f"{video_id}.jpg"
            if destination.exists() or downloader.download_thumbnail(thumb_url, destination):
                fields["thumbnail"] = str(destination)

        if not fields.get("title"):
            return
        self._push({"type": "item_metadata", "fields": fields})
        log.info("metadata resolved for %s: %s", video_id, fields.get("title"))

    def _push(self, event: dict[str, Any]) -> None:
        try:
            self.events.put_nowait(event)
        except queue.Full:  # pragma: no cover
            pass
