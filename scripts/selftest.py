"""T20 - MeTube self test.

Two halves:

* static scan - every ``self.X`` call inside ``app.py``'s ``App`` class must
  resolve to a defined method or an inherited Tk/CTk method, and the
  regression guarantees that are checkable from source (single sanitizer,
  single data-dir resolver, one customtkinter import per file, no bare
  except, no non-daemon threads) are asserted.
* runtime - construct ``App`` WITHOUT ``mainloop``, pump ``update()`` ~50
  times, and assert every attribute the handlers read actually exists.

Exit code 0 = pass.
"""

from __future__ import annotations

import ast
import os
import re
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import customtkinter as ctk  # noqa: E402  (imported once, after sys.path fix)

from metube import binaries  # noqa: E402
from metube import config  # noqa: E402
from metube import downloader  # noqa: E402
from metube import engine  # noqa: E402
from metube import utils  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0
_SCRATCH_DL: Path | None = None


def scratch_download_folder() -> Path:
    """A throwaway download folder for the checks that need a real path.

    It lives in the system temp dir rather than in the project root: a folder
    created next to the sources survived every run and looked like app data,
    while the checks only need somewhere that is a legal, writable path.
    """
    global _SCRATCH_DL
    if _SCRATCH_DL is None:
        _SCRATCH_DL = Path(tempfile.mkdtemp(prefix="metube_selftest_dl_"))
    return _SCRATCH_DL


def check(condition: bool, label: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}" + (f" :: {detail}" if detail else ""))
        FAILURES.append(label)


def app_files() -> list[Path]:
    """Files that ship as the application (scripts/ is build tooling)."""
    files = [ROOT / "app.py"]
    files += sorted((ROOT / "metube").rglob("*.py"))
    return [f for f in files if f.is_file()]


def source_files() -> list[Path]:
    return app_files() + sorted((ROOT / "scripts").rglob("*.py"))


# ----------------------------------------------------------------------
# static scans
# ----------------------------------------------------------------------
def scan_app_class() -> tuple[set[str], set[str], set[str]]:
    """Return (methods, assigned_attrs, all_self_references) for App."""
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    app_cls = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    methods = {
        node.name
        for node in app_cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    called: set[str] = set()
    read: set[str] = set()
    assigned: set[str] = set()
    for node in ast.walk(app_cls):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            target = node.func.value
            if isinstance(target, ast.Name) and target.id == "self":
                called.add(node.func.attr)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id != "self":
                continue
            if isinstance(node.ctx, ast.Store):
                assigned.add(node.attr)
            else:
                read.add(node.attr)
    return methods, assigned, called | read


def static_checks() -> tuple[set[str], set[str], set[str]]:
    print("\n[static] app.py App class resolution")
    methods, assigned, referenced = scan_app_class()

    inherited = set(dir(ctk.CTk))
    unresolved = sorted(
        name
        for name in referenced
        if name not in methods and name not in assigned and name not in inherited
    )
    check(not unresolved, "every self.X referenced in app.py resolves", ", ".join(unresolved))

    print("\n[static] duplicate / hygiene rules")
    sources = {path: path.read_text(encoding="utf-8") for path in source_files()}

    # one sanitizer
    sanitizers = [
        p.relative_to(ROOT).as_posix()
        for p, text in sources.items()
        if re.search(r"^def sanitize_filename\(", text, re.M)
    ]
    check(sanitizers == ["metube/utils.py"], "exactly one sanitize_filename", str(sanitizers))

    # one data-dir resolution
    for func in ("data_dir", "settings_path", "queue_path", "history_path", "logs_dir", "thumbs_dir"):
        owners = [
            p.relative_to(ROOT).as_posix()
            for p, text in sources.items()
            if re.search(rf"^def {func}\(", text, re.M)
        ]
        check(owners == ["metube/config.py"], f"exactly one {func}()", str(owners))

    # one canonical dropdown sync + alias
    sync_defs = [p.relative_to(ROOT).as_posix() for p, t in sources.items()
                 if re.search(r"^    def _sync_main_dropdowns\(", t, re.M)]
    check(sync_defs == ["app.py"], "one _sync_main_dropdowns definition", str(sync_defs))
    check(
        re.search(r"^    def sync_main_dropdowns\(", sources[ROOT / "app.py"], re.M) is not None,
        "sync_main_dropdowns alias exists (B10)",
    )

    # customtkinter discipline: one import per file, no bare-name references
    offenders = []
    for path in app_files():
        text = sources[path]
        if "import customtkinter" not in text:
            continue
        if text.count("import customtkinter") != 1:
            offenders.append(f"{path.name}: multiple imports")
        body = re.sub(r"(?m)^\s*import customtkinter.*$", "", text)
        if re.search(r"(?<![\w.])customtkinter\.", body):
            offenders.append(f"{path.name}: bare customtkinter reference")
    check(not offenders, "one customtkinter import per file, no bare references (B1/B13)", "; ".join(offenders))

    # no bare except
    bare = []
    for path in source_files():
        tree = ast.parse(sources[path])
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                bare.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    check(not bare, "zero bare except clauses", ", ".join(bare))

    # every Thread is daemon
    non_daemon = []
    for path in source_files():
        tree = ast.parse(sources[path])
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name != "Thread":
                continue
            daemon = any(
                kw.arg == "daemon" and getattr(kw.value, "value", None) is True
                for kw in node.keywords
            )
            always_daemon = False
            # threads created via binaries.bootstrap / worker-entrypoint helpers
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == "binaries":
                    always_daemon = True
            if not daemon and not always_daemon:
                non_daemon.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    check(not non_daemon, "every threading.Thread is daemon=True", ", ".join(non_daemon))

    # no wildcard / duplicate import lines
    dupes = []
    for path, text in sources.items():
        seen: set[str] = set()
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and " as " not in stripped:
                if stripped in seen:
                    dupes.append(f"{path.relative_to(ROOT)}: {stripped}")
                seen.add(stripped)
    check(not dupes, "no duplicate plain import lines (B13)", "; ".join(dupes))

    return methods, assigned, referenced


# ----------------------------------------------------------------------
# runtime
# ----------------------------------------------------------------------
def runtime_checks(referenced: set[str]) -> None:
    print("\n[runtime] construct App without mainloop and pump update()")
    # main() already pointed METUBE_DATA_DIR at a scratch dir; the data-dir
    # resolution is cached, so drop the cache to be sure the runtime checks use
    # that scratch dir rather than anything resolved earlier in this process.
    config._cached_data_dir = None
    config._cached_data_dir_reason = ""

    # a settings.json so the first-run modal is not triggered
    import json

    config.settings_path().write_text(
        json.dumps({"first_run": False, "download_folder": str(scratch_download_folder())}),
        encoding="utf-8",
    )

    from app import App

    app = App(skip_modals=True, autostart=False)
    try:
        for _ in range(50):
            app.update()

        methods, assigned, _ = scan_app_class()
        inherited = set(dir(ctk.CTk))
        missing = sorted(
            name
            for name in referenced
            if not hasattr(app, name)
            and name not in methods
            and name not in assigned
            and name not in inherited
        )
        check(not missing, "every attribute read by handlers exists after construction", ", ".join(missing))

        for widget in (
            "add_button", "format_menu", "quality_menu", "input_box", "queue_frame",
            "progress_label", "overall_bar", "pause_button", "clear_button",
            "cancel_all_button", "history_button", "settings_button",
            "queue_count_label", "empty_label", "settings_view", "history_view", "toast",
            "folder_label",
        ):
            check(hasattr(app, widget), f"widget self.{widget} exists")

        check(
            app.settings.download_folder in str(app.folder_label.cget("text")),
            "the 'Saving to' line names the configured download folder",
        )
        changed = config.data_dir() / "folder_label_probe"
        app.settings["download_folder"] = str(changed)
        app._sync_folder_label()
        app.update()
        # The line shortens very long paths (a temp path is longer than the
        # label's 72-character cap), so compare the part it is guaranteed to
        # keep: the tail of the path.
        wanted = str(changed)
        wanted = wanted if len(wanted) <= 72 else wanted[-71:]
        check(
            wanted in str(app.folder_label.cget("text")),
            "the 'Saving to' line follows a folder change",
        )

        app.format_var.set("MP3")
        app.on_format_change()
        app.update()
        check(app.quality_menu.cget("state") == "disabled", "quality disabled for MP3 (B9)")
        app.format_var.set("MP4")
        app.on_format_change()
        app.update()
        check(app.quality_menu.cget("state") == "normal", "quality enabled for MP4")
        app.format_var.set("M4A")
        app.on_format_change()
        app.update()
        check(app.quality_menu.cget("state") == "disabled", "quality disabled for M4A (B9)")

        check(app.input_box.get_input() == "", "placeholder is not real input (B7)")
        before = len(app.cards)
        app.add_links()
        check(len(app.cards) == before, "Add with placeholder-only content does nothing")

        app.show_view("settings")
        app.update()
        app.show_view("history")
        app.update()
        app.show_view("main")
        app.update()
        check(app._current_view == "main", "view switching works")

        app.queue_manager.shutdown()
    finally:
        try:
            app.destroy()
        except Exception:  # noqa: BLE001
            pass


# ----------------------------------------------------------------------
# bot-check client ladder (offline: argv shape only, no download)
# ----------------------------------------------------------------------
def client_ladder_checks() -> None:
    """The player-client fallback must be argv-correct and engine-independent.

    YouTube answers its default clients with a bot check far more often than it
    used to; the app answers that by asking with a different client.  These
    checks pin the argv shape down without touching the network or bin\\.
    """
    print("\n[ladder] player-client fallback (offline)")
    check(
        bool(downloader.BOT_CLIENT_FALLBACKS)
        and len(set(downloader.BOT_CLIENT_FALLBACKS)) == len(downloader.BOT_CLIENT_FALLBACKS),
        "a non-empty, non-repeating player-client ladder exists",
        f"{downloader.BOT_CLIENT_FALLBACKS}",
    )

    bot_stderr = (
        "ERROR: [youtube] jNQXAC9IVRw: Sign in to confirm you're not a bot. "
        "Use --cookies-from-browser or --cookies for the authentication."
    )
    kind, _reason = downloader.classify_failure(bot_stderr)
    check(
        kind == downloader.BOT,
        "a real bot check is classified as BOT (so the ladder is reached)",
        f"kind={kind}",
    )

    # Engine-independent: the exe path is irrelevant to the argv shape.
    original_base = downloader._base_argv
    downloader._base_argv = lambda: ["yt-dlp.exe"]
    try:
        from metube.models import QueueItem

        item = QueueItem(url="https://www.youtube.com/watch?v=jNQXAC9IVRw", fmt="MP3")
        plain, _ = downloader.build_command(item, scratch_download_folder())
        with_client, _ = downloader.build_command(
            item, scratch_download_folder(), player_client="android"
        )
        check(
            "--extractor-args" not in plain,
            "the first attempt uses yt-dlp's own default clients",
            f"argv={plain[:4]}...",
        )
        index = with_client.index("--extractor-args")
        check(
            with_client[index + 1] == "youtube:player_client=android"
            and with_client[-1] == item.url
            and with_client.count(item.url) == 1,
            "a client override is passed as --extractor-args youtube:player_client=...",
            f"{with_client[index:index + 2]} url_last={with_client[-1] == item.url} "
            f"url_count={with_client.count(item.url)}",
        )
    finally:
        downloader._base_argv = original_base

    check(
        0 < engine.BOT_SWITCH_WAITS < engine.COOLDOWN_WAITS[0],
        "a client switch happens quickly; long cooldowns stay for rate limits",
        f"switch={engine.BOT_SWITCH_WAITS} cooldowns={engine.COOLDOWN_WAITS}",
    )
    check(
        engine.TITLE_GRACE_SECONDS >= 8.0,
        "the title grace period covers a metadata lookup that walks the ladder",
        f"grace={engine.TITLE_GRACE_SECONDS}",
    )

    # yt-dlp writes 0x92 (the ANSI code page's curly apostrophe) on a piped
    # stderr even with PYTHONIOENCODING=utf-8.  Decoding that as UTF-8 with
    # errors='replace' turned "you're not a bot" into "you?re not a bot", which
    # the BOT markers did not match - so the ladder above never ran.
    raw = "ERROR: [youtube] X: Sign in to confirm you\x92re not a bot.".encode("latin-1")
    decoded = downloader.decode_output(raw)
    check(
        "\ufffd" not in decoded and "you\u2019re" in decoded,
        "a 0x92 (code page) apostrophe from yt-dlp is decoded, not mangled",
        f"{decoded[-40:]!r}",
    )
    check(
        downloader.classify_failure(decoded)[0] == downloader.BOT,
        "a bot check is still classified as BOT after a lossy decode",
        f"{downloader.classify_failure(decoded)}",
    )
    check(
        downloader.classify_failure("Sign in to confirm you\ufffdre not a bot")[0]
        == downloader.BOT,
        "...even when the apostrophe already arrived as U+FFFD",
    )

    # A relative download folder must never reach yt-dlp: it resolves relative
    # -o templates against its own cwd and drops the leading dot.
    relative = config.resolve_download_folder("downloads")
    dotted = config.resolve_download_folder(".media")
    absolute = config.resolve_download_folder(str(ROOT / "somewhere"))
    check(
        relative.is_absolute() and relative == config.app_dir() / "downloads",
        "a relative folder is resolved against the MeTube folder",
        f"{relative}",
    )
    check(
        dotted.is_absolute() and dotted.name == ".media",
        "a leading dot survives the resolution (yt-dlp would strip it)",
        f"{dotted}",
    )
    check(
        absolute == ROOT / "somewhere",
        "an absolute folder is left untouched",
        f"{absolute}",
    )

    # Disk-full has to arrive as a sentence the user can act on (measured: a
    # full system drive produced "[Errno 28] No space left on device" from deep
    # inside the tools, and nothing told the user what to do).
    free = utils.free_space_bytes(ROOT)
    check(
        free is not None and free > 0,
        "free space of a real folder is readable",
        f"{utils.human_mb(free or 0)} free",
    )
    check(
        utils.free_space_bytes(ROOT / "definitely" / "not" / "here") is None,
        "an unreadable path reports 'unknown' instead of raising",
    )
    reason = engine.no_space_reason(5 * 1024 * 1024, ROOT)
    check(
        reason.startswith("not enough free disk space")
        and "5 MB" in reason
        and "Retry" in reason
        and "Errno" not in reason,
        "the disk-full reason names the free space, the drive and Retry",
        f"{reason!r}",
    )
    check(
        engine.MIN_FREE_SPACE_BYTES >= 50 * 1024 * 1024,
        "the download free-space floor is not so low that it is pointless",
        f"{utils.human_mb(engine.MIN_FREE_SPACE_BYTES)}",
    )
    check(
        binaries.MIN_BOOTSTRAP_FREE_BYTES > binaries.ZIP_FREE_BYTES > 0,
        "the engine bootstrap checks both the download drive and the temp drive",
        f"dest={utils.human_mb(binaries.MIN_BOOTSTRAP_FREE_BYTES)} "
        f"temp={utils.human_mb(binaries.ZIP_FREE_BYTES)}",
    )


def main() -> int:
    print("=" * 68)
    print("MeTube self test (T20)")
    print("=" * 68)
    # Point the path helpers at a scratch data dir BEFORE any check runs.  The
    # static checks only read text, but the client-ladder check calls
    # downloader.build_command -> binaries.ffmpeg_location -> config.data_bin_dir,
    # which resolves the data folder on first use and creates it while probing
    # that it is writable.  Without this line a plain `python scripts/selftest.py`
    # left an empty <root>\data behind - a second data folder in the project
    # tree, which is exactly what the one-data-dir rule (B12) exists to stop.
    os.environ["METUBE_DATA_DIR"] = tempfile.mkdtemp(prefix="metube_selftest_")
    referenced: set[str] = set()
    try:
        _, _, referenced = static_checks()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        FAILURES.append("static checks raised")
    try:
        client_ladder_checks()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        FAILURES.append("client ladder checks raised")
    try:
        runtime_checks(referenced)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        FAILURES.append("runtime checks raised")

    print("\n" + "=" * 68)
    if FAILURES:
        print(f"SELFTEST FAILED: {len(FAILURES)} of {CHECKS} checks failed")
        for item in FAILURES:
            print(f"  - {item}")
        return 1
    print(f"SELFTEST PASSED: {CHECKS} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
