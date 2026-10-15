"""History panel: date, title, format, status, reveal-in-folder."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from .. import store
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
    FONT_TITLE,
    FAILURE,
    MUTED,
    SUCCESS,
    TEXT,
)
from ..utils import open_in_explorer


class HistoryView(ctk.CTkFrame):
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
            command=lambda: self.app.show_view("main"),
        ).pack(side="left")
        ctk.CTkLabel(
            header, text="History", font=FONT_TITLE, text_color=TEXT
        ).pack(side="left", padx=16)
        ctk.CTkButton(
            header,
            text="Clear History",
            width=130,
            height=30,
            font=FONT_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=FAILURE,
            hover_color="#3A2A2C",
            text_color="#F08A80",
            command=self._clear,
        ).pack(side="right")

        self._list = ctk.CTkScrollableFrame(self, fg_color=BG)
        self._list.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self._list.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        for child in self._list.winfo_children():
            child.destroy()
        rows = list(reversed(store.load_history()))
        if not rows:
            ctk.CTkLabel(
                self._list,
                text="No downloads yet.",
                font=FONT_BODY,
                text_color=MUTED,
            ).grid(row=0, column=0, pady=30)
            return
        for index, row in enumerate(rows):
            self._make_row(index, row)

    def _make_row(self, index: int, row: dict) -> None:
        card = ctk.CTkFrame(
            self._list,
            fg_color=CARD,
            corner_radius=8,
            border_width=1,
            border_color=BORDER,
        )
        card.grid(row=index, column=0, sticky="ew", pady=4, padx=2)
        card.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            card,
            text=row.get("timestamp", ""),
            font=FONT_SMALL,
            text_color=MUTED,
            width=140,
            anchor="w",
        ).grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=10, sticky="w")

        thumb_path = row.get("thumbnail") or ""
        if thumb_path and Path(thumb_path).is_file():
            image = self.app.load_history_thumb(thumb_path)
            if image is not None:
                ctk.CTkLabel(card, text="", image=image).grid(
                    row=0, column=1, rowspan=2, padx=(0, 10), pady=8
                )
            else:
                ctk.CTkLabel(card, text="", width=64).grid(row=0, column=1, rowspan=2)
        else:
            ctk.CTkLabel(card, text="", width=64).grid(row=0, column=1, rowspan=2)

        title = row.get("title") or row.get("url") or "(untitled)"
        ctk.CTkLabel(
            card,
            text=title,
            font=FONT_BODY,
            text_color=TEXT,
            anchor="w",
            justify="left",
            wraplength=520,
        ).grid(row=0, column=2, sticky="w", pady=(10, 0))

        status = row.get("status", "")
        colour = SUCCESS if status.startswith("Completed") else (
            FAILURE if status.startswith("Failed") else MUTED
        )
        detail = f"{row.get('fmt', '')}{(' · ' + row.get('quality')) if row.get('fmt') == 'MP4' else ''} — {status}"
        if row.get("failure_reason") and not status.endswith(row["failure_reason"]):
            detail += f" ({row['failure_reason']})"
        ctk.CTkLabel(
            card, text=detail, font=FONT_SMALL, text_color=colour, anchor="w"
        ).grid(row=1, column=2, sticky="w", pady=(0, 10))

        file_path = row.get("file_path") or ""
        ctk.CTkButton(
            card,
            text="Show in folder",
            width=120,
            height=26,
            font=FONT_BUTTON,
            fg_color=ACCENT if file_path else "transparent",
            hover_color=ACCENT_HOVER if file_path else "#33333C",
            border_width=0 if file_path else 1,
            border_color=BORDER,
            text_color="#FFFFFF" if file_path else MUTED,
            command=lambda p=file_path: self._reveal(p),
        ).grid(row=0, column=3, rowspan=2, padx=12)

    def _reveal(self, file_path: str) -> None:
        if not file_path or not Path(file_path).exists():
            messagebox.showinfo(
                "MeTube", "File location unknown — check your download folder"
            )
            return
        open_in_explorer(file_path)

    def _clear(self) -> None:
        if not messagebox.askyesno("MeTube", "Clear the whole download history?"):
            return
        store.clear_history()
        self.refresh()
