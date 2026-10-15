"""Modal dialogs.

Regression B2: calling ``grab_set`` before a Toplevel is mapped raises on
Windows and killed first launch.  Every dialog therefore defers the grab with
``after(150, ...)`` and wraps it in try/except TclError.
"""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from .. import config
from ..theme import (
    ACCENT,
    ACCENT_HOVER,
    BG,
    BORDER,
    CARD,
    FONT_BODY,
    FONT_BUTTON,
    FONT_HEADING,
    FONT_SMALL,
    MUTED,
    TEXT,
)

log = logging.getLogger("metube.ui.dialogs")


class BaseDialog(ctk.CTkToplevel):
    def __init__(self, master, title: str = "MeTube", width: int = 520, height: int = 220):
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=BG)
        self.resizable(False, False)
        self.result = None
        self._closed = False
        try:
            self.transient(master)
        except Exception:  # noqa: BLE001
            pass
        self.geometry(f"{width}x{height}")
        self.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self.after(60, self._center)
        # Deferred grab: the window is not mapped yet at construction time.
        self.after(150, self._safe_grab)

    # ------------------------------------------------------------------
    def _center(self) -> None:
        try:
            self.update_idletasks()
            master = self.master
            if master is not None and master.winfo_viewable():
                x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
                y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
            else:
                x = (self.winfo_screenwidth() - self.winfo_width()) // 2
                y = (self.winfo_screenheight() - self.winfo_height()) // 3
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:  # noqa: BLE001
            pass

    def _safe_grab(self) -> None:
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except tk.TclError:
            log.debug("grab_set deferred (window not mapped yet)")

    def _release_grab(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass

    def _on_close_request(self) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._release_grab()
        try:
            self.destroy()
        except tk.TclError:
            pass


class FirstRunDialog(BaseDialog):
    """'Choose where your downloads will be saved'."""

    def __init__(self, master, default_folder: Path):
        super().__init__(master, "MeTube — first run", 560, 240)
        self._folder = str(default_folder)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            body,
            text="Welcome to MeTube",
            font=FONT_HEADING,
            text_color=TEXT,
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            body,
            text="Choose where your downloads will be saved",
            font=FONT_BODY,
            text_color=MUTED,
            anchor="w",
        ).pack(fill="x", pady=(4, 14))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        self._entry = ctk.CTkEntry(
            row,
            font=FONT_BODY,
            fg_color=CARD,
            border_color=BORDER,
            text_color=TEXT,
        )
        self._entry.insert(0, self._folder)
        self._entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row,
            text="Browse…",
            width=92,
            height=30,
            font=FONT_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            hover_color="#33333C",
            text_color=TEXT,
            command=self._browse,
        ).pack(side="left", padx=(8, 0))

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x", pady=(22, 0))
        ctk.CTkButton(
            buttons,
            text="Save and continue",
            width=170,
            height=34,
            font=FONT_BUTTON,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._confirm,
        ).pack(side="right")
        ctk.CTkButton(
            buttons,
            text="Use default",
            width=120,
            height=34,
            font=FONT_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            hover_color="#33333C",
            text_color=TEXT,
            command=self._use_default,
        ).pack(side="right", padx=(0, 8))

    # ------------------------------------------------------------------
    def _browse(self) -> None:
        chosen = filedialog.askdirectory(
            parent=self, title="Choose download folder", initialdir=self._folder
        )
        if chosen:
            self._folder = chosen
            self._entry.delete(0, "end")
            self._entry.insert(0, chosen)

    def _use_default(self) -> None:
        self.result = str(config.default_download_folder())
        self.close()

    def _confirm(self) -> None:
        value = (self._entry.get() or "").strip()
        self.result = value or str(config.default_download_folder())
        self.close()


class RestoreSessionDialog(BaseDialog):
    def __init__(self, master, pending: int):
        super().__init__(master, "MeTube — restore session", 520, 200)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            body,
            text="Restore previous session?",
            font=FONT_HEADING,
            text_color=TEXT,
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            body,
            text=(
                f"Restore {pending} item{'s' if pending != 1 else ''} from your "
                "previous session?\nUnfinished items will go back to the queue."
            ),
            font=FONT_BODY,
            text_color=MUTED,
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(6, 18))
        ctk.CTkLabel(
            body,
            text="Choose No to clear the saved queue.",
            font=FONT_SMALL,
            text_color=MUTED,
            anchor="w",
        ).pack(fill="x")

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x", pady=(16, 0))
        ctk.CTkButton(
            buttons,
            text="Yes, restore",
            width=140,
            height=34,
            font=FONT_BUTTON,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=lambda: self._answer(True),
        ).pack(side="right")
        ctk.CTkButton(
            buttons,
            text="No, clear",
            width=110,
            height=34,
            font=FONT_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            hover_color="#33333C",
            text_color=TEXT,
            command=lambda: self._answer(False),
        ).pack(side="right", padx=(0, 8))

    def _answer(self, value: bool) -> None:
        self.result = value
        self.close()
