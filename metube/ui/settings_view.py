"""Full-screen settings panel."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..models import ALL_FORMATS, QUALITIES
from ..theme import (
    ACCENT,
    ACCENT_HOVER,
    BG,
    BORDER,
    CARD,
    FONT_BODY,
    FONT_BUTTON,
    FONT_SMALL,
    FONT_TITLE,
    MUTED,
    TEXT,
)

log = logging.getLogger("metube.ui.settings")


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color=BG)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        ctk.CTkButton(
            header,
            text="← Back",
            width=90,
            height=30,
            font=FONT_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            hover_color="#33333C",
            text_color=TEXT,
            command=self._back,
        ).pack(side="left")
        ctk.CTkLabel(
            header, text="Settings", font=FONT_TITLE, text_color=TEXT
        ).pack(side="left", padx=16)

        body = ctk.CTkScrollableFrame(self, fg_color=BG)
        body.grid(row=1, column=0, sticky="nsew", padx=14)
        body.grid_columnconfigure(0, weight=1)

        self._card = ctk.CTkFrame(
            body, fg_color=CARD, corner_radius=10, border_width=1, border_color=BORDER
        )
        self._card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._card.grid_columnconfigure(1, weight=1)

        self._row_index = 0

        # ---- download folder ----
        self._folder_var = tk.StringVar()
        ctk.CTkLabel(
            self._card, text="Download folder", font=FONT_BODY, text_color=TEXT
        ).grid(row=self._row_index, column=0, sticky="w", padx=16, pady=(16, 6))
        holder = ctk.CTkFrame(self._card, fg_color="transparent")
        holder.grid(row=self._row_index, column=1, sticky="ew", padx=(0, 16), pady=(16, 6))
        holder.grid_columnconfigure(0, weight=1)
        self._folder_entry = ctk.CTkEntry(
            holder,
            textvariable=self._folder_var,
            state="readonly",
            font=FONT_BODY,
            fg_color="#1E1E24",
            border_color=BORDER,
            text_color=MUTED,
            width=380,
        )
        self._folder_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            holder,
            text="Browse…",
            width=92,
            height=30,
            font=FONT_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            hover_color="#33333C",
            text_color=TEXT,
            command=self._browse_folder,
        ).grid(row=0, column=1, padx=(8, 0))
        self._row_index += 1

        # ---- default format ----
        self._format_var = tk.StringVar(value="MP3")
        ctk.CTkLabel(
            self._card, text="Default format", font=FONT_BODY, text_color=TEXT
        ).grid(row=self._row_index, column=0, sticky="w", padx=16, pady=6)
        self._format_menu = ctk.CTkOptionMenu(
            self._card,
            values=list(ALL_FORMATS),
            variable=self._format_var,
            width=180,
            font=FONT_BODY,
            fg_color=ACCENT,
            button_color=ACCENT_HOVER,
            command=self._on_format_change,
        )
        self._format_menu.grid(row=self._row_index, column=1, sticky="w", padx=(0, 16), pady=6)
        self._row_index += 1

        # ---- default quality ----
        self._quality_var = tk.StringVar(value="Best Available")
        ctk.CTkLabel(
            self._card, text="Default MP4 quality", font=FONT_BODY, text_color=TEXT
        ).grid(row=self._row_index, column=0, sticky="w", padx=16, pady=6)
        self._quality_menu = ctk.CTkOptionMenu(
            self._card,
            values=list(QUALITIES),
            variable=self._quality_var,
            width=180,
            font=FONT_BODY,
            fg_color=ACCENT,
            button_color=ACCENT_HOVER,
        )
        self._quality_menu.grid(row=self._row_index, column=1, sticky="w", padx=(0, 16), pady=6)
        self._row_index += 1

        # ---- delays ----
        self._delay_min_var = tk.StringVar(value="3")
        self._delay_max_var = tk.StringVar(value="5")
        ctk.CTkLabel(
            self._card,
            text="Delay between downloads (seconds)",
            font=FONT_BODY,
            text_color=TEXT,
        ).grid(row=self._row_index, column=0, sticky="w", padx=16, pady=6)
        delay_row = ctk.CTkFrame(self._card, fg_color="transparent")
        delay_row.grid(row=self._row_index, column=1, sticky="w", padx=(0, 16), pady=6)
        self._delay_min_entry = ctk.CTkEntry(
            delay_row,
            textvariable=self._delay_min_var,
            width=64,
            font=FONT_BODY,
            fg_color="#1E1E24",
            border_color=BORDER,
            text_color=TEXT,
        )
        self._delay_min_entry.pack(side="left")
        ctk.CTkLabel(delay_row, text="min  ·  max", font=FONT_SMALL, text_color=MUTED).pack(
            side="left", padx=8
        )
        self._delay_max_entry = ctk.CTkEntry(
            delay_row,
            textvariable=self._delay_max_var,
            width=64,
            font=FONT_BODY,
            fg_color="#1E1E24",
            border_color=BORDER,
            text_color=TEXT,
        )
        self._delay_max_entry.pack(side="left")
        self._row_index += 1

        # ---- toggles ----
        self._auto_update_var = tk.BooleanVar(value=True)
        self._notify_var = tk.BooleanVar(value=True)
        self._keep_awake_var = tk.BooleanVar(value=True)
        self._keep_awake_switch = None
        for label, var in (
            ("Auto-update yt-dlp on startup", self._auto_update_var),
            ("Finish notification", self._notify_var),
            ("Keep PC awake while downloading", self._keep_awake_var),
        ):
            ctk.CTkLabel(
                self._card, text=label, font=FONT_BODY, text_color=TEXT
            ).grid(row=self._row_index, column=0, sticky="w", padx=16, pady=6)
            switch = ctk.CTkSwitch(
                self._card,
                text="",
                variable=var,
                onvalue=True,
                offvalue=False,
                progress_color=ACCENT,
                button_color="#E0E0E6",
                button_hover_color="#FFFFFF",
            )
            switch.grid(row=self._row_index, column=1, sticky="w", padx=(0, 16), pady=6)
            self._row_index += 1

        action_row = ctk.CTkFrame(self._card, fg_color="transparent")
        action_row.grid(row=self._row_index, column=0, columnspan=2, sticky="ew", padx=16, pady=(14, 16))
        for text, command in (
            ("Check for yt-dlp update now", self._check_update),
            ("Re-download components", self._redownload),
            ("Open logs folder", self._open_logs),
            ("Reset settings", self._reset),
        ):
            ctk.CTkButton(
                action_row,
                text=text,
                height=32,
                font=FONT_BUTTON,
                fg_color="transparent",
                border_width=1,
                border_color=BORDER,
                hover_color="#33333C",
                text_color=TEXT,
                command=command,
            ).pack(side="left", padx=(0, 8))

        save_row = ctk.CTkFrame(body, fg_color="transparent")
        save_row.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        ctk.CTkButton(
            save_row,
            text="Save settings",
            width=160,
            height=38,
            font=FONT_BUTTON,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._save,
        ).pack(side="right")

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        settings = self.app.settings
        self._folder_var.set(settings.download_folder)
        self._format_var.set(settings.default_format)
        self._quality_var.set(settings.default_quality)
        low, high = settings.validated_delays()
        self._delay_min_var.set(str(settings.delay_min if settings.delay_min >= 2 else low))
        self._delay_max_var.set(str(settings.delay_max if settings.delay_max >= settings.delay_min else high))
        self._auto_update_var.set(bool(settings.get("auto_update_ytdlp", True)))
        self._notify_var.set(bool(settings.get("finish_notification", True)))
        self._keep_awake_var.set(bool(settings.get("keep_awake", True)))
        self._sync_quality_state()

    def _on_format_change(self, _value=None) -> None:
        self._sync_quality_state()

    def _sync_quality_state(self) -> None:
        if self._format_var.get() == "MP4":
            self._quality_menu.configure(
                state="normal",
                fg_color=ACCENT,
                button_color=ACCENT_HOVER,
                text_color="#FFFFFF",
            )
        else:
            self._quality_menu.configure(
                state="disabled",
                fg_color="#2E2E36",
                button_color="#2E2E36",
                text_color=MUTED,
            )

    # ------------------------------------------------------------------
    def _browse_folder(self) -> None:
        current = self._folder_var.get() or str(self.app.settings.download_folder)
        chosen = filedialog.askdirectory(
            parent=self, title="Choose download folder", initialdir=current
        )
        if chosen:
            self._folder_var.set(chosen)

    def _check_update(self) -> None:
        self.app.check_updates_now()

    def _redownload(self) -> None:
        self.app.redownload_components()

    def _open_logs(self) -> None:
        self.app.open_logs_folder()

    def _reset(self) -> None:
        self.app.reset_settings()

    def _save(self) -> None:
        folder = (self._folder_var.get() or "").strip()
        if not folder:
            messagebox.showwarning("MeTube", "Please choose a download folder.")
            return
        try:
            low = int(self._delay_min_var.get().strip())
            high = int(self._delay_max_var.get().strip())
        except ValueError:
            messagebox.showwarning("MeTube", "Delays must be whole numbers.")
            return
        if low < 2:
            messagebox.showwarning("MeTube", "Minimum delay must be at least 2 seconds.")
            return
        if high < low:
            messagebox.showwarning("MeTube", "Maximum delay must be >= minimum delay.")
            return

        values = {
            "download_folder": folder,
            "default_format": self._format_var.get(),
            "default_quality": self._quality_var.get(),
            "delay_min": low,
            "delay_max": high,
            "auto_update_ytdlp": bool(self._auto_update_var.get()),
            "finish_notification": bool(self._notify_var.get()),
            "keep_awake": bool(self._keep_awake_var.get()),
        }
        accepted = self.app.apply_settings(values)
        if accepted:
            self.app.show_toast("Settings saved")
        else:
            # The folder could not be created here (another PC's drive letter,
            # a removed USB stick, no permission). Say so - and show the folder
            # the app is really going to use - instead of silently failing on
            # every later download.
            actual = self.app.settings.download_folder
            self._folder_var.set(actual)
            messagebox.showwarning(
                "MeTube",
                f"This folder can't be used:\n{folder}\n\n"
                f"Downloads will be saved to:\n{actual}",
            )
            self.app.show_toast("Download folder changed to a usable folder")
        self.app.show_view("main")

    def _back(self) -> None:
        self.refresh()
        self.app.show_view("main")
