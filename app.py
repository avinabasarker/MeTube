"""MeTube entry point and main window.

Threading rules (Section 10): widgets are created and mutated only on the Tk
main thread.  Background workers push plain dicts onto ``self.events`` and the
``after(100)`` poller applies them.
"""

from __future__ import annotations

import ctypes
import logging
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from metube import (
    binaries,
    config,
    downloader,
    keepawake,
    logger,
    notify,
    settings as settings_module,
    single_instance,
    store,
    utils,
)
from metube.engine import QueueManager
from metube.metadata import MetadataFetcher
from metube.models import ALL_FORMATS, QUALITIES, STATUS_COMPLETED, QueueItem
from metube.theme import (
    ACCENT,
    ACCENT_HOVER,
    BG,
    BORDER,
    CARD,
    FAILURE,
    FONT_BODY,
    FONT_BUTTON,
    FONT_HEADING,
    FONT_ICON,
    FONT_SMALL,
    FONT_TITLE,
    MUTED,
    TEXT,
)
from metube.ui.card import QueueCard
from metube.ui.dialogs import FirstRunDialog, RestoreSessionDialog
from metube.ui.history_view import HistoryView
from metube.ui.settings_view import SettingsView
from metube.ui.widgets import PlaceholderTextbox, ThumbnailLoader, Toast

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

log = logging.getLogger("metube.app")

PLACEHOLDER = "Paste YouTube links — separate with commas or new lines"
EVENTS_PER_TICK = 40


class App(ctk.CTk):
    def __init__(self, skip_modals: bool = False, autostart: bool = True) -> None:
        super().__init__()
        self.skip_modals = skip_modals
        self.autostart = autostart
        self.withdraw()

        self.title("MeTube")
        self._set_window_icon()
        self.geometry("1000x680")
        self.minsize(820, 560)
        self.configure(fg_color=BG)

        self.settings = settings_module.load_settings()
        # A settings.json copied from another PC can point at a folder that does
        # not exist here (another drive letter, another user profile). Check it
        # before anything writes there, and stay self-contained when it is gone.
        self._folder_notice = ""
        if settings_module.settings_exist() and not self.settings.get("first_run", False):
            self._folder_notice = self._ensure_download_folder()
        self.events: "queue.Queue[dict]" = queue.Queue()
        self.queue_manager = QueueManager(self.events, self.get_settings)
        self.metadata = MetadataFetcher(self.events)
        self.thumb_loader = ThumbnailLoader(self.events, size=(96, 54))
        self.cards: dict[str, QueueCard] = {}
        self._thumb_images: dict[str, object] = {}
        self._history_thumbs: dict[str, object] = {}
        self._views: dict[str, ctk.CTkFrame] = {}
        self._current_view = "main"
        self.engine_ready = False
        self._closing = False
        self._updater_running = False

        if not skip_modals:
            self._maybe_first_run()

        self._build_ui()
        self._sync_main_dropdowns()
        if not skip_modals:
            self._maybe_restore()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.deiconify()
        # The window is mapped from here on, but CustomTkinter only records
        # that when its own update()/mainloop() run - and its mainloop()
        # title-bar pass withdraws the window first and skips showing it again
        # because withdraw() was called before the window ever existed (which
        # is how this window is built). Marking it mapped here keeps that pass
        # from hiding the UI, and makes later colour passes restore "normal".
        try:
            self._window_exists = True
        except Exception:  # noqa: BLE001 - the attribute is CTk-internal
            log.debug("could not mark the window as mapped", exc_info=True)
        # Belt and braces: an app that runs invisibly looks exactly like
        # "nothing happened" when the exe is double-clicked.
        self.after(150, self._ensure_window_shown)
        self.after(900, self._ensure_window_shown)
        self.after(120, self._startup_tasks)
        self.after(100, self._poll_events)

    # ==================================================================
    # construction helpers
    # ==================================================================
    def _set_window_icon(self) -> None:
        """Use the bundled icon so the taskbar matches the built exe."""
        try:
            icon = config.resource_path("assets/icon.ico")
            if icon.exists():
                self.iconbitmap(str(icon))
        except (tk.TclError, OSError):
            log.debug("could not set the window icon", exc_info=True)

    def _ensure_window_shown(self) -> None:
        """Guarantee the main window is really on screen.

        CustomTkinter's title-bar colour pass withdraws the window while it
        updates the DWM attribute; when it believes the window was never
        mapped it does not show it again, leaving the app running with an
        invisible window. Verify and re-show instead of trusting a single
        deiconify(), and leave a log line when it has to be repeated.
        """
        if self._closing:
            return
        try:
            state = self.state()
        except Exception:  # noqa: BLE001
            log.debug("window state unavailable", exc_info=True)
            return
        if state == "withdrawn":
            log.warning("main window was left withdrawn - showing it again")
            try:
                self.deiconify()
                self.lift()
            except Exception:  # noqa: BLE001
                log.debug("could not re-show the main window", exc_info=True)

    def get_settings(self):
        return self.settings

    def _ensure_download_folder(self) -> str:
        """Keep the remembered download folder usable across machines.

        Returns a message for the user when the folder had to be replaced, or
        an empty string when everything was already fine.
        """
        configured = self.settings.download_folder
        folder = config.resolve_download_folder(configured)
        if config.folder_is_usable(folder):
            if not configured:
                self.settings["download_folder"] = str(folder)
                settings_module.save_settings(self.settings)
            return ""

        fallback = config.portable_download_folder()
        log.warning(
            "remembered download folder %s is not usable here - using %s",
            folder,
            fallback,
        )
        self.settings["download_folder"] = str(fallback)
        settings_module.save_settings(self.settings)
        return (
            "Saved download folder is unavailable — downloads now go to "
            f"{fallback}"
        )

    def _build_ui(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        main = ctk.CTkFrame(self, fg_color=BG)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)
        self._views["main"] = main

        self._build_header(main)
        self._build_controls(main)
        self._build_queue(main)
        self._build_toolbar(main)
        self._build_bottom(main)

        self.settings_view = SettingsView(self, self)
        self.history_view = HistoryView(self, self)
        self._views["settings"] = self.settings_view
        self._views["history"] = self.history_view

        self.show_view("main")

        self.toast = Toast(self)

    def _build_header(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="MeTube", font=FONT_TITLE, text_color=TEXT).grid(
            row=0, column=0, sticky="w"
        )

        progress_block = ctk.CTkFrame(header, fg_color="transparent")
        progress_block.grid(row=0, column=1, sticky="ew", padx=24)
        progress_block.grid_columnconfigure(0, weight=1)
        self.progress_label = ctk.CTkLabel(
            progress_block,
            text="0 of 0 complete",
            font=FONT_SMALL,
            text_color=MUTED,
            anchor="w",
        )
        self.progress_label.grid(row=0, column=0, sticky="ew")
        self.overall_bar = ctk.CTkProgressBar(
            progress_block, height=5, corner_radius=3, progress_color=ACCENT,
            fg_color=BORDER,
        )
        self.overall_bar.set(0)
        self.overall_bar.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        self.history_button = ctk.CTkButton(
            header,
            text="History",
            width=90,
            height=32,
            font=FONT_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            hover_color="#33333C",
            text_color=TEXT,
            command=lambda: self.show_view("history"),
        )
        self.history_button.grid(row=0, column=2, padx=(0, 8))

        self.settings_button = ctk.CTkButton(
            header,
            text="⚙",
            width=42,
            height=32,
            font=FONT_ICON,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            hover_color="#33333C",
            text_color=TEXT,
            command=lambda: self.show_view("settings"),
        )
        self.settings_button.grid(row=0, column=3)

    def _build_controls(self, parent) -> None:
        controls = ctk.CTkFrame(parent, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 6))

        ctk.CTkLabel(controls, text="Format", font=FONT_BODY, text_color=MUTED).pack(
            side="left"
        )
        self.format_var = tk.StringVar(value=self.settings.default_format)
        self.format_menu = ctk.CTkOptionMenu(
            controls,
            values=list(ALL_FORMATS),
            variable=self.format_var,
            width=110,
            font=FONT_BODY,
            fg_color=ACCENT,
            button_color=ACCENT_HOVER,
            command=self.on_format_change,
        )
        self.format_menu.pack(side="left", padx=(8, 20))

        ctk.CTkLabel(controls, text="Quality", font=FONT_BODY, text_color=MUTED).pack(
            side="left"
        )
        self.quality_var = tk.StringVar(value=self.settings.default_quality)
        self.quality_menu = ctk.CTkOptionMenu(
            controls,
            values=list(QUALITIES),
            variable=self.quality_var,
            width=170,
            font=FONT_BODY,
            fg_color=ACCENT,
            button_color=ACCENT_HOVER,
        )
        self.quality_menu.pack(side="left", padx=(8, 0))

    def _build_queue(self, parent) -> None:
        self.queue_frame = ctk.CTkScrollableFrame(parent, fg_color=BG)
        self.queue_frame.grid(row=2, column=0, sticky="nsew", padx=14, pady=(4, 6))
        self.queue_frame.grid_columnconfigure(0, weight=1)

        self.empty_label = ctk.CTkLabel(
            self.queue_frame,
            text="Paste YouTube links below to get started.",
            font=FONT_BODY,
            text_color=MUTED,
        )
        self.empty_label.grid(row=0, column=0, pady=40)

    def _build_toolbar(self, parent) -> None:
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 6))
        toolbar.grid_columnconfigure(0, weight=1)

        self.queue_count_label = ctk.CTkLabel(
            toolbar, text="0 items in queue", font=FONT_SMALL, text_color=MUTED, anchor="w"
        )
        self.queue_count_label.grid(row=0, column=0, sticky="w")

        self.cancel_all_button = ctk.CTkButton(
            toolbar,
            text="Cancel All",
            width=110,
            height=30,
            font=FONT_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=FAILURE,
            hover_color="#3A2A2C",
            text_color="#F08A80",
            command=self.on_cancel_all,
        )
        self.cancel_all_button.grid(row=0, column=1)

        # Where the next download goes, on screen.  The folder is remembered
        # across launches, so without this line the only way to know it is to
        # open Settings; a click opens the folder itself.
        self.folder_label = ctk.CTkLabel(
            toolbar,
            text="",
            font=FONT_SMALL,
            text_color=MUTED,
            anchor="w",
            justify="left",
            cursor="hand2",
        )
        self.folder_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.folder_label.bind("<Button-1>", lambda _event: self.open_download_folder())
        self._sync_folder_label()

    def _build_bottom(self, parent) -> None:
        bottom = ctk.CTkFrame(parent, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 16))
        bottom.grid_columnconfigure(0, weight=1)

        self.input_box = PlaceholderTextbox(bottom, placeholder=PLACEHOLDER, height=70)
        self.input_box.grid(row=0, column=0, columnspan=4, sticky="ew")
        self.input_box.bind("<Control-Return>", self._on_ctrl_return, add="+")

        self.add_button = ctk.CTkButton(
            bottom,
            text="Add to Queue",
            width=150,
            height=36,
            font=FONT_BUTTON,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self.add_links,
        )
        self.add_button.grid(row=1, column=3, sticky="e", pady=(10, 0))

        self.clear_button = ctk.CTkButton(
            bottom,
            text="Clear Completed",
            width=140,
            height=36,
            font=FONT_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            hover_color="#33333C",
            text_color=TEXT,
            command=self.on_clear_completed,
        )
        self.clear_button.grid(row=1, column=0, sticky="w", pady=(10, 0))

        self.pause_button = ctk.CTkButton(
            bottom,
            text="Pause All",
            width=120,
            height=36,
            font=FONT_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            hover_color="#33333C",
            text_color=TEXT,
            command=self.on_toggle_pause,
        )
        self.pause_button.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        self.engine_hint = ctk.CTkLabel(
            bottom, text="", font=FONT_SMALL, text_color=MUTED, anchor="e"
        )
        self.engine_hint.grid(row=1, column=2, sticky="e", padx=(0, 12), pady=(10, 0))

    # ==================================================================
    # startup
    # ==================================================================
    def _maybe_first_run(self) -> None:
        if settings_module.settings_exist() and not self.settings.get("first_run", False):
            log.info("settings found at %s — skipping first-run dialog", config.settings_path())
            return
        # A portable copy must open even when the profile's Downloads folder is
        # unusable (locked-down or redirected machines), so the picker starts
        # from a folder that really works here.
        suggested = config.default_download_folder()
        if not config.folder_is_usable(suggested):
            suggested = config.portable_download_folder()
            log.warning("default download folder unusable - suggesting %s", suggested)
        log.info("first run detected — showing folder picker")
        dialog = FirstRunDialog(self, suggested)
        self.wait_window(dialog)
        folder = config.resolve_download_folder(dialog.result or suggested)
        if not config.folder_is_usable(folder):
            log.warning("chosen folder %s is unusable; using %s", folder, suggested)
            folder = suggested
        self.settings["download_folder"] = str(folder)
        self.settings["first_run"] = False
        settings_module.save_settings(self.settings)
        log.info("first run complete; download folder = %s", folder)

    def _maybe_restore(self) -> None:
        items = store.load_queue()
        if not items:
            return
        pending = [i for i in items if not _is_done(i)]
        if not pending:
            for item in items:
                self.queue_manager.add_item(item)
            return
        dialog = RestoreSessionDialog(self, len(pending))
        self.wait_window(dialog)
        if dialog.result:
            for item in items:
                if not _is_done(item):
                    item.status = "Queued"
                    item.failure_reason = ""
                self.queue_manager.add_item(item)
            log.info("restored %s queue items", len(items))
        else:
            store.clear_queue()
            log.info("queue snapshot cleared by user")

    def _startup_tasks(self) -> None:
        if not self.autostart:
            return
        self.queue_manager.start()
        self.metadata.start()
        keepawake.set_enabled(bool(self.settings.get("keep_awake", True)))
        if self._folder_notice:
            log.warning("%s", self._folder_notice)
            self.show_toast(self._folder_notice, duration=6000)
            self._folder_notice = ""

        if binaries.is_complete():
            self._set_engine_ready(True)
            threading.Thread(
                target=self._validate_engine_async, name="EngineValidate", daemon=True
            ).start()
        else:
            log.warning("engine binaries incomplete at startup — bootstrapping")
            self._start_bootstrap()

        if self.settings.get("auto_update_ytdlp", True):
            self.start_updater(notify_result=False)

    def _validate_engine_async(self) -> None:
        results = binaries.validate_all()
        failed = [name for name, (ok, _) in results.items() if not ok]
        self.events.put({"type": "engine_validated", "failed": failed, "results": {
            k: v[1] for k, v in results.items()
        }})

    def _start_bootstrap(self) -> None:
        self._set_engine_ready(False, "Preparing engine…")
        binaries.bootstrap(
            on_progress=lambda text: self.events.put(
                {"type": "bootstrap_status", "text": text}
            ),
            on_done=lambda ok, message: self.events.put(
                {"type": "bootstrap_done", "ok": ok, "message": message}
            ),
        )

    def _set_engine_ready(self, ready: bool, hint: str = "") -> None:
        self.engine_ready = ready
        try:
            self.add_button.configure(
                state="normal" if ready else "disabled",
                text="Add to Queue" if ready else "Preparing engine…",
                fg_color=ACCENT if ready else "#3A3A42",
            )
            self.engine_hint.configure(text=hint)
        except tk.TclError:
            pass

    def start_updater(self, notify_result: bool = False) -> None:
        if self._updater_running and not notify_result:
            return

        def worker() -> None:
            self._updater_running = True
            output = "yt-dlp.exe not found"
            ytdlp = binaries.resolve_binary(binaries.YTDLP_NAME)
            try:
                if ytdlp is not None:
                    proc = subprocess.run(
                        [str(ytdlp), "-U"],
                        capture_output=True,
                        text=True,
                        timeout=240,
                        creationflags=utils.NO_WINDOW,
                    )
                    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
            except Exception as exc:  # noqa: BLE001
                output = f"yt-dlp update failed: {exc}"
            finally:
                self._updater_running = False
            self.events.put(
                {"type": "updater_done", "output": output[-600:], "notify": notify_result}
            )

        threading.Thread(target=worker, name="UpdaterThread", daemon=True).start()

    # ==================================================================
    # views
    # ==================================================================
    def show_view(self, name: str) -> None:
        for key, frame in self._views.items():
            if key == name:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_remove()
        self._current_view = name
        if name == "history":
            self.history_view.refresh()
        elif name == "settings":
            self.settings_view.refresh()
        self._update_counts_ui(self.queue_manager.counts())

    def show_toast(self, text: str, duration: int = 3200) -> None:
        try:
            self.toast.show(text, duration)
        except Exception:  # noqa: BLE001
            log.debug("toast failed", exc_info=True)

    # ==================================================================
    # dropdown sync (single canonical method + alias -> regression B10)
    # ==================================================================
    def _sync_main_dropdowns(self) -> None:
        """Apply settings to the main Format/Quality dropdowns and folder line."""
        self.format_var.set(self.settings.default_format)
        self.quality_var.set(self.settings.default_quality)
        self._sync_quality_state()
        self._sync_folder_label()

    def download_folder_path(self) -> Path:
        """The folder the next download will use (absolute, never blank)."""
        return config.resolve_download_folder(self.settings.download_folder)

    def _sync_folder_label(self) -> None:
        """Show the remembered download folder under the queue counter."""
        folder = str(self.download_folder_path())
        shown = folder if len(folder) <= 72 else "…" + folder[-71:]
        try:
            self.folder_label.configure(text=f"Saving to  {shown}")
        except (tk.TclError, AttributeError):
            log.debug("could not update the folder label", exc_info=True)

    def open_download_folder(self) -> None:
        """Open the download folder in Explorer (click on the folder line)."""
        folder = self.download_folder_path()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            utils.open_file(folder)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                "MeTube", f"Could not open the download folder:\n{exc}"
            )

    def sync_main_dropdowns(self) -> None:
        """Thin alias so every historical call site resolves."""
        self._sync_main_dropdowns()

    def on_format_change(self, _value=None) -> None:
        self._sync_quality_state()

    def _sync_quality_state(self) -> None:
        """Quality is meaningless for audio: disabled for MP3/M4A (B9)."""
        if self.format_var.get() == "MP4":
            self.quality_menu.configure(
                state="normal",
                fg_color=ACCENT,
                button_color=ACCENT_HOVER,
                text_color="#FFFFFF",
            )
        else:
            self.quality_menu.configure(
                state="disabled",
                fg_color="#2E2E36",
                button_color="#2E2E36",
                text_color=MUTED,
            )
        self.settings_view._sync_quality_state()

    # ==================================================================
    # adding links
    # ==================================================================
    def _on_ctrl_return(self, _event=None):
        self.add_links()
        return "break"

    def add_links(self) -> None:
        if not self.engine_ready:
            self.show_toast("Engine is still preparing…")
            return
        raw = self.input_box.get_input()
        # Empty, whitespace, or the hint text itself: do nothing at all.
        # The hint is normally filtered by PlaceholderTextbox.get_input(), but
        # checking the literal too means placeholder-only content can never be
        # submitted even if the internal flag were ever out of sync.
        if not raw.strip() or raw.strip() == PLACEHOLDER:
            return
        links = utils.split_links(raw)
        if not links:
            return
        self.input_box.clear_input()

        existing = {i.video_id for i in self.queue_manager.snapshot() if i.video_id}
        added = 0
        playlists = 0
        for link in links:
            if utils.is_playlist_url(link):
                self._expand_playlist(link)
                playlists += 1
                continue
            video_id = utils.extract_video_id(link)
            if video_id and video_id in existing:
                continue  # duplicate: silently skipped
            item = QueueItem(
                url=utils.canonical_url(video_id) if video_id else link,
                fmt=self.format_var.get(),
                quality=self.quality_var.get(),
                video_id=video_id,
            )
            self.queue_manager.add_item(item)
            if video_id:
                existing.add(video_id)
            self.metadata.submit(item.id, item.url)
            added += 1

        if added:
            self.show_toast(f"Added {added} item{'s' if added != 1 else ''} to the queue")
        elif not playlists:
            self.show_toast("Those links are already in the queue")

    def _expand_playlist(self, url: str) -> None:
        def worker() -> None:
            try:
                ids = downloader.expand_playlist(url)
                self.events.put({"type": "playlist_expanded", "url": url, "ids": ids})
            except Exception as exc:  # noqa: BLE001
                self.events.put({"type": "playlist_failed", "url": url, "error": str(exc)})

        threading.Thread(target=worker, name="PlaylistExpand", daemon=True).start()

    # ==================================================================
    # card actions
    # ==================================================================
    def _item(self, item_id: str):
        return self.queue_manager.find(item_id)

    def on_pause(self) -> None:
        self.queue_manager.pause_all()
        self._update_pause_button()

    def on_resume(self) -> None:
        self.queue_manager.resume_all()
        self._update_pause_button()

    def on_toggle_pause(self) -> None:
        if self.queue_manager.is_paused():
            self.on_resume()
        else:
            self.on_pause()

    def on_cancel(self, item_id: str) -> None:
        self.queue_manager.cancel_item(item_id)

    def on_dismiss(self, item_id: str) -> None:
        self.queue_manager.remove_item(item_id)

    def on_retry(self, item_id: str) -> None:
        self.queue_manager.retry_item(item_id)

    def on_cancel_all(self) -> None:
        self.queue_manager.cancel_all()
        self._update_pause_button()

    def on_clear_completed(self) -> None:
        self.queue_manager.clear_completed()

    def on_show_in_folder(self, item) -> None:
        self._reveal(item.file_path)

    def on_open_file(self, item) -> None:
        if not item.file_path or not Path(item.file_path).exists():
            messagebox.showinfo(
                "MeTube", "File location unknown — check your download folder"
            )
            return
        try:
            utils.open_file(item.file_path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("MeTube", f"Could not open the file:\n{exc}")

    def _reveal(self, file_path: str) -> None:
        if not file_path or not Path(file_path).exists():
            messagebox.showinfo(
                "MeTube", "File location unknown — check your download folder"
            )
            return
        try:
            utils.open_in_explorer(file_path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("MeTube", f"Could not open the folder:\n{exc}")

    def on_show_history_item(self, file_path: str) -> None:  # pragma: no cover
        self._reveal(file_path)

    def load_history_thumb(self, path: str):
        cached = self._history_thumbs.get(path)
        if cached is not None:
            return cached
        try:
            from PIL import Image, ImageOps

            with Image.open(path) as raw:
                image = ImageOps.fit(raw.convert("RGB"), (64, 36))
            ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(64, 36))
        except Exception:  # noqa: BLE001
            return None
        self._history_thumbs[path] = ctk_image
        return ctk_image

    # ==================================================================
    # settings actions
    # ==================================================================
    def apply_settings(self, values: dict) -> bool:
        """Persist settings and report whether the chosen folder was accepted.

        Settings are saved immediately (they must survive a crash and the next
        launch).  When the chosen folder cannot be created or written here, the
        download folder is replaced with the app-folder one instead of being
        stored broken - the caller tells the user, and every later download has
        somewhere real to go.
        """
        for key, value in values.items():
            self.settings[key] = value
        # Store the resolved, absolute folder: a relative value would otherwise
        # be handed to yt-dlp and land somewhere else (see config).
        folder = config.resolve_download_folder(self.settings.download_folder)
        accepted = config.folder_is_usable(folder)
        if accepted:
            self.settings["download_folder"] = str(folder)
        else:
            fallback = config.portable_download_folder()
            log.warning(
                "chosen download folder %s is not usable here - using %s", folder, fallback
            )
            self.settings["download_folder"] = str(fallback)
        self.settings["first_run"] = False
        settings_module.save_settings(self.settings)
        keepawake.set_enabled(bool(self.settings.get("keep_awake", True)))
        self._sync_main_dropdowns()
        log.info("settings saved; download folder = %s", self.settings.download_folder)
        return accepted

    def reset_settings(self) -> None:
        if not messagebox.askyesno(
            "MeTube",
            "Reset all settings to defaults?\n\nThe folder picker will appear on the "
            "next launch.",
        ):
            return
        settings_module.reset_for_first_run()
        self.settings = settings_module.load_settings()
        self.settings["first_run"] = True
        self._sync_main_dropdowns()
        self.settings_view.refresh()
        self.show_view("main")
        self.show_toast("Settings reset — the picker appears on next launch")

    def open_logs_folder(self) -> None:
        folder = config.logs_dir()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            utils.open_file(folder)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("MeTube", f"Could not open logs folder:\n{exc}")

    def check_updates_now(self) -> None:
        self.show_toast("Checking for yt-dlp updates…")
        self.start_updater(notify_result=True)

    def redownload_components(self) -> None:
        if not messagebox.askyesno(
            "MeTube", "Re-download yt-dlp and ffmpeg into data\\bin?"
        ):
            return
        self._start_bootstrap()

    # ==================================================================
    # event pump
    # ==================================================================
    def _poll_events(self) -> None:
        if self._closing:
            return
        if single_instance.poll_signal():
            self._on_second_instance()
        processed = 0
        while processed < EVENTS_PER_TICK:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            try:
                self._handle_event(event)
            except Exception:  # noqa: BLE001 - one bad event must not kill the UI
                log.exception("event handler failed: %s", event.get("type"))
            processed += 1
        self.after(100, self._poll_events)

    def _handle_event(self, event: dict) -> None:
        handler = {
            "item_added": self._on_item_added,
            "item_updated": self._on_item_updated,
            "item_metadata": self._on_item_metadata,
            "item_removed": self._on_item_removed,
            "queue_changed": lambda e: self._update_counts_ui(e["counts"]),
            "queue_finished": self._on_queue_finished,
            "engine_idle": lambda e: self._update_pause_button(),
            "thumb_ready": self._on_thumb_ready,
            "playlist_expanded": self._on_playlist_expanded,
            "playlist_failed": lambda e: self.show_toast(
                f"Could not read playlist: {e['error'][:80]}"
            ),
            "bootstrap_status": lambda e: self._set_engine_ready(False, e["text"]),
            "bootstrap_done": self._on_bootstrap_done,
            "engine_validated": self._on_engine_validated,
            "updater_done": self._on_updater_done,
        }.get(event.get("type"))
        if handler is not None:
            handler(event)

    def _on_item_added(self, event: dict) -> None:
        item = QueueItem.from_dict(event["item"])
        self._ensure_card(item)
        self._update_empty_state()
        self._update_counts_ui(self.queue_manager.counts())

    def _on_item_updated(self, event: dict) -> None:
        fields = dict(event["fields"])
        item_id = fields.pop("id")
        item = self.queue_manager.find(item_id)
        if item is None:
            return
        for key, value in fields.items():
            setattr(item, key, value)
        card = self.cards.get(item_id)
        if card is not None:
            card.item = item
            card.refresh()
        self._update_counts_ui(self.queue_manager.counts())

    def _on_item_metadata(self, event: dict) -> None:
        fields = dict(event["fields"])
        item_id = fields.pop("id")
        item = self.queue_manager.find(item_id)
        if item is None:
            return
        for key, value in fields.items():
            setattr(item, key, value)
        card = self.cards.get(item_id)
        if card is None:
            return
        card.item = item
        card.refresh()
        if item.thumbnail:
            self.request_thumbnail(item, card)

    def _on_item_removed(self, event: dict) -> None:
        card = self.cards.pop(event["id"], None)
        if card is not None:
            card.destroy()
        self._update_empty_state()
        self._update_counts_ui(self.queue_manager.counts())

    def _on_queue_finished(self, event: dict) -> None:
        completed = int(event.get("completed", 0))
        failed = int(event.get("failed", 0))
        notify.queue_finished(
            completed, failed, enabled=bool(self.settings.get("finish_notification", True))
        )
        self.show_toast(f"Queue finished: {completed} completed, {failed} failed.", 5000)
        self._update_pause_button()

    def _on_bootstrap_done(self, event: dict) -> None:
        if event.get("ok"):
            self._set_engine_ready(True)
            self.show_toast("Engine ready")
            log.info("engine bootstrap succeeded")
            return
        self._set_engine_ready(False, "Engine unavailable")
        log.error("engine bootstrap failed: %s", event.get("message"))
        messagebox.showerror(
            "MeTube — engine missing",
            "MeTube could not download its engine files.\n\n"
            f"Reason: {event.get('message') or 'unknown'}\n\n"
            f"{binaries.MANUAL_INSTRUCTIONS}",
        )

    def _on_engine_validated(self, event: dict) -> None:
        failed = event.get("failed") or []
        if failed:
            log.error("engine validation failed for %s — bootstrapping", failed)
            self.show_toast("Engine files look damaged — re-downloading")
            self._start_bootstrap()
        else:
            log.info("engine validation passed: %s", event.get("results"))

    def _on_updater_done(self, event: dict) -> None:
        output = (event.get("output") or "").strip()
        log.info("yt-dlp updater finished: %s", output.replace("\n", " | ")[:400])
        if event.get("notify"):
            messagebox.showinfo("MeTube — yt-dlp update", output or "No output.")

    def _on_playlist_expanded(self, event: dict) -> None:
        ids = event.get("ids") or []
        existing = {i.video_id for i in self.queue_manager.snapshot() if i.video_id}
        added = 0
        for video_id in ids:
            if video_id in existing:
                continue
            item = QueueItem(
                url=utils.canonical_url(video_id),
                fmt=self.format_var.get(),
                quality=self.quality_var.get(),
                video_id=video_id,
            )
            self.queue_manager.add_item(item)
            existing.add(video_id)
            self.metadata.submit(item.id, item.url)
            added += 1
        self.show_toast(f"Added {added} videos from playlist")

    def _on_thumb_ready(self, event: dict) -> None:
        image = event.get("image")
        if image is None:
            return
        try:
            ctk_image = ctk.CTkImage(
                light_image=image, dark_image=image, size=image.size
            )
        except Exception:  # noqa: BLE001
            return
        self._thumb_images[event.get("path") or event["id"]] = ctk_image
        card = self.cards.get(event["id"])
        if card is not None:
            card.set_thumbnail(ctk_image)

    def _on_second_instance(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self.after(400, lambda: self.attributes("-topmost", False))
        except tk.TclError:
            pass

    # ==================================================================
    # cards / counts
    # ==================================================================
    def _ensure_card(self, item: QueueItem) -> QueueCard:
        card = self.cards.get(item.id)
        if card is not None:
            return card
        card = QueueCard(self.queue_frame, item, self)
        card.grid(row=len(self.cards) + 1, column=0, sticky="ew", pady=4, padx=2)
        self.cards[item.id] = card
        if item.thumbnail:
            self.request_thumbnail(item, card)
        return card

    def request_thumbnail(self, item: QueueItem, card: QueueCard) -> None:
        cached = self._thumb_images.get(item.thumbnail)
        if cached is not None:
            card.set_thumbnail(cached)
            return
        self.thumb_loader.request(item.id, item.thumbnail)

    def _update_empty_state(self) -> None:
        has_cards = bool(self.cards)
        try:
            if has_cards:
                self.empty_label.grid_remove()
            else:
                self.empty_label.grid(row=0, column=0, pady=40)
        except tk.TclError:
            pass

    def _update_counts_ui(self, counts: dict) -> None:
        total = counts.get("total", 0)
        completed = counts.get("completed", 0)
        try:
            self.progress_label.configure(text=f"{completed} of {total} complete")
            self.queue_count_label.configure(
                text=f"{total} item{'s' if total != 1 else ''} in queue"
            )
            self.overall_bar.set((completed / total) if total else 0.0)
        except tk.TclError:
            pass

    def _update_pause_button(self) -> None:
        paused = self.queue_manager.is_paused()
        try:
            self.pause_button.configure(text="Resume All" if paused else "Pause All")
        except tk.TclError:
            pass

    # ==================================================================
    # shutdown
    # ==================================================================
    def _on_close(self) -> None:
        if self._closing:
            return
        counts = self.queue_manager.counts()
        busy = counts.get("active", 0) > 0 or counts.get("pending", 0) > 0
        if busy:
            if not messagebox.askyesno(
                "MeTube",
                "Downloads are still running. Quit anyway?\n\n"
                "The queue will be saved and can be restored next launch.",
            ):
                return
        self._closing = True
        log.info("shutting down")
        try:
            self.queue_manager.shutdown()
        except Exception:  # noqa: BLE001
            log.exception("queue shutdown failed")
        try:
            store.save_queue(self.queue_manager.snapshot())
        except Exception:  # noqa: BLE001
            log.exception("queue snapshot failed")
        try:
            self.metadata.stop()
        except Exception:  # noqa: BLE001
            pass
        keepawake.release()
        self.destroy()

    # ------------------------------------------------------------------
    def report_callback_exception(self, exc_type, exc_value, exc_tb) -> None:
        text = logger.log_crash("tk callback", exc_value)
        log.error("tk callback error:\n%s", text)


def _is_done(item: QueueItem) -> bool:
    return item.status == STATUS_COMPLETED or item.status.startswith("Failed") or item.status == "Cancelled"


# ======================================================================
# entry point
# ======================================================================
def _set_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    _set_dpi_awareness()
    logger.setup_logging()
    logger.install_excepthooks()

    if not single_instance.acquire():
        log.info("another instance is already running — signalling it")
        single_instance.signal_existing_instance()
        return 0

    app = App()
    app.mainloop()
    log.info("MeTube exited cleanly")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - last line of defence (B11)
        body = logger.log_crash("__main__", exc)
        logger._message_box(
            "MeTube could not start",
            "MeTube hit an unexpected error and had to stop.\n\n"
            f"Details were written to:\n{config.crash_log_path()}\n\n"
            + body.strip().splitlines()[-1][:500],
        )
        raise SystemExit(1)
