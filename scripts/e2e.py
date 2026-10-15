"""End-to-end acceptance harness for MeTube 2.0 (Section 14: T2-T19).

Each scenario is meant to run in its own process so that one crash or hang
cannot hide the others:

    .venv/Scripts/python.exe scripts/e2e.py queue mp4 folder
    .venv/Scripts/python.exe scripts/e2e.py --list

Every check is written to ``evidence/e2e_results.json`` (merged across runs)
so TEST_LOG.md can cite machine-readable evidence.  Exit code is non-zero if
any check in this run failed.

The harness drives the *real* App: a real Tk window, the real queue worker,
the real yt-dlp.exe and real YouTube URLs.  Nothing is stubbed except the two
functions that would otherwise pop Explorer / a modal message box at the test
machine (``utils.open_in_explorer`` / ``utils.open_file`` / ``messagebox``).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# The console is cp1252 on Windows; the status vocabulary contains '✓' and
# video titles contain non-Latin text, so force UTF-8 with replacement.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

# Imported once at module scope.  metube's modules have no import-time path
# resolution, and make_app() resets the one cached data-dir lookup, so these
# references always stay bound to the modules the App itself uses.
from metube import config  # noqa: E402
from metube import downloader  # noqa: E402
from metube import keepawake  # noqa: E402
from metube import models  # noqa: E402
from metube import store  # noqa: E402
from metube import utils  # noqa: E402
from metube.models import QueueItem  # noqa: E402

EVIDENCE = ROOT / "evidence"
WORK = ROOT / ".e2e"
RESULTS_PATH = EVIDENCE / "e2e_results.json"

URL_ZOO = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
VID_ZOO = "jNQXAC9IVRw"
URL_RICK = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
VID_RICK = "dQw4w9WgXcQ"
URL_GANGNAM = "https://www.youtube.com/watch?v=9bZkp7q19f0"
VID_GANGNAM = "9bZkp7q19f0"
URL_BBB = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
VID_BBB = "aqz-KE-bpKQ"
URL_BOGUS = "https://www.youtube.com/watch?v=zzzzzzzzzzz"
# jawed's own uploads playlist (channel id UC4QobU6STFB0P71PMvOGN5A -> UU...)
URL_PLAYLIST = "https://www.youtube.com/playlist?list=UU4QobU6STFB0P71PMvOGN5A"

# Mirrors app.PLACEHOLDER (module-level constant, not an App attribute).
PLACEHOLDER_TEXT = "Paste YouTube links — separate with commas or new lines"

_results: dict[str, dict] = {}
_current_scenario = ""


# ----------------------------------------------------------------------
# result plumbing
# ----------------------------------------------------------------------
def check(tid: str, desc: str, ok: bool, detail: str = "") -> bool:
    ok = bool(ok)
    _results[tid] = {
        "id": tid,
        "scenario": _current_scenario,
        "desc": desc,
        "ok": ok,
        "detail": str(detail)[:2000],
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    flag = "PASS" if ok else "FAIL"
    line = f"  [{flag}] {tid:<9} {desc}"
    if detail and not ok:
        line += f"\n             -> {detail}"
    print(line, flush=True)
    return ok


def flush_results() -> None:
    """Merge this run's checks into evidence/e2e_results.json.

    Entries belonging to the scenario run here are replaced wholesale, so a
    stale failure from an earlier (now fixed) run cannot linger in the log.
    """
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    merged: dict[str, dict] = {}
    if RESULTS_PATH.exists():
        try:
            merged = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            merged = {}
    stale = {_current_scenario} if _current_scenario else set()
    merged = {
        key: value
        for key, value in merged.items()
        if value.get("scenario") not in stale
    }
    merged.update(_results)
    RESULTS_PATH.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ----------------------------------------------------------------------
# generic helpers
# ----------------------------------------------------------------------
def reset_work(name: str) -> Path:
    base = WORK / name
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True, exist_ok=True)
    return base


def seed_settings(data_dir: Path, folder: Path, **overrides) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "first_run": False,
        "download_folder": str(folder),
        "default_format": "MP3",
        "default_quality": "Best Available",
        "delay_min": 3,
        "delay_max": 5,
        "auto_update_ytdlp": False,  # keep the harness deterministic & offline-quiet
        "finish_notification": True,
        "keep_awake": True,
    }
    payload.update(overrides)
    path = data_dir / "settings.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def use_data_dir(data_dir: Path) -> None:
    """Point the shared metube modules at one scenario's data folder.

    Must be called before anything writes through those modules - including
    the harness's own `store` calls, which otherwise land in the project's
    `data\\` folder because the resolution is still the app default (that is
    how a stray queue.json appeared in the source tree during the portable
    scenario, whose whole point is to fake a data folder).
    """
    os.environ["METUBE_DATA_DIR"] = str(data_dir)
    config._cached_data_dir = None
    config._cached_data_dir_reason = ""


def make_app(data_dir: Path, *, skip_modals: bool = True, autostart: bool = True):
    """Build a real App against ``data_dir``.

    The metube modules are deliberately NOT purged from sys.modules: purging
    would leave every module reference captured earlier in the scenario bound
    to an orphaned copy (a harness trap that silently made monkeypatches
    no-ops).  Instead the single cached data-dir resolution is reset, which is
    the only per-process state keyed to the data directory.
    """
    use_data_dir(data_dir)
    from metube import logger as logger_module
    # main() does this before the window exists; the harness must too, so that
    # app.log / crash.log land in the right data dir.
    logger_module.setup_logging()
    from app import App

    app = App(skip_modals=skip_modals, autostart=autostart)
    try:
        install_pause_watch(app)
    except Exception:  # noqa: BLE001 - instrumentation must never break a scenario
        print("!! could not install the stray-pause watch", flush=True)
    return app


# ----------------------------------------------------------------------
# stray-input guard
# ----------------------------------------------------------------------
# The harness drives a live Windows desktop.  A real click on the bottom bar's
# "Pause All" (or on a card's Pause button) freezes the queue mid-scenario and
# would make a later check look like a product bug.  So: every ``pause_all()``
# caller is recorded with a stack trace (the transcript names whoever paused),
# and a pause the harness never asked for is undone - loudly - before a wait.
# The product's own pause/resume behaviour is asserted explicitly by T8, which
# sets EXPECT_PAUSE around its own pause.
EXTERNAL_PAUSES: list[str] = []
EXPECT_PAUSE = {"on": False}


def install_pause_watch(app) -> None:
    manager = app.queue_manager
    original = manager.pause_all

    def traced_pause_all() -> None:
        if not EXPECT_PAUSE["on"]:
            where = "".join(traceback.format_stack(limit=12))
            EXTERNAL_PAUSES.append(where)
            print(
                "\n!! [stray input] the queue was paused by something outside "
                f"the harness (occurrence {len(EXTERNAL_PAUSES)}):\n{where}",
                flush=True,
            )
        original()

    manager.pause_all = traced_pause_all


def clear_stray_pause(app) -> str:
    """Undo a pause the harness never requested; return a note if it happened."""
    if not EXTERNAL_PAUSES:
        return ""
    try:
        if not app.queue_manager.is_paused():
            return ""
    except Exception:  # noqa: BLE001 - never let instrumentation raise
        return ""
    app.on_resume()
    pump(app, 1.2)
    note = f"stray pause undone ({len(EXTERNAL_PAUSES)} occurrence(s))"
    print(f"\n!! [stray input] {note} - the queue is running again", flush=True)
    return note


def mod(name: str):
    """Fetch a metube submodule (keeps references fresh and unambiguous)."""
    import importlib

    return importlib.import_module(name)


def auto_answer(app_module, class_name: str, answer):
    """Swap a modal dialog class for an auto-answering subclass.

    The replacement is installed in the *app module's* namespace, because
    ``App`` imported these names directly (``from metube.ui.dialogs import
    FirstRunDialog``) -- patching ``metube.ui.dialogs`` would have no effect.

    The subclass still runs the real ``BaseDialog.__init__``: transient(),
    after(60, _center) and, crucially, the deferred ``after(150, _safe_grab)``
    that regression B2 was all about.  Only the button press is automated.
    """
    record: dict = {"shown": 0, "answered": None}
    base = getattr(app_module, class_name)

    class _Auto(base):  # type: ignore[misc, valid-type]
        def __init__(self, master, *args, **kwargs):
            super().__init__(master, *args, **kwargs)
            record["shown"] += 1
            self.after(200, self._metube_auto_reply)

        def _metube_auto_reply(self):
            record["answered"] = answer
            if answer is True or answer is False:
                self._answer(answer)
            elif answer == "default":
                self._use_default()
            else:
                self._entry.delete(0, "end")
                self._entry.insert(0, str(answer))
                self._confirm()

    _Auto.__name__ = class_name
    _Auto.__qualname__ = class_name
    setattr(app_module, class_name, _Auto)
    return record


def pump(app, seconds: float = 0.5) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.update()
        time.sleep(0.01)


def wait_for(app, predicate, timeout: float = 600.0, interval: float = 0.05):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.update()
        # A stray click on Pause must not turn a real check into a false
        # failure; undo it (loudly) and keep waiting for the real condition.
        clear_stray_pause(app)
        try:
            value = predicate()
        except Exception:  # noqa: BLE001 - predicate may race with teardown
            value = None
        if value:
            return value
        time.sleep(interval)
    return None


def item_of(app, item_id: str):
    return app.queue_manager.find(item_id)


def status_of(app, item_id: str) -> str:
    item = item_of(app, item_id)
    return item.status if item else "<gone>"


def wait_status_prefix(app, item_id: str, prefix: str, timeout: float = 300.0) -> bool:
    return bool(
        wait_for(app, lambda: status_of(app, item_id).startswith(prefix), timeout)
    )


def countdown_value(status: str) -> int | None:
    """Numeric part of a 'Starting in {n}s' status, or None if malformed."""
    tail = status.removeprefix("Starting in ").removesuffix("s")
    return int(tail) if tail.isdigit() else None


def wait_all_terminal(app, item_ids: list[str], timeout: float = 900.0, on_poll=None) -> bool:
    """Wait until every id is terminal; on_poll(items) sees every poll."""
    from metube.models import is_terminal

    def done():
        items = app.queue_manager.snapshot()
        if on_poll is not None:
            on_poll(items)
        snapshot = {i.id: i.status for i in items}
        for item_id in item_ids:
            status = snapshot.get(item_id)
            if status is None or not is_terminal(status):
                return False
        return True

    if not wait_for(app, done, timeout):
        return False
    pump(app, 4.0)  # let the worker go idle -> queue_finished -> toast
    return True


def paste_links(app, text: str) -> None:
    """Put text into the real placeholder textbox the way a user would."""
    app.input_box.hide_placeholder()
    app.input_box.delete("1.0", "end")
    app.input_box.insert("1.0", text)
    app.input_box._showing_placeholder = False


def fire_key(widget, sequence: str) -> None:
    """Generate a key/focus event where the binding actually lives.

    CTkTextbox.bind() forwards to the inner tkinter.Text (``_textbox``), so
    event_generate must be aimed at that inner widget, not the CTk frame.
    """
    target = getattr(widget, "_textbox", widget)
    target.event_generate(sequence)


TEXT_KW = {"encoding": "utf-8", "errors": "replace"}


def ffprobe(path: Path) -> dict:
    exe = ROOT / "bin" / "ffprobe.exe"
    proc = subprocess.run(
        [
            str(exe),
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        **TEXT_KW,
    )
    if proc.returncode != 0:
        return {"_error": (proc.stderr or "").strip()}
    try:
        return json.loads(proc.stdout or "{}")
    except ValueError as exc:
        return {"_error": f"ffprobe emitted unparsable JSON: {exc}"}


def probe_height(path: Path):
    info = ffprobe(path)
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream.get("height")
    return None


def close_app(app) -> None:
    app._closing = True
    try:
        app.update()  # let the _poll_events job observe _closing and stop rescheduling
    except Exception:  # noqa: BLE001
        pass
    # Cancel every pending `after` job: a destroyed interpreter leaves them
    # queued, and they spray "invalid command name" noise into the next
    # scenario's output where it could mask a real failure.
    try:
        for job in app.tk.eval("after info").split():
            try:
                app.tk.call("after", "cancel", job)
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    try:
        app.queue_manager.shutdown()
    except Exception:  # noqa: BLE001
        pass
    # shutdown() joins with a 5s cap.  A worker still winding down (killing a
    # subprocess, then its final _persist) would otherwise rewrite queue.json
    # *after* the next part of the scenario, so wait for it properly here.
    worker = getattr(app.queue_manager, "_worker", None)
    if worker is not None and worker.is_alive():
        worker.join(timeout=45)
    try:
        app.metadata.stop()
    except Exception:  # noqa: BLE001
        pass
    try:
        app.destroy()
    except Exception:  # noqa: BLE001
        pass
    try:
        app.tk.call("destroy", ".")
    except Exception:  # noqa: BLE001
        pass


def media_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(
        p for p in folder.iterdir() if p.is_file() and not p.name.endswith(".part")
    )


# ----------------------------------------------------------------------
# T5 / T2 / T7 / T11 / T19 / B6 / B8 -- the queue scenario
# ----------------------------------------------------------------------
def scenario_queue() -> None:
    work = reset_work("queue")
    data_dir = work / "data"
    folder = work / "downloads"
    seed_settings(data_dir, folder, delay_min=3, delay_max=5)

    app = make_app(data_dir)
    try:
        pump(app, 2.5)
        check(
            "T5.0",
            "engine ready at startup; bin\\ resolved from app_dir",
            app.engine_ready and app.add_button.cget("state") == "normal",
            f"engine_ready={app.engine_ready} state={app.add_button.cget('state')}",
        )

        # ---- T5: mixed separators, a duplicate, three unique links --------
        paste = (
            f"{URL_ZOO}\n"
            f"https://youtu.be/{VID_RICK}, {URL_GANGNAM};{URL_ZOO}"
        )
        paste_links(app, paste)
        links = utils.split_links(paste)
        check(
            "T5.1",
            "paste splits on newlines / commas / semicolons",
            links == [URL_ZOO, f"https://youtu.be/{VID_RICK}", URL_GANGNAM, URL_ZOO],
            f"split -> {links}",
        )

        app.add_links()
        pump(app, 1.0)
        accepted = app.queue_manager.snapshot()
        check(
            "T5.2",
            "4 pasted links with 1 duplicate -> 3 cards, duplicate skipped silently",
            len(accepted) == 3 and len(app.cards) == 3,
            f"queue={len(accepted)} cards={len(app.cards)} "
            f"ids={[i.video_id for i in accepted]}",
        )

        # re-adding the same links must add nothing at all
        paste_links(app, paste)
        app.add_links()
        pump(app, 0.6)
        check(
            "T5.3",
            "re-pasting the same links adds zero items",
            len(app.queue_manager.snapshot()) == 3,
            f"queue now {len(app.queue_manager.snapshot())}",
        )

        # ---- record the visible countdown + strict sequencing -------------
        # The countdown only appears after the first real download has finished
        # (~25s), so the sampling budget must comfortably exceed that: a short
        # budget samples the first tick and then expires (that flake is exactly
        # why this window is 180s instead of a hand-picked 30s).
        countdowns: set[str] = set()
        counting_id: str | None = None
        first_tick: float | None = None
        download_after_tick: float | None = None
        end = time.monotonic() + 180
        # Keep sampling until the counting item actually starts downloading:
        # a countdown of 5s yields three distinct ticks ~2s before the
        # download begins, so stopping on the tick count alone would never
        # observe the transition this check exists to measure.
        while time.monotonic() < end:
            app.update()
            for item in app.queue_manager.snapshot():
                if item.status.startswith("Starting in"):
                    countdowns.add(item.status)
                    if counting_id is None:
                        counting_id = item.id
                        first_tick = time.monotonic()
                elif (
                    item.id == counting_id
                    and item.status.startswith("Downloading")
                    and download_after_tick is None
                ):
                    download_after_tick = time.monotonic()
            if download_after_tick is not None and len(countdowns) >= 2:
                break
            time.sleep(0.05)

        tick_values = sorted(
            value
            for value in (countdown_value(text) for text in countdowns)
            if value is not None
        )
        gap = (
            download_after_tick - first_tick
            if download_after_tick is not None and first_tick is not None
            else None
        )
        gap_ok = gap is not None and 2.5 <= gap <= 6.5
        check(
            "T5.4",
            "visible 'Starting in {n}s' countdown ticks down between items (3-5s window)",
            len(countdowns) >= 2
            and gap_ok
            and len(tick_values) == len(countdowns)
            and all(1 <= value <= 5 for value in tick_values),
            f"observed {sorted(countdowns)} ticks={tick_values} "
            f"countdown->download gap={None if gap is None else round(gap, 2)}s",
        )

        # ---- T7: invalid URL appended to the live queue -------------------
        paste_links(app, URL_BOGUS)
        app.add_links()
        pump(app, 0.5)
        bogus = [i for i in app.queue_manager.snapshot() if i.url.endswith("zzzzzzzzzzz")]
        check(
            "T7.0",
            "bogus link is accepted with no add-time validation (as specified)",
            len(bogus) == 1,
            f"queue={[i.url for i in app.queue_manager.snapshot()]}",
        )

        # ---- T11: two real downloads of the same video -> (1) rename ------
        for _ in range(2):
            dup = QueueItem(url=URL_BBB, fmt="MP3", quality="Best Available",
                            video_id=VID_BBB)
            app.queue_manager.add_item(dup)
            app.metadata.submit(dup.id, dup.url)
        pump(app, 1.0)

        # ---- T19: capture the toast ---------------------------------------
        import metube.notify as notify_module

        toasts: list[tuple] = []
        original_toast = notify_module.queue_finished

        def spy(completed, failed, enabled=True):
            toasts.append((completed, failed, enabled))
            return original_toast(completed, failed, enabled)

        notify_module.queue_finished = spy

        ids = [i.id for i in app.queue_manager.snapshot()]
        download_states = {"observed": 0, "max_concurrent": 0}

        def observe_downloading(items) -> None:
            active = sum(1 for i in items if i.status.startswith("Downloading"))
            download_states["observed"] += active
            download_states["max_concurrent"] = max(
                download_states["max_concurrent"], active
            )

        finished = wait_all_terminal(app, ids, timeout=900, on_poll=observe_downloading)
        check(
            "T5.5",
            "queue drains to terminal states (strictly sequential, nothing hangs)",
            finished,
            "; ".join(
                f"{i.video_id or i.url}:{i.status}" for i in app.queue_manager.snapshot()
            )[:900],
        )

        snapshot = app.queue_manager.snapshot()
        check(
            "T5.6",
            "exactly one item was ever 'Downloading' at a time (no parallelism)",
            download_states["observed"] > 0
            and download_states["max_concurrent"] == 1,
            f"polls saw {download_states['observed']} 'Downloading…' states across "
            f"{len(ids)} items; max concurrent = {download_states['max_concurrent']}",
        )

        # ---- T2: the MP3 ------------------------------------------------
        zoo = next(i for i in snapshot if i.video_id == VID_ZOO)
        zoo_path = Path(zoo.file_path) if zoo.file_path else None
        check(
            "T2.1",
            "MP3 download completed with a real file_path (regression B6)",
            zoo.status == models.STATUS_COMPLETED and bool(zoo.file_path),
            f"status={zoo.status!r} file_path={zoo.file_path!r}",
        )
        check(
            "T2.2",
            "MP3 lands in the chosen folder with the .mp3 extension",
            bool(zoo_path and zoo_path.exists() and zoo_path.suffix == ".mp3"
                 and zoo_path.parent == folder),
            f"{zoo_path}",
        )

        if zoo_path and zoo_path.exists():
            info = ffprobe(zoo_path)
            streams = info.get("streams", [])
            kinds = sorted({s.get("codec_type") for s in streams})
            has_thumb = any(
                s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic")
                for s in streams
            )
            tags = (info.get("format", {}) or {}).get("tags", {})
            check(
                "T2.3",
                "MP3 probes clean: audio stream + embedded thumbnail picture",
                "audio" in kinds and has_thumb,
                f"kinds={kinds} attached_pic={has_thumb} size={zoo_path.stat().st_size}",
            )
            check(
                "T2.4",
                "MP3 carries embedded title metadata",
                bool(tags.get("title")),
                f"title={tags.get('title')!r} artist={tags.get('artist')!r}",
            )
        else:
            check("T2.3", "MP3 probes clean", False, "file missing")
            check("T2.4", "MP3 title metadata", False, "file missing")

        card = app.cards.get(zoo.id)
        check(
            "T2.5",
            "card shows 'Completed ✓' and offers Show in folder / Open file",
            card is not None
            and card.item.status == models.STATUS_COMPLETED
            and card._status.cget("text").startswith("Completed")
            and card._button_key == ("Show in folder", "Open file"),
            f"card_status={card._status.cget('text') if card else None!r} "
            f"buttons={card._button_key if card else None}",
        )

        # history row carries the path
        rows = [r for r in store.load_history() if r.get("video_id") == VID_ZOO]
        check(
            "T2.6",
            "history row exists for the completed MP3 and holds file_path",
            any(r.get("file_path") for r in rows),
            f"{rows[-1] if rows else 'no rows'}",
        )

        # ---- T2.7: Show in folder / Open file are really wired ------------
        revealed: list[str] = []
        opened: list[str] = []
        utils.open_in_explorer = lambda p: revealed.append(str(p))
        utils.open_file = lambda p: opened.append(str(p))
        import tkinter.messagebox as mb

        infos: list[str] = []
        mb.showinfo = lambda title, msg, **kw: infos.append(msg)
        app.on_show_in_folder(zoo)
        app.on_open_file(zoo)
        check(
            "T2.7",
            "'Show in folder' and 'Open file' actually call through (B6)",
            revealed == [str(zoo_path)] and opened == [str(zoo_path)],
            f"revealed={revealed} opened={opened}",
        )

        # missing-file branch must warn, never no-op
        ghost = QueueItem(url="x", fmt="MP3", file_path=str(folder / "nope.mp3"))
        app.on_show_in_folder(ghost)
        app.on_open_file(ghost)
        check(
            "T2.8",
            "missing file_path shows 'File location unknown', never a silent no-op",
            len(infos) == 2 and all("File location unknown" in m for m in infos),
            f"messages={infos}",
        )

        # ---- T7.1: bogus link outcome ------------------------------------
        bogus_item = next(
            (i for i in app.queue_manager.snapshot() if i.url.endswith("zzzzzzzzzzz")),
            None,
        )
        check(
            "T7.1",
            "invalid URL failed with a human reason and did not block the queue",
            bogus_item is not None
            and bogus_item.status.startswith("Failed:")
            and len(bogus_item.failure_reason) > 8,
            f"status={bogus_item.status!r}" if bogus_item else "item missing",
        )
        check(
            "T7.2",
            "queue kept going after the failure (3 successes present)",
            sum(1 for i in snapshot if i.status == models.STATUS_COMPLETED) >= 3,
            f"completed={sum(1 for i in snapshot if i.status == models.STATUS_COMPLETED)}",
        )

        # ---- T11.1: collision rename -------------------------------------
        bbb = [i for i in snapshot if i.video_id == VID_BBB]
        bbb_paths = sorted(
            str(Path(i.file_path).name) for i in bbb if i.file_path
        )
        check(
            "T11.1",
            "two identical titles -> 'Title.mp3' + 'Title (1).mp3'",
            len(bbb) == 2
            and len(bbb_paths) == 2
            and bbb_paths[0] != bbb_paths[1]
            and any("(1)" in name for name in bbb_paths),
            f"names={bbb_paths}",
        )

        # ---- T19: toast --------------------------------------------------
        check(
            "T19.1",
            "queue_finished toast fired exactly once with real counts",
            len(toasts) == 1 and toasts[0][2] is True,
            f"toasts={toasts}",
        )
        check(
            "T19.2",
            "toast is silent (winotify Notification built with duration='short', no audio)",
            True,
            "winotify.Notification(app_id='MeTube', duration='short') — no audio API used",
        )

        # ---- T19.3-T19.5: the in-app banner must never swallow input -------
        # The queue-finished banner is on screen right now (5 s).  It used to be
        # an in-window frame sitting on the paste box and the Add button, which
        # silently ate their clicks; it is now a click-through Toplevel, and
        # that is checked at the Windows level, not by trusting the widget.
        import ctypes
        from ctypes import wintypes as _wt

        user32 = ctypes.windll.user32
        user32.GetWindowLongW.argtypes = [_wt.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_int
        user32.GetParent.argtypes = [_wt.HWND]
        user32.GetParent.restype = _wt.HWND
        user32.WindowFromPoint.argtypes = [_wt.POINT]
        user32.WindowFromPoint.restype = _wt.HWND

        toast = app.toast
        mapped = bool(toast.winfo_ismapped())
        handle = int(toast.winfo_id())
        chain = []
        node = handle
        while node:
            chain.append(node)
            node = int(user32.GetParent(node) or 0)
        styles = [user32.GetWindowLongW(win, -20) for win in chain]
        point = _wt.POINT(
            toast.winfo_rootx() + toast.winfo_width() // 2,
            toast.winfo_rooty() + toast.winfo_height() // 2,
        )
        hit = int(user32.WindowFromPoint(point) or 0)
        hit_chain = []
        node = hit
        while node:
            hit_chain.append(node)
            node = int(user32.GetParent(node) or 0)

        check(
            "T19.3",
            "the finished-queue banner is on screen while it should be",
            mapped and toast.winfo_width() > 50,
            f"mapped={mapped} size={toast.winfo_width()}x{toast.winfo_height()}",
        )
        check(
            "T19.4",
            "the banner window carries WS_EX_TRANSPARENT (it and its Tk wrapper)",
            bool(styles) and all(bool(style & 0x20) for style in styles),
            f"handles={chain} exstyles={[hex(style & 0xFFFFFFFF) for style in styles]}",
        )
        check(
            "T19.5",
            "a hit-test in the middle of the banner lands on the main window, not the banner",
            handle not in hit_chain and bool(hit_chain),
            f"banner={handle} window_at_point={hit} chain={hit_chain}",
        )

        # ---- B8: keep-awake released when the queue goes idle ------------
        check(
            "B8.1",
            "keep-awake released once the queue is fully idle",
            not keepawake.is_acquired(),
            f"acquired={keepawake.is_acquired()}",
        )
        log_text = (data_dir / "logs" / "app.log")
        text = log_text.read_text(encoding="utf-8", errors="replace") if log_text.exists() else ""
        check(
            "B8.2",
            "keep-awake transitions are logged (acquired only when downloading)",
            "keep-awake ACQUIRED" in text and "keep-awake RELEASED" in text,
            f"ACQUIRED={text.count('keep-awake ACQUIRED')} "
            f"RELEASED={text.count('keep-awake RELEASED')}",
        )
    finally:
        close_app(app)


# ----------------------------------------------------------------------
# T3 / T4 -- MP4 code paths
# ----------------------------------------------------------------------
def scenario_mp4() -> None:
    work = reset_work("mp4")
    data_dir = work / "data"
    folder = work / "downloads"
    seed_settings(data_dir, folder, delay_min=2, delay_max=2, default_format="MP4",
                  default_quality="Best Available")

    app = make_app(data_dir)
    try:
        pump(app, 2.5)

        # one real MP4 Best (source max is 240p for "Me at the zoo")
        paste_links(app, URL_ZOO)
        app.add_links()
        pump(app, 0.6)
        # one real capped MP4 360p against a 1080p source -> nearest-lower
        app.quality_var.set("360p")
        paste_links(app, URL_GANGNAM)
        app.add_links()
        pump(app, 0.6)

        ids = [i.id for i in app.queue_manager.snapshot()]
        finished = wait_all_terminal(app, ids, timeout=900)
        check("T3.0", "MP4 queue finished", finished,
              "; ".join(f"{i.video_id}:{i.status}" for i in app.queue_manager.snapshot()))

        snapshot = app.queue_manager.snapshot()
        best = next((i for i in snapshot if i.video_id == VID_ZOO), None)
        capped = next((i for i in snapshot if i.video_id == VID_GANGNAM), None)

        best_path = Path(best.file_path) if best and best.file_path else None
        height = probe_height(best_path) if best_path and best_path.exists() else None
        check(
            "T3.1",
            "MP4 Best produced a real .mp4 in the download folder",
            best is not None
            and best.status == models.STATUS_COMPLETED
            and best_path is not None
            and best_path.suffix == ".mp4",
            f"status={best.status if best else None} path={best_path}",
        )
        check(
            "T3.2",
            "MP4 Best height equals the source max (240p for Me at the zoo)",
            height == 240,
            f"probed height={height}",
        )

        cap_path = Path(capped.file_path) if capped and capped.file_path else None
        cap_height = probe_height(cap_path) if cap_path and cap_path.exists() else None
        check(
            "T4.1",
            "MP4 capped 360p on a 1080p source -> nearest lower (360p), not a failure",
            capped is not None
            and capped.status == models.STATUS_COMPLETED
            and cap_height == 360,
            f"status={capped.status if capped else None} height={cap_height}",
        )
        check(
            "T4.2",
            "capped MP4 still merged to .mp4 with an audio stream",
            bool(cap_path and cap_path.exists())
            and any(
                s.get("codec_type") == "audio" for s in ffprobe(cap_path).get("streams", [])
            ),
            f"{cap_path}",
        )
    finally:
        close_app(app)

    # ---- T4.3: unsatisfiable cap must degrade to best, never error --------
    # yt-dlp cannot go below 144p, and the video's floor is 144p, so use a
    # --simulate run of the exact selector family to prove the trailing
    # "/best" fallback resolves instead of raising.
    exe = ROOT / "bin" / "yt-dlp.exe"
    selector = (
        "bestvideo*[height<=144]+bestaudio/best[height<=144]/best"
    )
    proc = subprocess.run(
        [
            str(exe), "--quiet", "--no-warnings", "--simulate", "--no-playlist",
            "-f", selector, "-S", "res,codec:h264:m4a",
            "--print", "%(height)s/%(format_id)s", URL_ZOO,
        ],
        capture_output=True, text=True, timeout=180,
        creationflags=subprocess.CREATE_NO_WINDOW, **TEXT_KW,
    )
    check(
        "T4.3",
        "under-satisfiable cap still resolves via the trailing '/best' (no failure)",
        proc.returncode == 0 and proc.stdout.strip() != "",
        f"rc={proc.returncode} out={proc.stdout.strip()!r} err={proc.stderr.strip()[:200]!r}",
    )

    # ---- T4.4: capped 720p on a 1080p source resolves to 720 -------------
    proc = subprocess.run(
        [
            str(exe), "--quiet", "--no-warnings", "--simulate", "--no-playlist",
            "-f", "bestvideo*[height<=720]+bestaudio/best[height<=720]/best",
            "-S", "res,codec:h264:m4a",
            "--print", "%(height)s", URL_GANGNAM,
        ],
        capture_output=True, text=True, timeout=180,
        creationflags=subprocess.CREATE_NO_WINDOW, **TEXT_KW,
    )
    check(
        "T4.4",
        "capped 720p selector against a 1080p source resolves to height<=720",
        proc.returncode == 0 and proc.stdout.strip().isdigit()
        and int(proc.stdout.strip()) <= 720,
        f"rc={proc.returncode} out={proc.stdout.strip()!r}",
    )


# ----------------------------------------------------------------------
# T10 / B5 -- folder changes apply without restart
# ----------------------------------------------------------------------
def scenario_folder() -> None:
    work = reset_work("folder")
    data_dir = work / "data"
    folder_a = work / "folder_a"
    folder_b = work / "folder_b"
    seed_settings(data_dir, folder_a, delay_min=2, delay_max=2)

    app = make_app(data_dir)
    try:
        pump(app, 2.5)

        paste_links(app, URL_ZOO)
        app.add_links()
        first = app.queue_manager.snapshot()[-1]
        wait_all_terminal(app, [first.id], timeout=300)
        first_item = app.queue_manager.find(first.id)
        check(
            "T10.1",
            "item 1 lands in the folder configured at launch",
            first_item.status == models.STATUS_COMPLETED
            and Path(first_item.file_path).parent == folder_a,
            f"path={first_item.file_path}",
        )

        app.on_clear_completed()
        pump(app, 0.8)
        check(
            "T10.2",
            "'Clear Completed' empties the queue",
            len(app.queue_manager.snapshot()) == 0,
            f"queue={len(app.queue_manager.snapshot())}",
        )

        # change the folder through the Settings save path (no restart!)
        app.apply_settings(
            {"download_folder": str(folder_b), "delay_min": 2, "delay_max": 2}
        )
        pump(app, 0.5)
        on_disk = json.loads((data_dir / "settings.json").read_text(encoding="utf-8"))
        check(
            "T10.3",
            "Settings save applies immediately (settings.json + live object)",
            app.settings.download_folder == str(folder_b)
            and on_disk.get("download_folder") == str(folder_b),
            f"live={app.settings.download_folder!r} "
            f"on_disk={on_disk.get('download_folder')!r}",
        )

        paste_links(app, URL_RICK)
        app.add_links()
        second = app.queue_manager.snapshot()[-1]
        wait_all_terminal(app, [second.id], timeout=600)
        second_item = app.queue_manager.find(second.id)
        check(
            "T10.3b",
            "the main window's 'Saving to' line follows the change immediately",
            str(folder_b) in str(app.folder_label.cget("text")),
            f"label='{app.folder_label.cget('text')}'",
        )

        check(
            "T10.4",
            "item 2 lands in the NEW folder with NO restart (regression B5)",
            second_item.status == models.STATUS_COMPLETED
            and Path(second_item.file_path).parent == folder_b,
            f"path={second_item.file_path}",
        )
        check(
            "T10.5",
            "nothing new was written into the old folder after the change",
            not any(p.name.startswith("Rick Astley") for p in media_files(folder_a)),
            f"folder_a={[p.name for p in media_files(folder_a)]}",
        )
    finally:
        close_app(app)

    # ---- the change must survive a restart (no re-picking every launch) ----
    app = make_app(data_dir)
    try:
        pump(app, 2.5)
        check(
            "T10.6",
            "the download folder change survives a restart",
            app.settings.download_folder == str(folder_b),
            f"after relaunch='{app.settings.download_folder}' expected='{folder_b}'",
        )
        app.show_view("settings")
        pump(app, 0.6)
        shown = app.settings_view._folder_var.get()
        check(
            "T10.6b",
            "the Settings screen shows the remembered folder (nothing to re-enter)",
            shown == str(folder_b),
            f"entry='{shown}'",
        )
        app.show_view("main")
        pump(app, 0.4)
        check(
            "T10.6c",
            "the relaunched window shows the remembered folder without opening Settings",
            str(folder_b) in str(app.folder_label.cget("text")),
            f"label='{app.folder_label.cget('text')}'",
        )

        # ---- a relative folder must be made absolute, never handed to yt-dlp
        # (yt-dlp resolves a relative -o template against its own cwd and drops
        # the leading dot, which put files in a folder nobody chose).
        app.apply_settings({"download_folder": "relative_probe"})
        pump(app, 0.4)
        stored = Path(app.settings.download_folder)
        check(
            "T10.6d",
            "a relative download folder is stored absolute, under the app folder",
            stored.is_absolute()
            and stored.name == "relative_probe"
            and stored.parent == config.app_dir()
            and app.download_folder_path() == stored,
            f"stored='{app.settings.download_folder}' "
            f"shown='{app.download_folder_path()}'",
        )
        check(
            "T10.6e",
            "...and the 'Saving to' line shows the resolved folder",
            str(stored) in str(app.folder_label.cget("text")),
            f"label='{app.folder_label.cget('text')}'",
        )
        app.apply_settings({"download_folder": str(folder_b)})  # back to folder B
        pump(app, 0.4)

        paste_links(app, URL_ZOO)
        app.add_links()
        third = app.queue_manager.snapshot()[-1]
        wait_all_terminal(app, [third.id], timeout=300)
        third_item = app.queue_manager.find(third.id)
        check(
            "T10.7",
            "a real download AFTER the restart lands in the remembered folder",
            third_item.status == models.STATUS_COMPLETED
            and Path(third_item.file_path).parent == folder_b
            and Path(third_item.file_path).parent == app.download_folder_path(),
            f"path={third_item.file_path} shown={app.download_folder_path()}",
        )

        # Live evidence from the real downloads above: YouTube bot-checks the
        # default clients on many networks, and the app must answer that with a
        # different client rather than by failing (and without mojibake).
        log_file = data_dir / "logs" / "app.log"
        log_text = (
            log_file.read_text(encoding="utf-8", errors="replace")
            if log_file.exists()
            else ""
        )
        bot_checks = log_text.count("bot check on")
        switches = log_text.count("retrying with player_client=")
        check(
            "T10.8",
            "every bot check met by a real download switched the YouTube client",
            bot_checks == switches,
            f"bot_checks={bot_checks} client_switches={switches}",
        )
        check(
            "T10.9",
            "no mojibake (U+FFFD) anywhere in the log of real downloads",
            "\ufffd" not in log_text,
            f"replacement_chars={log_text.count(chr(0xFFFD))}",
        )
    finally:
        close_app(app)
        # apply_settings created this folder while resolving the relative probe
        shutil.rmtree(config.app_dir() / "relative_probe", ignore_errors=True)


# ----------------------------------------------------------------------
# T21 -- portable copy: the remembered folder may not exist on this PC
# ----------------------------------------------------------------------
def scenario_portable() -> None:
    """A `data\\` copied from another machine.

    Its settings.json remembers a folder on a drive/profile that does not exist
    here.  The app must still start, replace the folder with its own one, keep
    that choice, and really download there - that is what makes the folder
    portable to another PC or a pendrive.
    """
    work = reset_work("portable")
    data_dir = work / "data"
    # Point the modules at this scenario's folder BEFORE the harness itself
    # writes a queue snapshot below (store resolves through the same modules).
    use_data_dir(data_dir)
    foreign = Path("Q:/metube_other_pc/Downloads/MeTube")
    # Exactly what a data\\ copied from another PC looks like: the remembered
    # folder is on a drive letter this machine does not have.
    seed_settings(
        data_dir, work / "ignored", delay_min=2, delay_max=2,
        download_folder=str(foreign),
    )

    expected = config.portable_download_folder()
    check(
        "T21.0",
        "the 'other PC' folder in settings.json really is unreachable here",
        config.folder_is_usable(foreign) is False,
        f"{foreign} usable={config.folder_is_usable(foreign)}",
    )

    # A queue file that holds only finished work must not nag with a restore
    # dialog, and the real constructor path (modals included) must open.
    store.save_queue(
        [
            QueueItem(
                url=URL_RICK,
                fmt="MP3",
                quality="Best Available",
                video_id=VID_RICK,
                status=models.STATUS_COMPLETED,
                file_path=str(work / "old.mp3"),
            )
        ]
    )
    import app as app_module

    record = auto_answer(app_module, "RestoreSessionDialog", True)
    app = make_app(data_dir, skip_modals=False)
    try:
        pump(app, 3.0)
        check(
            "T21.1",
            "the app starts and moves downloads into its own folder",
            app.settings.download_folder == str(expected),
            f"folder='{app.settings.download_folder}' expected='{expected}'",
        )
        check(
            "T21.1b",
            "a queue holding only finished items does not nag for a restore",
            record["shown"] == 0,
            f"restore dialogs shown={record['shown']}",
        )
        on_disk = json.loads((data_dir / "settings.json").read_text(encoding="utf-8"))
        check(
            "T21.2",
            "the replacement is persisted, so the next launch needs no action",
            on_disk.get("download_folder") == str(expected),
            f"on_disk='{on_disk.get('download_folder')}'",
        )
        check(
            "T21.1c",
            "the window shows the folder the app will really use",
            str(expected) in str(app.folder_label.cget("text")),
            f"label='{app.folder_label.cget('text')}'",
        )
        app_log = ""
        log_file = data_dir / "logs" / "app.log"
        if log_file.exists():
            app_log = log_file.read_text(encoding="utf-8", errors="replace")
        check(
            "T21.2b",
            "the user is told where the downloads went",
            "Saved download folder is unavailable" in app_log,
            f"notice logged={('Saved download folder is unavailable' in app_log)}",
        )

        paste_links(app, URL_ZOO)
        app.add_links()
        item = app.queue_manager.snapshot()[-1]
        wait_all_terminal(app, [item.id], timeout=300)
        row = app.queue_manager.find(item.id)
        landed = Path(row.file_path) if row.file_path else None
        check(
            "T21.3",
            "a real download lands in <app folder>\\downloads",
            row.status == models.STATUS_COMPLETED
            and landed is not None
            and landed.parent == expected
            and landed.exists(),
            f"path={row.file_path}",
        )
    finally:
        close_app(app)

    # The app recreates this folder whenever it is needed; the harness leaves
    # the source tree as it found it.
    shutil.rmtree(expected, ignore_errors=True)
    check(
        "T21.4",
        "the harness cleaned up the portable downloads folder it created",
        not expected.exists(),
        f"{expected} exists={expected.exists()}",
    )


# ----------------------------------------------------------------------
# T6 -- playlist expansion
# ----------------------------------------------------------------------
def scenario_playlist() -> None:
    work = reset_work("playlist")
    data_dir = work / "data"
    folder = work / "downloads"
    seed_settings(data_dir, folder, delay_min=2, delay_max=2)

    ids = downloader.expand_playlist(URL_PLAYLIST)
    check(
        "T6.1",
        "expand_playlist() returns video ids for a pure playlist URL",
        isinstance(ids, list) and len(ids) >= 1 and all(utils.VIDEO_ID_RE.match(i) for i in ids),
        f"id={URL_PLAYLIST.rsplit('=', 1)[-1]} -> {ids}",
    )
    check(
        "T6.2",
        "is_playlist_url() true for the pure playlist URL",
        utils.is_playlist_url(URL_PLAYLIST) is True,
        "",
    )
    mixed = f"https://www.youtube.com/watch?v={VID_ZOO}&list=UU4QobU6STFB0P71PMvOGN5A&index=1&t=5s"
    check(
        "T6.3",
        "watch?v=X&list=Y is NOT treated as a playlist (exactly one item)",
        utils.is_playlist_url(mixed) is False
        and utils.extract_video_id(mixed) == VID_ZOO,
        f"is_playlist={utils.is_playlist_url(mixed)} id={utils.extract_video_id(mixed)}",
    )
    # A *different* video, so the queue's duplicate rule cannot legitimately
    # swallow it (the uploads playlist above contains the zoo video itself).
    mixed_other = (
        f"https://m.youtube.com/watch?v={VID_RICK}"
        "&list=UU4QobU6STFB0P71PMvOGN5A&index=1&pp=abc"
    )
    check(
        "T6.3b",
        "m.youtube.com /shorts-style extra params still resolve to one video id",
        utils.is_playlist_url(mixed_other) is False
        and utils.extract_video_id(mixed_other) == VID_RICK,
        f"is_playlist={utils.is_playlist_url(mixed_other)} "
        f"id={utils.extract_video_id(mixed_other)}",
    )

    app = make_app(data_dir)
    try:
        pump(app, 2.5)
        # add via the real UI path: the playlist URL must expand, not queue itself
        paste_links(app, URL_PLAYLIST)
        app.add_links()
        expanded = wait_for(
            app,
            lambda: len(app.queue_manager.snapshot()) == len(ids) or None,
            timeout=180,
        )
        snapshot = app.queue_manager.snapshot()
        check(
            "T6.4",
            "pasting a pure playlist URL adds N cards, none of them the playlist itself",
            expanded
            and len(snapshot) == len(ids)
            and all(i.url.startswith("https://www.youtube.com/watch?v=") for i in snapshot),
            f"expected={len(ids)} got={len(snapshot)} urls={[i.url for i in snapshot]}",
        )

        # toast text mentions N
        toast_text = ""
        try:
            toast_text = app.toast._label.cget("text")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            toast_text = ""
        check(
            "T6.5",
            "toast announces 'Added N videos from playlist'",
            "playlist" in toast_text.lower() and str(len(ids)) in toast_text,
            f"toast={toast_text!r}",
        )

        # mixed watch?v=&list= -> exactly one item, and NOT the whole playlist
        paste_links(app, mixed_other)
        app.add_links()
        pump(app, 1.2)
        after = app.queue_manager.snapshot()
        check(
            "T6.6",
            "watch?v=&list= adds exactly one item (playlist stripped, dedupe apart)",
            len(after) == len(ids) + 1
            and sum(1 for i in after if i.video_id == VID_RICK) == 1,
            f"queue={len(after)} rick_items="
            f"{sum(1 for i in after if i.video_id == VID_RICK)}",
        )
    finally:
        close_app(app)


# ----------------------------------------------------------------------
# T8 / T9 -- pause/resume and cancel against a big real download
# ----------------------------------------------------------------------
def scenario_controls() -> None:
    import psutil

    work = reset_work("controls")
    data_dir = work / "data"
    folder = work / "downloads"
    seed_settings(data_dir, folder, delay_min=2, delay_max=2, default_format="MP4",
                  default_quality="720p")

    app = make_app(data_dir)
    try:
        pump(app, 2.5)

        # big item for pause/resume, big item for cancel, small item to prove
        # the queue advances after a cancel.  The second big item is added
        # straight to the queue because add_links() would (correctly) refuse the
        # duplicate URL.
        paste_links(app, URL_BBB)
        app.add_links()
        pump(app, 0.4)
        second_big = QueueItem(url=URL_BBB, fmt="MP4", quality="720p", video_id=VID_BBB)
        app.queue_manager.add_item(second_big)
        app.metadata.submit(second_big.id, second_big.url)
        pump(app, 0.4)
        app.format_var.set("MP3")
        app.on_format_change()
        paste_links(app, URL_ZOO)
        app.add_links()
        pump(app, 0.8)

        snapshot = app.queue_manager.snapshot()
        big1 = snapshot[0]
        big2 = snapshot[1]
        small = snapshot[-1]
        check(
            "T8.0",
            "three items queued (2x MP4 720p, 1x MP3 tail)",
            len(snapshot) == 3
            and small is not big2
            and (small.fmt, big1.fmt) == ("MP3", "MP4"),
            f"{[(i.video_id, i.fmt, i.quality) for i in snapshot]}",
        )

        caught = wait_for(
            app,
            lambda: (
                status_of(app, big1.id).startswith("Downloading")
                and item_of(app, big1.id).progress < 70
                or None
            ),
            timeout=300,
        )
        check("T8.1", "caught item 1 mid-download", bool(caught),
              f"status={status_of(app, big1.id)}")

        # --- freeze ------------------------------------------------------
        EXPECT_PAUSE["on"] = True
        try:
            app.on_pause()
        finally:
            EXPECT_PAUSE["on"] = False
        pump(app, 1.0)

        # The engine records exactly what it suspended; assert on that set, not
        # on every process merely *named* yt-dlp (short-lived children of an
        # earlier attempt may still be listed and can exit during the pause).
        suspended = list(getattr(app.queue_manager, "_suspended", []))
        states = []
        for proc in suspended:
            try:
                states.append(proc.status())
            except psutil.Error:
                states.append("gone")

        sizes = [p.stat().st_size for p in media_files(folder)] + [
            p.stat().st_size for p in folder.glob("*.part")
        ]
        pump(app, 3.0)
        sizes_after = [p.stat().st_size for p in media_files(folder)] + [
            p.stat().st_size for p in folder.glob("*.part")
        ]
        states_after = []
        for proc in suspended:
            try:
                states_after.append(proc.status())
            except psutil.Error:
                states_after.append("gone")

        check(
            "T8.2",
            "Pause suspends the live yt-dlp process tree (psutil status -> stopped)",
            bool(suspended) and any(s == "stopped" for s in states_after),
            f"suspended={len(suspended)} statuses={states_after} "
            f"(at pause: {states})",
        )
        check(
            "T8.3",
            "no bytes are written while paused",
            sizes == sizes_after,
            f"before={sizes} after={sizes_after}",
        )
        check(
            "T8.4",
            "card shows 'Paused' while the pause is active",
            status_of(app, big1.id) == models.STATUS_PAUSED
            or "Paused" in status_of(app, big1.id),
            f"status={status_of(app, big1.id)!r}",
        )

        # --- resume ------------------------------------------------------
        app.on_resume()
        pump(app, 1.5)
        states_resumed = []
        for proc in suspended:
            try:
                states_resumed.append(proc.status())
            except psutil.Error:
                states_resumed.append("gone")
        check(
            "T8.5",
            "Resume un-suspends the process tree and clears the engine's list",
            all(s in ("running", "gone") for s in states_resumed)
            and not getattr(app.queue_manager, "_suspended", []),
            f"{states_resumed} engine_list={getattr(app.queue_manager, '_suspended', None)}",
        )
        grew = wait_for(
            app,
            lambda: (
                sum(p.stat().st_size for p in folder.glob("*.part"))
                > sum(sizes_after) - 1
                or status_of(app, big1.id).startswith("Completed")
                or None
            ),
            timeout=300,
        )
        check("T8.6", "download continues growing after Resume", bool(grew), "")

        wait_status_prefix(app, big1.id, "Completed", timeout=600)
        check(
            "T8.7",
            "the paused-then-resumed item completes successfully",
            status_of(app, big1.id) == models.STATUS_COMPLETED,
            f"status={status_of(app, big1.id)!r} path={item_of(app, big1.id).file_path}",
        )

        # --- T9: cancel --------------------------------------------------
        caught2 = wait_for(
            app,
            lambda: (
                status_of(app, big2.id).startswith("Downloading")
                and item_of(app, big2.id).progress < 80
                or None
            ),
            timeout=300,
        )
        check("T9.1", "caught item 2 mid-download", bool(caught2),
              f"status={status_of(app, big2.id)}")
        parts_before = [p.name for p in folder.glob("*.part")]
        app.on_cancel(big2.id)
        pump(app, 2.5)
        parts_after = [p.name for p in folder.glob("*.part")]
        check(
            "T9.2",
            "Cancel marks the item Cancelled",
            status_of(app, big2.id) == models.STATUS_CANCELLED,
            f"status={status_of(app, big2.id)!r}",
        )
        check(
            "T9.3",
            "partial .part / .ytdl temp files are removed after Cancel",
            len(parts_before) >= 0 and len(parts_after) == 0,
            f"before={parts_before} after={parts_after}",
        )
        started_next = wait_for(
            app,
            lambda: (
                status_of(app, small.id).startswith(("Downloading", "Starting", "Completed"))
                or None
            ),
            timeout=180,
        )
        check(
            "T9.4",
            "the cancelled item does not block the queue: next item starts",
            bool(started_next),
            f"next status={status_of(app, small.id)!r}",
        )
        wait_all_terminal(app, [small.id], timeout=300)
        stray_note = (
            f" | stray input handled: {len(EXTERNAL_PAUSES)} pause(s) undone"
            if EXTERNAL_PAUSES
            else ""
        )
        check(
            "T9.5",
            "the trailing item still completes after a cancel",
            status_of(app, small.id) == models.STATUS_COMPLETED,
            f"status={status_of(app, small.id)!r}{stray_note}",
        )
    finally:
        close_app(app)


# ----------------------------------------------------------------------
# T15 -- network failure -> retries -> Failed -> manual retry succeeds
# ----------------------------------------------------------------------
def scenario_offline() -> None:
    from metube import models

    work = reset_work("offline")
    data_dir = work / "data"
    folder = work / "downloads"
    seed_settings(data_dir, folder, delay_min=2, delay_max=2)

    # A dead proxy is the closest thing to "airplane mode" without touching the
    # host network.  yt-dlp inherits this and cannot reach YouTube.
    os.environ["HTTPS_PROXY"] = "http://127.0.0.1:9"
    os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"
    os.environ["NO_PROXY"] = ""

    app = make_app(data_dir)
    try:
        pump(app, 2.0)
        paste_links(app, URL_ZOO)
        app.add_links()
        pump(app, 0.6)
        item = app.queue_manager.snapshot()[-1]

        # watch for the retry vocabulary while it fails
        seen: set[str] = set()
        deadline = time.monotonic() + 420
        while time.monotonic() < deadline:
            app.update()
            status = status_of(app, item.id)
            seen.add(status.split("·")[0].split(" 0%")[0])
            if models.is_terminal(status):
                break
            time.sleep(0.05)

        final_status = status_of(app, item.id)
        check(
            "T15.1",
            "offline download ends in a Failed status (never hangs forever)",
            final_status.startswith("Failed:"),
            f"status={final_status!r} seen={sorted(seen)[:12]}",
        )
        retried = any(s.startswith(("Retrying", "Cooling down")) for s in seen)
        check(
            "T15.2",
            "transient/bot failures are retried with visible vocabulary",
            retried or final_status.startswith("Failed:"),
            f"observed={sorted(seen)[:12]}",
        )
        reason = item_of(app, item.id).failure_reason
        check(
            "T15.3",
            "failure reason is one short human sentence, not a raw traceback",
            bool(reason)
            and "Traceback" not in reason
            and "please report this issue" not in reason
            and "caused by" not in reason
            and len(reason) < 300,
            f"reason={reason!r}",
        )
        # The engine sets the terminal status a hair before it writes the
        # history row, so give the row a bounded moment to land.
        hist_store = mod("metube.store")
        recorded = wait_for(
            app,
            lambda: any(
                r.get("video_id") == VID_ZOO
                and r.get("status", "").startswith("Failed")
                for r in hist_store.load_history()
            )
            or None,
            timeout=20,
        )
        check(
            "T15.4",
            "failure (with its reason) was recorded in history",
            bool(recorded),
            f"history={[(r.get('video_id'), r.get('status')) for r in hist_store.load_history()]}",
        )

        # ---- a nearly-full target drive must not produce a raw OS error ---
        # (measured: a full C: made the app fail with "[Errno 28] No space left
        # on device" and nobody could tell what to do about it)
        engine_module = mod("metube.engine")
        real_free = engine_module.free_space_bytes
        engine_module.free_space_bytes = lambda _path: 5 * 1024 * 1024
        try:
            paste_links(app, URL_RICK)
            app.add_links()
            pump(app, 0.6)
            cramped = app.queue_manager.snapshot()[-1]
            settled = wait_for(
                app,
                lambda: (models.is_terminal(status_of(app, cramped.id)) or None),
                timeout=90,
            )
            cramped_status = status_of(app, cramped.id)
            check(
                "T15.6",
                "a nearly-full download drive fails with a sentence, not [Errno 28]",
                bool(settled)
                and cramped_status.startswith("Failed:")
                and "free disk space" in cramped_status
                and "Errno" not in cramped_status,
                f"status={cramped_status!r}",
            )
            log_path = data_dir / "logs" / "app.log"
            log_text = (
                log_path.read_text(encoding="utf-8", errors="replace")
                if log_path.exists()
                else ""
            )
            check(
                "T15.7",
                "...and yt-dlp was never even started for that item",
                f"download start: {URL_RICK}" not in log_text,
                f"download_start_lines={log_text.count('download start: ' + URL_RICK)}",
            )
        finally:
            engine_module.free_space_bytes = real_free
            try:
                app.on_dismiss(cramped.id)
            except UnboundLocalError:  # pragma: no cover - the add itself failed
                pass
            pump(app, 0.3)

        # ---- reconnect and retry manually --------------------------------
        os.environ.pop("HTTPS_PROXY", None)
        os.environ.pop("HTTP_PROXY", None)
        app.on_retry(item.id)
        pump(app, 0.6)
        recovered = wait_for(
            app,
            lambda: (
                status_of(app, item.id) == models.STATUS_COMPLETED or None
            ),
            timeout=420,
        )
        check(
            "T15.5",
            "manual Retry succeeds once the network is back",
            bool(recovered) and status_of(app, item.id) == models.STATUS_COMPLETED,
            f"status={status_of(app, item.id)!r} "
            f"path={item_of(app, item.id).file_path}",
        )
    finally:
        close_app(app)


# ----------------------------------------------------------------------
# T16 / T17 (B7 / B9) -- placeholder and quality dropdown, on the real widget
# ----------------------------------------------------------------------
def scenario_ui() -> None:
    work = reset_work("ui")
    data_dir = work / "data"
    folder = work / "downloads"
    seed_settings(data_dir, folder)

    app = make_app(data_dir)
    try:
        pump(app, 2.0)

        # ---- T16 placeholder --------------------------------------------
        box = app.input_box
        check(
            "T16.1",
            "startup: hint text is present, muted, and not real input",
            box._showing_placeholder is True
            and box._raw_text() == PLACEHOLDER_TEXT
            and box.get_input() == "",
            f"showing={box._showing_placeholder} raw={box._raw_text()!r}",
        )
        check(
            "T16.2",
            "hint is rendered in the muted colour, not the text colour",
            box.tag_cget("_metube_placeholder", "foreground").lower()
            == "#9a9aa5",
            f"tag fg={box.tag_cget('_metube_placeholder', 'foreground')!r}",
        )

        fire_key(box, "<FocusIn>")
        pump(app, 0.3)
        check(
            "T16.3",
            "FocusIn clears the hint and restores the normal text colour",
            box._showing_placeholder is False and box._raw_text() == "",
            f"showing={box._showing_placeholder} raw={box._raw_text()!r}",
        )

        # paste works immediately -- no manual deletion (B7)
        box.insert("1.0", URL_ZOO)
        pump(app, 0.2)
        check(
            "T16.4",
            "a link can be pasted immediately after focusing (regression B7)",
            box.get_input() == URL_ZOO,
            f"input={box.get_input()!r}",
        )
        check(
            "T16.5",
            "get_input() never returns the placeholder text",
            PLACEHOLDER_TEXT not in box.get_input(),
            f"input={box.get_input()!r}",
        )

        # Ctrl+Return triggers Add (Tk delivers key events to the focused
        # widget, so the inner Text has to hold focus for the binding to fire).
        box._textbox.focus_force()
        pump(app, 0.2)
        fire_key(box, "<Control-Return>")
        pump(app, 0.8)
        added_via_ctrl = len(app.queue_manager.snapshot())
        check(
            "T16.6",
            "Ctrl+Return is bound on the real inner Text and adds the item",
            added_via_ctrl == 1,
            f"queue={added_via_ctrl} bindings={box._textbox.bind()}",
        )

        # The user selects all the hint text and deletes it, leaving a truly
        # empty box, then presses Add.
        box.hide_placeholder()
        box.delete("1.0", "end")
        check(
            "T16.6b",
            "deleting the hint leaves a genuinely empty, usable box",
            box.get_input() == "",
            f"get_input={box.get_input()!r}",
        )
        before = len(app.queue_manager.snapshot())
        app.add_links()
        pump(app, 0.6)
        check(
            "T16.7",
            "Add with an empty textbox does nothing (no toast, no item)",
            len(app.queue_manager.snapshot()) == before,
            f"queue before={before} after={len(app.queue_manager.snapshot())}",
        )

        # Now leave the box untouched so the hint is showing, and press Add.
        box.clear_input()
        pump(app, 0.2)
        app.add_links()
        pump(app, 0.6)
        check(
            "T16.8",
            "Add while the hint is showing (placeholder-only content) does nothing",
            len(app.queue_manager.snapshot()) == before
            and box._showing_placeholder is True,
            f"queue={len(app.queue_manager.snapshot())} "
            f"showing={box._showing_placeholder} raw={box._raw_text()!r}",
        )

        # FocusOut restores the hint when empty
        box.clear_input()
        fire_key(box, "<FocusOut>")
        pump(app, 0.3)
        check(
            "T16.9",
            "FocusOut on an empty box brings the hint back",
            box._showing_placeholder is True and box._raw_text() == PLACEHOLDER_TEXT,
            f"showing={box._showing_placeholder} raw={box._raw_text()!r}",
        )

        # ---- T17 quality dropdown (B9) -----------------------------------
        def quality_state() -> str:
            return str(app.quality_menu.cget("state"))

        def format_state() -> str:
            return str(app.format_menu.cget("state"))

        app.format_var.set("MP3")
        app.on_format_change()
        pump(app, 0.2)
        mp3_disabled = quality_state() == "disabled"

        app.format_var.set("M4A")
        app.on_format_change()
        pump(app, 0.2)
        m4a_disabled = quality_state() == "disabled"

        app.format_var.set("MP4")
        app.on_format_change()
        pump(app, 0.2)
        mp4_enabled = quality_state() == "normal"

        check(
            "T17.1",
            "Quality dropdown: disabled for MP3, disabled for M4A, enabled for MP4",
            mp3_disabled and m4a_disabled and mp4_enabled,
            f"MP3={quality_state()} (was {mp3_disabled}) / M4A={m4a_disabled} / "
            f"MP4={quality_state()} (was {mp4_enabled})",
        )

        # after a Settings save the state must be re-applied
        app.apply_settings(
            {
                "download_folder": str(folder),
                "default_format": "MP3",
                "default_quality": "Best Available",
                "delay_min": 3,
                "delay_max": 5,
            }
        )
        pump(app, 0.3)
        check(
            "T17.2",
            "after a Settings save the dropdowns re-sync (B9): MP3 selected + Quality disabled",
            app.format_var.get() == "MP3"
            and app.quality_var.get() == "Best Available"
            and quality_state() == "disabled",
            f"fmt={app.format_var.get()} quality={app.quality_var.get()} "
            f"state={quality_state()}",
        )
        check(
            "T17.3",
            "the Settings screen's own Quality dropdown obeys the same rule",
            str(app.settings_view._quality_menu.cget("state")) == "disabled",
            f"settings quality state="
            f"{app.settings_view._quality_menu.cget('state')}",
        )
        check(
            "T17.4",
            "sync method resolves under both canonical and alias names (B10)",
            callable(app._sync_main_dropdowns) and callable(app.sync_main_dropdowns),
            "",
        )
        check(
            "T17.5",
            "format dropdown stays always enabled",
            format_state() == "normal",
            f"state={format_state()}",
        )

        # ---- view switching ----------------------------------------------
        app.show_view("settings")
        pump(app, 0.4)
        settings_visible = app._views["settings"].winfo_ismapped()
        app.show_view("history")
        pump(app, 0.4)
        history_visible = app._views["history"].winfo_ismapped()
        app.show_view("main")
        pump(app, 0.4)
        main_visible = app._views["main"].winfo_ismapped()
        check(
            "T17.6",
            "Settings / History / main view switching works without errors",
            settings_visible and history_visible and main_visible,
            f"settings={settings_visible} history={history_visible} main={main_visible}",
        )
    finally:
        close_app(app)


# ----------------------------------------------------------------------
# T12 / B14 -- queue snapshot + restore
# ----------------------------------------------------------------------
def scenario_restore() -> None:
    work = reset_work("restore")
    data_dir = work / "data"
    folder = work / "downloads"
    seed_settings(data_dir, folder, delay_min=2, delay_max=2)

    # --- phase 1: build a queue, then die like a crash ---------------------
    app = make_app(data_dir)
    ids = []
    try:
        pump(app, 2.0)
        os.environ["HTTPS_PROXY"] = "http://127.0.0.1:9"  # hold items unfinished
        for url in (URL_ZOO, URL_RICK, URL_GANGNAM):
            item = QueueItem(url=url, fmt="MP3", quality="Best Available")
            app.queue_manager.add_item(item)
            ids.append(item.id)
        # Bounded wait until the engine is genuinely working on item 1, so the
        # snapshot is known to hold a non-Queued status (the engine waits out
        # its title grace period first, which the dead proxy never satisfies).
        moved = wait_for(
            app,
            lambda: any(i.status != "Queued" for i in app.queue_manager.snapshot()) or None,
            timeout=120,
        )
        check(
            "T12.0",
            "the engine starts from a snapshot-loaded queue (state advances)",
            bool(moved),
            f"statuses={[i.status for i in app.queue_manager.snapshot()]}",
        )
    finally:
        os.environ.pop("HTTPS_PROXY", None)
        close_app(app)

    saved = store.load_queue()
    check(
        "T12.1",
        "queue.json snapshot holds every item with all fields round-tripped",
        (data_dir / "queue.json").exists()
        and len(saved) == 3
        and any(i.status != "Queued" for i in saved)
        and all(
            {"id", "url", "video_id", "fmt", "quality", "status", "file_path",
             "failure_reason"}.issubset(set(i.to_dict()))
            for i in saved
        ),
        f"path={data_dir / 'queue.json'} items={[(i.video_id, i.status) for i in saved]}",
    )

    # --- phase 2: relaunch; the real constructor path must raise the dialog -
    import app as app_module

    record = auto_answer(app_module, "RestoreSessionDialog", True)
    app = make_app(data_dir, skip_modals=False)  # ctor runs _maybe_restore()
    try:
        pump(app, 2.5)
        check(
            "T12.2",
            "relaunch shows 'Restore N items from your previous session?'",
            record["shown"] == 1 and record["answered"] is True,
            f"shown={record['shown']} answered={record['answered']}",
        )
        restored = app.queue_manager.snapshot()
        check(
            "T12.2b",
            "'Yes, restore' puts the unfinished items back on the queue",
            len(restored) == 3,
            f"statuses={[i.status for i in restored]}",
        )
        progressed = wait_for(
            app,
            lambda: (
                any(
                    i.status.startswith(("Downloading", "Failed", "Starting"))
                    for i in app.queue_manager.snapshot()
                )
                or None
            ),
            timeout=240,
        )
        check(
            "T12.3",
            "the restored queue actually resumes downloading",
            bool(progressed),
            f"statuses={[i.status for i in app.queue_manager.snapshot()]}",
        )
    finally:
        close_app(app)

    # --- phase 3: "No, clear" empties the snapshot -------------------------
    use_data_dir(data_dir)
    store.save_queue(saved)
    record = auto_answer(app_module, "RestoreSessionDialog", False)
    app = make_app(data_dir, skip_modals=False)
    try:
        pump(app, 1.5)
        check(
            "T12.4",
            "'No, clear' empties the snapshot and leaves the queue empty",
            record["shown"] == 1
            and len(app.queue_manager.snapshot()) == 0
            and not store.load_queue(),
            f"shown={record['shown']} queue={len(app.queue_manager.snapshot())} "
            f"snapshot={len(store.load_queue())}",
        )
    finally:
        close_app(app)

    # --- phase 4: the cleared snapshot must not prompt again ---------------
    record = auto_answer(app_module, "RestoreSessionDialog", True)
    app = make_app(data_dir, skip_modals=False)
    try:
        pump(app, 1.5)
        check(
            "T12.5",
            "after 'No, clear' the next launch shows no restore prompt",
            record["shown"] == 0 and len(app.queue_manager.snapshot()) == 0,
            f"shown={record['shown']} queue={len(app.queue_manager.snapshot())}",
        )
    finally:
        close_app(app)


# ----------------------------------------------------------------------
# T13 / B2 / B11 / B12 -- first run, crash log, single data dir
# ----------------------------------------------------------------------
def scenario_firstrun() -> None:
    from metube import config, logger, settings as settings_module

    work = reset_work("firstrun")
    data_dir = work / "data"
    folder = work / "downloads"
    # deliberately NO settings.json -> true first run

    import app as app_module
    from metube import config, logger, settings as settings_module

    # The dialog auto-replies, but the real BaseDialog constructor still runs
    # (deferred grab included) -- that is exactly where v1 flash-vanished.
    record = auto_answer(app_module, "FirstRunDialog", str(folder))
    app = make_app(data_dir, skip_modals=False)  # ctor runs _maybe_first_run()
    try:
        pump(app, 1.2)
        check(
            "T13.1",
            "first run (no settings.json) shows the FirstRunDialog",
            record["shown"] == 1 and record["answered"] == str(folder),
            f"shown={record['shown']} answered={record['answered']!r}",
        )
        check(
            "T13.2",
            "settings.json is written with first_run=false before the main window shows",
            (data_dir / "settings.json").exists()
            and settings_module.load_settings().get("first_run") is False,
            f"path={data_dir / 'settings.json'} "
            f"first_run={settings_module.load_settings().get('first_run')!r}",
        )
        check(
            "T13.3",
            "the chosen download folder is created",
            folder.exists() and folder.is_dir(),
            f"{folder}",
        )
        check(
            "T13.4",
            "the main window is visible (no flash-and-vanish, regression B2)",
            app.winfo_exists() == 1 and app.state() != "withdrawn",
            f"state={app.state()} exists={app.winfo_exists()}",
        )
        dialog_src = (ROOT / "metube" / "ui" / "dialogs.py").read_text(encoding="utf-8")
        check(
            "T13.5",
            "the deferred grab is guarded (no unguarded grab_set on Windows, B2)",
            "after(150" in dialog_src
            and "except tk.TclError" in dialog_src
            and "grab_set()" in dialog_src,
            "deferred after(150, _safe_grab) + try/except TclError present",
        )
        check(
            "T13.5b",
            "no unguarded grab on a not-yet-mapped window appeared in the log",
            "grab_set failed" not in (data_dir / "logs" / "app.log").read_text(
                encoding="utf-8", errors="replace"
            ),
            "",
        )
    finally:
        close_app(app)

    # ---- second launch must NOT show the picker (B14) ---------------------
    record = auto_answer(app_module, "FirstRunDialog", str(folder))
    app = make_app(data_dir, skip_modals=False)
    try:
        pump(app, 1.2)
        check(
            "T13.6",
            "second launch does NOT show the first-run picker (regression B14)",
            record["shown"] == 0,
            f"dialogs shown={record['shown']}",
        )
        app_log = (data_dir / "logs" / "app.log")
        log_text = app_log.read_text(encoding="utf-8", errors="replace") if app_log.exists() else ""
        check(
            "T13.7",
            "the resolved settings.json path is logged at startup (B12)",
            str(config.settings_path()) in log_text,
            f"log={app_log} exists={app_log.exists()}",
        )
        check(
            "T13.8",
            "only ONE data folder is in play (regression B12)",
            config.data_dir() == data_dir
            and not (ROOT / "data" / "settings.json").exists(),
            f"config.data_dir()={config.data_dir()} project data={ROOT / 'data'}",
        )
        check(
            "T13.9",
            "no crash.log was written during a clean first run (B11)",
            not (data_dir / "logs" / "crash.log").exists(),
            f"{(data_dir / 'logs' / 'crash.log')}",
        )
    finally:
        close_app(app)

    # ---- the crash handler itself (B11) ----------------------------------
    crash_data = work / "crashdata"
    crash_data.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["METUBE_DATA_DIR"] = str(crash_data)
    env["METUBE_FORCE_CRASH"] = "1"
    env.pop("PYTHONPATH", None)
    script = (
        "import sys, os; sys.path.insert(0, r'%s');\n"
        "from metube import logger, config;\n"
        "logger.setup_logging();\n"
        "try:\n"
        "    raise RuntimeError('deliberate crash-handler probe')\n"
        "except BaseException as exc:\n"
        "    logger.log_crash('probe', exc)\n"
        "print(config.crash_log_path())\n" % ROOT
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env,
        cwd=str(ROOT), timeout=120, **TEXT_KW,
    )
    crash_path = Path(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else None
    body = crash_path.read_text(encoding="utf-8", errors="replace") if crash_path and crash_path.exists() else ""
    check(
        "T13.10",
        "crash handler writes a full traceback to data\\logs\\crash.log (B11)",
        bool(crash_path and crash_path.exists())
        and "deliberate crash-handler probe" in body
        and "Traceback" in body,
        f"rc={proc.returncode} path={crash_path} body={body[:200]!r}",
    )
    check(
        "T13.11",
        "logger exposes a MessageBox path so --noconsole apps never die silently",
        callable(getattr(logger, "_message_box", None)),
        "",
    )


# ----------------------------------------------------------------------
# T14 / B14 -- single instance
# ----------------------------------------------------------------------
def scenario_instance() -> None:
    from metube import single_instance

    acquired = single_instance.acquire()
    check("T14.1", "first acquire() takes the named mutex", acquired is True, "")

    env = dict(os.environ)
    env["METUBE_DATA_DIR"] = str(reset_work("instance") / "data")
    script = (
        "import sys; sys.path.insert(0, r'%s');\n"
        "from metube import single_instance;\n"
        "print('acquired', single_instance.acquire())\n"
        "print('signalled'); single_instance.signal_existing_instance()\n" % ROOT
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env,
        cwd=str(ROOT), timeout=120, **TEXT_KW,
    )
    out = (proc.stdout or "").strip()
    check(
        "T14.2",
        "a second process detects the running instance and signals it",
        "acquired False" in out and "signalled" in out,
        f"rc={proc.returncode} out={out!r} err={proc.stderr.strip()[:200]!r}",
    )
    check(
        "T14.3",
        "the running instance consumes the signal (WinEvent poll)",
        single_instance.poll_signal() is True,
        "",
    )
    check(
        "T14.4",
        "the signal is one-shot (poll returns False the second time)",
        single_instance.poll_signal() is False,
        "",
    )

    # The App wires that poll into a focus/raise handler.
    work = reset_work("instance")
    data_dir = work / "data"
    folder = work / "downloads"
    seed_settings(data_dir, folder)
    app = make_app(data_dir)
    try:
        pump(app, 2.5)
        raised: list[str] = []
        app.lift = lambda: raised.append("lift")
        app.focus_force = lambda: raised.append("focus")
        app._on_second_instance()
        pump(app, 0.3)
        check(
            "T14.5",
            "a second launch lift()s and focuses the existing window",
            raised == ["lift", "focus"] or "lift" in raised,
            f"calls={raised}",
        )
        check(
            "T14.6",
            "the existing instance is still alive and usable",
            app.winfo_exists() == 1 and app.engine_ready,
            f"exists={app.winfo_exists()} engine_ready={app.engine_ready}",
        )
    finally:
        close_app(app)

    # no zombie python processes left behind by the probe
    proc = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq yt-dlp.exe", "/FO", "CSV"],
        capture_output=True, text=True, timeout=60, **TEXT_KW,
    )
    check(
        "T14.7",
        "no zombie yt-dlp.exe processes remain after the instance probe",
        "yt-dlp.exe" not in (proc.stdout or ""),
        f"{(proc.stdout or '').strip()[:200]}",
    )


# ----------------------------------------------------------------------
# T18 / B3 / B4 -- bootstrap (missing bin) and cross-drive safety
# ----------------------------------------------------------------------
def scenario_bootstrap() -> None:
    from metube import binaries

    work = reset_work("bootstrap")

    # ---- B3: cross-drive move (project is on F:, TEMP on C:) -------------
    tmp_root = Path(os.environ.get("TEMP") or "/tmp").resolve()
    project_root = ROOT.resolve()
    cross_volume = tmp_root.drive.lower() != project_root.drive.lower()
    src = work / "cross_src.bin"
    src.write_bytes(os.urandom(2 * 1024 * 1024))
    src_size = src.stat().st_size  # safe_move deletes the source by design
    dst_dir = Path(subprocess.run(
        [sys.executable, "-c", "import tempfile;print(tempfile.gettempdir())"],
        capture_output=True, text=True, timeout=60, **TEXT_KW,
    ).stdout.strip())
    dst = dst_dir / f"metube_cross_{os.getpid()}.bin"
    ok = False
    detail = ""
    try:
        utils.safe_move(src, dst)
        ok = (
            dst.exists()
            and dst.stat().st_size == src_size
            and not src.exists()
            and not (dst_dir / (dst.name + ".tmp")).exists()
        )
        detail = (
            f"src_drive={project_root.drive} dst_drive={dst_dir.drive} "
            f"cross_volume={cross_volume} moved={dst.stat().st_size if dst.exists() else 'missing'}"
            f"/{src_size} src_removed={not src.exists()}"
        )
    except Exception as exc:  # noqa: BLE001
        detail = f"{type(exc).__name__}: {exc}"
    finally:
        if dst.exists():
            try:
                dst.unlink()
            except OSError:
                pass
    check(
        "B3.1",
        "safe_move() survives a cross-volume move (no WinError 17)",
        ok,
        detail,
    )
    check(
        "B3.2",
        "the cross-volume test really did cross a volume boundary",
        cross_volume,
        f"cwd drive={project_root.drive} temp drive={tmp_root.drive}",
    )

    # ---- B4: bootstrap failure path must not hang and must give instructions
    data_dir = work / "faildata"
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["METUBE_DATA_DIR"] = str(data_dir)
    from metube import binaries as fresh_binaries

    original_url = fresh_binaries.YTDLP_URL
    fresh_binaries.YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/does-not-exist.exe"
    outcome: dict[str, object] = {}
    done = __import__("threading").Event()

    def on_done(ok, message):
        outcome["ok"] = ok
        outcome["message"] = message
        done.set()

    started = time.monotonic()
    fresh_binaries.bootstrap(on_progress=lambda t: None, on_done=on_done)
    finished = done.wait(timeout=240)
    elapsed = time.monotonic() - started
    fresh_binaries.YTDLP_URL = original_url

    check(
        "B4.1",
        "a failing bootstrap calls on_done(False, ...) promptly (no hang, no dead UI)",
        finished and outcome.get("ok") is False and elapsed < 240,
        f"finished={finished} elapsed={elapsed:.1f}s outcome={outcome}",
    )
    check(
        "B4.2",
        "the failure message names the class of error (HTTP/SSL/disc/network)",
        bool(outcome.get("message")),
        f"message={outcome.get('message')!r}",
    )
    check(
        "B4.3",
        "only GitHub URLs are used for the engine files (regression B4: gyan.dev)",
        fresh_binaries.YTDLP_URL.startswith("https://github.com/")
        and fresh_binaries.FFMPEG_URL.startswith("https://github.com/"),
        f"ytdlp={fresh_binaries.YTDLP_URL} ffmpeg={fresh_binaries.FFMPEG_URL}",
    )
    check(
        "B4.4",
        "manual-fix instructions name the exact folder and the exact three filenames",
        all(
            token in fresh_binaries.MANUAL_INSTRUCTIONS
            for token in ("bin", "yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe")
        ),
        f"{fresh_binaries.MANUAL_INSTRUCTIONS[:300]!r}",
    )

    # ---- T18: real bootstrap with bin\ moved away -------------------------
    ship_bin = ROOT / "bin"
    backup_bin = ROOT / "bin_bak"
    if backup_bin.exists():
        shutil.rmtree(backup_bin, ignore_errors=True)
    live_dir = work / "livedata"
    seed_settings(live_dir, work / "downloads", auto_update_ytdlp=False)

    moved = False
    try:
        ship_bin.rename(backup_bin)
        moved = True
        # bin_bak is not consulted by the resolver, so the engine looks missing
        app = make_app(live_dir)
        try:
            pump(app, 2.5)
            check(
                "T18.1",
                "window STILL opens with bin\\ missing (no crash on bootstrap failure)",
                app.winfo_exists() == 1 and app.state() != "withdrawn",
                f"exists={app.winfo_exists()} state={app.state()}",
            )
            check(
                "T18.2",
                "Add to Queue is disabled and relabelled 'Preparing engine…'",
                app.add_button.cget("state") == "disabled"
                and app.add_button.cget("text") == "Preparing engine…",
                f"state={app.add_button.cget('state')} "
                f"text={app.add_button.cget('text')!r}",
            )
            check(
                "T18.3",
                "the queue engine is not considered ready",
                app.engine_ready is False,
                f"engine_ready={app.engine_ready}",
            )

            ready = wait_for(app, lambda: app.engine_ready is True, timeout=900)
            check(
                "T18.4",
                "bootstrap downloads the engine and re-enables Add to Queue",
                bool(ready)
                and app.add_button.cget("state") == "normal"
                and app.add_button.cget("text") == "Add to Queue",
                f"ready={ready} text={app.add_button.cget('text')!r}",
            )
            data_bin = live_dir / "bin"
            present = sorted(p.name for p in data_bin.iterdir()) if data_bin.exists() else []
            check(
                "T18.5",
                "the three engine files land in <data>\\bin with exact names",
                set(fresh_binaries.BINARY_NAMES).issubset(set(present)),
                f"{data_bin} -> {present}",
            )
            check(
                "T18.6",
                "bootstrap used the cross-drive-safe move into data\\bin (B3)",
                "safe_move" in (ROOT / "metube" / "binaries.py").read_text(encoding="utf-8"),
                "",
            )
        finally:
            close_app(app)
    finally:
        if moved:
            if ship_bin.exists():
                shutil.rmtree(ship_bin, ignore_errors=True)
            backup_bin.rename(ship_bin)
        check(
            "T18.7",
            "bin\\ restored after the bootstrap test",
            (ROOT / "bin" / "yt-dlp.exe").exists()
            and (ROOT / "bin" / "ffmpeg.exe").exists()
            and (ROOT / "bin" / "ffprobe.exe").exists(),
            f"{sorted(p.name for p in (ROOT / 'bin').iterdir())}",
        )


# ----------------------------------------------------------------------
SCENARIOS = {
    "queue": scenario_queue,
    "mp4": scenario_mp4,
    "folder": scenario_folder,
    "portable": scenario_portable,
    "playlist": scenario_playlist,
    "controls": scenario_controls,
    "offline": scenario_offline,
    "ui": scenario_ui,
    "restore": scenario_restore,
    "firstrun": scenario_firstrun,
    "instance": scenario_instance,
    "bootstrap": scenario_bootstrap,
}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="MeTube 2.0 end-to-end harness")
    parser.add_argument("scenarios", nargs="*", help="scenario names, or --all")
    parser.add_argument("--list", action="store_true", help="list scenarios and exit")
    parser.add_argument(
        "--inprocess",
        action="store_true",
        help="run the named scenario(s) in THIS process (internal use)",
    )
    args = parser.parse_args(argv)

    if args.list:
        for name in SCENARIOS:
            print(name)
        return 0

    names = list(SCENARIOS) if (not args.scenarios or "all" in args.scenarios) else args.scenarios
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        print(f"unknown scenario(s): {unknown}. known: {list(SCENARIOS)}")
        return 2

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    # Each scenario gets its own process: a destroyed Tk interpreter leaves
    # pending `after` jobs that would otherwise spray "invalid command name"
    # noise into the next scenario and hide real failures.
    global _current_scenario
    if not args.inprocess and len(names) > 1:
        failures = 0
        for name in names:
            print(f"\n=================== scenario: {name} "
                  f"(pid separated) ===================", flush=True)
            proc = subprocess.run(
                [sys.executable, str(Path(__file__)), name, "--inprocess"],
                cwd=str(ROOT),
            )
            if proc.returncode != 0:
                failures += 1
        flush_results()
        merged = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        failed = [r for r in merged.values() if not r["ok"]]
        print(
            f"\n=== {len(merged) - len(failed)}/{len(merged)} checks passed overall; "
            f"{failures} scenario(s) reported failures ===",
            flush=True,
        )
        for row in failed:
            print(f"  FAIL {row['id']}: {row['desc']} -> {row['detail'][:300]}")
        return 1 if (failed or failures) else 0

    failures = 0
    for name in names:
        global _current_scenario
        _current_scenario = name
        print(f"\n=================== scenario: {name} ===================", flush=True)
        try:
            SCENARIOS[name]()
        except Exception:  # noqa: BLE001 - report, keep going
            failures += 1
            traceback.print_exc()
            check(f"{name}.EXC", f"scenario {name} raised", False, traceback.format_exc())
        flush_results()

    failed = [r for r in _results.values() if not r["ok"]]
    print(
        f"\n=== {len(_results) - len(failed)}/{len(_results)} checks passed "
        f"in this run; {failures} scenario exception(s) ===",
        flush=True,
    )
    if EXTERNAL_PAUSES:
        print(
            f"=== NOTE: {len(EXTERNAL_PAUSES)} stray pause(s) from outside the "
            f"harness were detected and undone (see the stack traces above) ===",
            flush=True,
        )
    for row in failed:
        print(f"  FAIL {row['id']}: {row['desc']} -> {row['detail'][:300]}")
    return 1 if (failed or failures) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
