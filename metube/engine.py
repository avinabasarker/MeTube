"""Sequential download queue engine.

Threading contract (Section 10): this module owns exactly one worker thread
plus the yt-dlp reader threads.  No widget is ever touched from a worker;
every UI-facing change is pushed onto the shared ``queue.Queue`` of events
that the Tk main loop drains.
"""

from __future__ import annotations

import logging
import queue
import random
import threading
import time
from pathlib import Path
from typing import Any, Callable

import psutil

from . import config, downloader, keepawake, store
from .utils import free_space_bytes, human_mb
from .downloader import BOT, PERMANENT, TRANSIENT
from .models import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_PAUSED,
    STATUS_QUEUED,
    QueueItem,
    is_terminal,
    status_cooldown,
    status_downloading,
    status_failed,
    status_retrying,
    status_starting_in,
)

log = logging.getLogger("metube.engine")

TRANSIENT_WAITS = (15, 30)
# A bot check is normally about *which* YouTube client asked, not about rate
# limits, so the first answer is to ask with a different client almost at once
# (see downloader.BOT_CLIENT_FALLBACKS).  Only once every client has been tried
# does the long rate-limit cooldown ladder below apply.
BOT_SWITCH_WAITS = 5
# Bounded grace period before the first download of an item, so the metadata
# fetcher can name the file properly instead of falling back to the video id.
# The value also has to cover a metadata lookup that steps down the
# player-client ladder after a bot check (downloader.BOT_CLIENT_FALLBACKS).
TITLE_GRACE_SECONDS = 12.0
COOLDOWN_WAITS = (60, 120, 240)
# Below this, nothing sensible fits anyway and the raw OS error ("[Errno 28] No
# space left on device") is the least useful thing to show - fail with a
# sentence the user can act on instead, and let Retry do the rest.
MIN_FREE_SPACE_BYTES = 100 * 1024 * 1024


def no_space_reason(free: int, folder: Path) -> str:
    drive = Path(folder).drive or str(folder)
    return (
        f"not enough free disk space ({human_mb(free)} left on {drive}) "
        "— free some space, then press Retry"
    )


class QueueManager:
    """Owns the queue, the sequential worker and all queue persistence."""

    def __init__(
        self,
        events: "queue.Queue[dict[str, Any]]",
        settings_provider: Callable[[], Any],
        items: list[QueueItem] | None = None,
    ) -> None:
        self.events = events
        self.settings_provider = settings_provider
        self._items: list[QueueItem] = list(items or [])
        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._paused = False
        self._cancelled_ids: set[str] = set()
        self._worker: threading.Thread | None = None
        self._active_item: QueueItem | None = None
        self._active_proc = None
        self._suspended: list[Any] = []
        self._processed_since_idle = 0
        self._completed_since_idle = 0
        self._failed_since_idle = 0
        self._has_run_something = False
        self._last_progress_push = 0.0
        self._last_persist = 0.0
        self._persist_lock = threading.Lock()
        self._idle = True
        self.items_added_since_start = 0

    # ------------------------------------------------------------------
    # public API (Tk main thread)
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(
            target=self._loop, name="QueueWorker", daemon=True
        )
        self._worker.start()
        log.info("queue worker started")

    def shutdown(self) -> None:
        self._stop.set()
        self._terminate_active()
        with self._cv:
            self._cv.notify_all()
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=5)
        keepawake.release()
        log.info("queue worker stopped")

    def snapshot(self) -> list[QueueItem]:
        with self._lock:
            return list(self._items)

    def counts(self) -> dict[str, int]:
        with self._lock:
            total = len(self._items)
            completed = sum(1 for i in self._items if i.status == STATUS_COMPLETED)
            failed = sum(1 for i in self._items if i.status.startswith("Failed"))
            active = sum(
                1
                for i in self._items
                if not is_terminal(i.status) and i.status != STATUS_QUEUED
            )
            pending = sum(1 for i in self._items if i.status == STATUS_QUEUED)
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "active": active,
            "pending": pending,
            "finished": completed + failed,
        }

    def has_terminal(self) -> bool:
        with self._lock:
            return any(i.status == STATUS_COMPLETED for i in self._items)

    def find(self, item_id: str) -> QueueItem | None:
        with self._lock:
            for item in self._items:
                if item.id == item_id:
                    return item
        return None

    def add_item(self, item: QueueItem, announce: bool = True) -> None:
        with self._lock:
            self._items.append(item)
        if announce:
            self._push({"type": "item_added", "item": item.to_dict()})
        self.items_added_since_start += 1
        self._persist(force=True)
        self._push_counts()
        with self._cv:
            self._cv.notify_all()

    def remove_item(self, item_id: str) -> None:
        with self._lock:
            self._items = [i for i in self._items if i.id != item_id]
        self._push({"type": "item_removed", "id": item_id})
        self._persist(force=True)
        self._push_counts()

    def retry_item(self, item_id: str) -> None:
        with self._lock:
            item = next((i for i in self._items if i.id == item_id), None)
            if item is None:
                return
            self._cancelled_ids.discard(item_id)
            item.status = STATUS_QUEUED
            item.failure_reason = ""
            item.progress = 0.0
            item.speed = ""
            item.eta = ""
        self._set_fields(item_id, status=STATUS_QUEUED, failure_reason="", progress=0.0)
        with self._cv:
            self._cv.notify_all()

    def cancel_item(self, item_id: str) -> None:
        self._cancelled_ids.add(item_id)
        with self._lock:
            active = self._active_item is not None and self._active_item.id == item_id
            item = next((i for i in self._items if i.id == item_id), None)
        if active:
            self._terminate_active()
        elif item is not None and not is_terminal(item.status):
            self._set_fields(item_id, status=STATUS_CANCELLED)

    def cancel_all(self) -> None:
        with self._lock:
            ids = [i.id for i in self._items if not is_terminal(i.status)]
        for item_id in ids:
            self._cancelled_ids.add(item_id)
        self._terminate_active()
        for item_id in ids:
            self._set_fields(item_id, status=STATUS_CANCELLED)

    def clear_completed(self) -> None:
        with self._lock:
            finished = [i.id for i in self._items if i.status == STATUS_COMPLETED]
        for item_id in finished:
            self.remove_item(item_id)

    def pause_all(self) -> None:
        with self._lock:
            if self._paused:
                return
            self._paused = True
            item = self._active_item
            proc = self._active_proc
        if item is not None:
            self._set_fields(item.id, status=STATUS_PAUSED)
        if proc is not None:
            self._suspend_proc_tree(proc)
            log.info("paused active process tree")
        with self._cv:
            self._cv.notify_all()

    def resume_all(self) -> None:
        with self._lock:
            if not self._paused:
                return
            self._paused = False
            item = self._active_item
        if self._suspended:
            self._resume_proc_tree()
            log.info("resumed paused process tree")
        if item is not None:
            self._set_fields(
                item.id, status=status_downloading(f"{item.progress:.1f}", item.speed, item.eta)
            )
        with self._cv:
            self._cv.notify_all()

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    # ------------------------------------------------------------------
    # event / persistence helpers
    # ------------------------------------------------------------------
    def _push(self, event: dict[str, Any]) -> None:
        try:
            self.events.put_nowait(event)
        except queue.Full:  # pragma: no cover - unbounded queue
            pass

    def _push_counts(self) -> None:
        self._push({"type": "queue_changed", "counts": self.counts()})

    def _set_fields(self, item_id: str, **fields: Any) -> None:
        with self._lock:
            item = next((i for i in self._items if i.id == item_id), None)
            if item is None:
                return
            for key, value in fields.items():
                setattr(item, key, value)
        payload = dict(fields)
        payload["id"] = item_id
        self._push({"type": "item_updated", "fields": payload})
        self._persist()

    def _persist(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._last_persist) < 0.5:
            return
        if not self._persist_lock.acquire(blocking=False):
            return
        try:
            self._last_persist = now
            store.save_queue(self.snapshot())
        finally:
            self._persist_lock.release()

    # ------------------------------------------------------------------
    # worker
    # ------------------------------------------------------------------
    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self._paused:
                    self._wait_for_resume()
                    continue
                item = self._next_queued()
                if item is None:
                    self._go_idle()
                    with self._cv:
                        self._cv.wait(timeout=0.3)
                    continue
                self._run_item(item)
            except Exception:  # noqa: BLE001 - worker must survive
                log.exception("queue worker iteration failed")
                time.sleep(0.5)

    def _next_queued(self) -> QueueItem | None:
        with self._lock:
            for item in self._items:
                if item.status == STATUS_QUEUED:
                    return item
        return None

    def _go_idle(self) -> None:
        if self._idle:
            return
        self._idle = True
        keepawake.release()
        if self._has_run_something:
            self._has_run_something = False
            self._push(
                {
                    "type": "queue_finished",
                    "completed": self._completed_since_idle,
                    "failed": self._failed_since_idle,
                }
            )
            log.info(
                "queue idle: %s completed, %s failed",
                self._completed_since_idle,
                self._failed_since_idle,
            )
        self._completed_since_idle = 0
        self._failed_since_idle = 0
        self._push({"type": "engine_idle"})

    def _await_title(self, item: QueueItem, timeout: float = TITLE_GRACE_SECONDS) -> None:
        """Give the metadata fetcher a bounded moment to resolve the title.

        The outtmpl is built from the item title (Section 9), so a download
        that starts before metadata lands gets named after the bare video id
        (``jNQXAC9IVRw.mp3`` instead of ``Me at the zoo.mp3``).  The very first
        item of a session starts with no inter-item delay, so without this
        grace period the first file of every session would be misnamed.

        The wait is hard-capped: a metadata failure must never stall the queue
        (Section 7.6 - the item proceeds and the file is verified at download
        time instead).
        """
        if item.title:
            return
        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < deadline:
            if item.title or self._stop.is_set() or self._is_cancelled(item) or self._paused:
                return
            with self._cv:
                self._cv.wait(timeout=0.1)

    def _run_item(self, item: QueueItem) -> None:
        settings = self.settings_provider()
        low, high = settings.validated_delays()

        self._await_title(item)

        if self._has_run_something:
            delay = random.uniform(float(low), float(high))
            item_ref = item
            if not self._countdown(item_ref, delay):
                return

        attempt = 0
        cooldown = 0
        client_index = 0
        player_client = ""
        while not self._stop.is_set():
            if self._is_cancelled(item):
                self._finish_cancelled(item)
                return

            # Honour a pause taken while we were between attempts: Pause must
            # stop the queue advancing, not just suspend the live process.
            if self._paused:
                self._set_fields(item.id, status=STATUS_PAUSED)
                self._wait_for_resume()
                if self._stop.is_set():
                    return
                if self._is_cancelled(item):
                    self._finish_cancelled(item)
                    return

            # Absolute at the boundary: yt-dlp resolves a relative -o template
            # against its own cwd (see config.resolve_download_folder).
            folder = config.resolve_download_folder(settings.download_folder)
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self._fail(item, f"cannot create download folder: {exc}")
                return

            free = free_space_bytes(folder)
            if free is not None and free < MIN_FREE_SPACE_BYTES:
                self._fail(item, no_space_reason(free, folder))
                return

            self._set_fields(item.id, status="Downloading… 0%", progress=0.0, speed="", eta="", failure_reason="")
            keepawake.set_enabled(bool(settings.get("keep_awake", True)))

            item.title = item.title or item.video_id or "video"
            result = downloader.run_download(
                item,
                folder,
                player_client=player_client,
                on_progress=self._make_progress(item),
                register_proc=lambda proc: self._register_proc(item, proc, settings),
                should_cancel=lambda: self._is_cancelled(item) or self._stop.is_set(),
            )
            self._clear_active()

            if self._stop.is_set() and not result.file_path:
                self._finish_cancelled(item)
                return
            if result.cancelled or self._is_cancelled(item):
                self._cleanup_partials(folder, result.base_title)
                self._finish_cancelled(item)
                return
            if result.ok:
                self._complete(item, result.file_path)
                return

            kind, reason = downloader.classify_failure(result.stderr)

            if kind == BOT and client_index < len(downloader.BOT_CLIENT_FALLBACKS):
                player_client = downloader.BOT_CLIENT_FALLBACKS[client_index]
                client_index += 1
                log.info(
                    "bot check on %s - retrying with player_client=%s",
                    item.url,
                    player_client,
                )
                self._set_fields(item.id, failure_reason=reason)
                if not self._wait(item, BOT_SWITCH_WAITS, status_cooldown):
                    return
                continue

            if kind == BOT and cooldown < len(COOLDOWN_WAITS):
                wait = COOLDOWN_WAITS[cooldown]
                cooldown += 1
                self._set_fields(item.id, failure_reason=reason)
                if not self._wait(item, wait, status_cooldown):
                    return
                continue
            if kind == TRANSIENT and attempt < len(TRANSIENT_WAITS):
                wait = TRANSIENT_WAITS[attempt]
                attempt += 1
                self._set_fields(item.id, failure_reason=reason)
                if not self._wait(item, wait, lambda r: status_retrying(attempt, len(TRANSIENT_WAITS))):
                    return
                continue

            self._fail(item, reason)
            return

    # ------------------------------------------------------------------
    # per-download plumbing
    # ------------------------------------------------------------------
    def _register_proc(self, item: QueueItem, proc, settings) -> None:
        with self._lock:
            self._active_item = item
            self._active_proc = proc
            self._idle = False
        self._has_run_something = True
        if settings.get("keep_awake", True):
            keepawake.acquire()
        self._processed_since_idle += 1
        # Pause can land between "Downloading… 0%" and the subprocess actually
        # existing (Popen takes tens of ms).  If that happened, suspend the
        # fresh process tree immediately instead of letting it run unpaused.
        if self._paused:
            self._suspend_proc_tree(proc)
            self._set_fields(item.id, status=STATUS_PAUSED)
            log.info("paused immediately after spawn")

    def _clear_active(self) -> None:
        with self._lock:
            self._active_item = None
            self._active_proc = None
            self._suspended = []

    def _make_progress(self, item: QueueItem) -> Callable[[str, str, str], None]:
        def _on_progress(percent: str, speed: str, eta: str) -> None:
            try:
                value = float((percent or "0").replace("%", "").strip())
            except ValueError:
                value = 0.0
            now = time.monotonic()
            if item.status == STATUS_PAUSED:
                return
            if value >= 100.0 and item.fmt in ("MP3", "M4A"):
                status = "Converting audio…"
            else:
                status = status_downloading(percent.strip() or "0", speed, eta)
            item.progress = value
            item.speed = speed
            item.eta = eta
            if now - self._last_progress_push < 0.25:
                self._persist()
                return
            self._last_progress_push = now
            self._push(
                {
                    "type": "item_updated",
                    "fields": {
                        "id": item.id,
                        "status": status,
                        "progress": value,
                        "speed": speed,
                        "eta": eta,
                    },
                }
            )
            self._persist()

        return _on_progress

    def _complete(self, item: QueueItem, file_path: str) -> None:
        self._set_fields(
            item.id,
            status=STATUS_COMPLETED,
            file_path=file_path,
            progress=100.0,
            failure_reason="",
        )
        self._completed_since_idle += 1
        try:
            store.append_history(
                item,
                status=STATUS_COMPLETED,
                file_path=file_path,
                failure_reason="",
            )
        except Exception:  # noqa: BLE001
            log.exception("history append failed")
        log.info("completed: %s -> %s", item.title, file_path)

    def _fail(self, item: QueueItem, reason: str) -> None:
        self._set_fields(
            item.id,
            status=status_failed(reason),
            failure_reason=reason,
            speed="",
            eta="",
        )
        self._failed_since_idle += 1
        try:
            store.append_history(
                item,
                status=status_failed(reason),
                failure_reason=reason,
            )
        except Exception:  # noqa: BLE001
            log.exception("history append failed")
        log.warning("failed: %s :: %s", item.title, reason)

    def _finish_cancelled(self, item: QueueItem) -> None:
        self._set_fields(item.id, status=STATUS_CANCELLED, speed="", eta="")
        log.info("cancelled: %s", item.title)

    def _cleanup_partials(self, folder: Path, base_title: str) -> None:
        try:
            for entry in folder.iterdir():
                if entry.is_file() and entry.name.endswith((".part", ".ytdl", ".tmp")):
                    if not base_title or entry.stem.startswith(base_title):
                        try:
                            entry.unlink()
                        except OSError:
                            pass
        except OSError:
            pass

    # ------------------------------------------------------------------
    # pause / cancel plumbing
    # ------------------------------------------------------------------
    def _is_cancelled(self, item: QueueItem) -> bool:
        return item.id in self._cancelled_ids

    def _countdown(self, item: QueueItem, seconds: float) -> bool:
        total = max(1, int(round(seconds)))
        for remaining in range(total, 0, -1):
            if self._stop.is_set() or self._is_cancelled(item):
                if self._is_cancelled(item):
                    self._finish_cancelled(item)
                return False
            self._set_fields(item.id, status=status_starting_in(remaining))
            if not self._sleep(1.0, item):
                if self._is_cancelled(item):
                    self._finish_cancelled(item)
                return False
        return True

    def _wait(self, item: QueueItem, seconds: int, formatter: Callable[[int], str]) -> bool:
        remaining = int(seconds)
        while remaining > 0:
            if self._stop.is_set() or self._is_cancelled(item):
                if self._is_cancelled(item):
                    self._finish_cancelled(item)
                return False
            self._set_fields(item.id, status=formatter(remaining))
            if not self._sleep(1.0, item):
                if self._is_cancelled(item):
                    self._finish_cancelled(item)
                return False
            remaining -= 1
        return True

    def _sleep(self, seconds: float, item: QueueItem | None = None) -> bool:
        end = time.monotonic() + seconds
        while True:
            if self._stop.is_set():
                return False
            if item is not None and self._is_cancelled(item):
                return False
            if self._paused:
                # Show "Paused" while we hold; the callers (_countdown / _wait)
                # re-apply their own status line on the next iteration.
                if item is not None:
                    self._set_fields(item.id, status=STATUS_PAUSED)
                self._wait_for_resume()
                if self._stop.is_set():
                    return False
                continue
            remaining = end - time.monotonic()
            if remaining <= 0:
                return True
            with self._cv:
                self._cv.wait(timeout=min(0.2, remaining))

    def _wait_for_resume(self) -> None:
        with self._cv:
            while self._paused and not self._stop.is_set():
                self._cv.wait(timeout=0.2)

    # ------------------------------------------------------------------
    # process tree control
    # ------------------------------------------------------------------
    def _suspend_proc_tree(self, proc) -> None:
        try:
            root = psutil.Process(proc.pid)
            procs = list(root.children(recursive=True)) + [root]
            suspended = []
            for candidate in procs:
                try:
                    candidate.suspend()
                    suspended.append(candidate)
                except psutil.Error:
                    pass
            with self._lock:
                self._suspended = suspended
        except Exception:  # noqa: BLE001
            log.exception("suspend failed")

    def _resume_proc_tree(self) -> None:
        with self._lock:
            suspended = list(self._suspended)
            self._suspended = []
        for candidate in reversed(suspended):
            try:
                candidate.resume()
            except Exception:  # noqa: BLE001
                pass

    def _terminate_active(self) -> None:
        with self._lock:
            proc = self._active_proc
        if proc is None:
            return
        try:
            root = psutil.Process(proc.pid)
            victims = list(root.children(recursive=True)) + [root]
            for victim in victims:
                try:
                    victim.terminate()
                except psutil.Error:
                    pass
            _, alive = psutil.wait_procs(victims, timeout=3)
            for victim in alive:
                try:
                    victim.kill()
                except psutil.Error:
                    pass
        except Exception:  # noqa: BLE001
            try:
                proc.terminate()
            except Exception:
                pass
        log.info("terminated active download process")
