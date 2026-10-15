"""A single queue card: thumbnail, title, meta, badge, status, progress."""

from __future__ import annotations

import logging

import customtkinter as ctk

from ..models import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_PAUSED,
    QueueItem,
)
from ..theme import (
    ACCENT,
    ACCENT_HOVER,
    BORDER,
    CARD,
    FONT_BODY,
    FONT_BADGE,
    FONT_BUTTON,
    FONT_HEADING,
    FONT_SMALL,
    MUTED,
    SUCCESS,
    TEXT,
    WARNING,
    font,
    status_color,
)

log = logging.getLogger("metube.ui.card")

THUMB_SIZE = (96, 54)


class QueueCard(ctk.CTkFrame):
    def __init__(self, master, item: QueueItem, controller) -> None:
        super().__init__(
            master,
            fg_color=CARD,
            corner_radius=10,
            border_width=1,
            border_color=BORDER,
        )
        self.item = item
        self.controller = controller
        self._button_key: tuple = ()
        self._buttons: list[ctk.CTkButton] = []
        self._thumb_image = None

        self.grid_columnconfigure(1, weight=1)
        self._build()
        self.refresh()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        self._thumb = ctk.CTkLabel(
            self,
            text="▶",
            width=THUMB_SIZE[0],
            height=THUMB_SIZE[1],
            fg_color=ACCENT,
            corner_radius=6,
            text_color="#FFFFFF",
            font=FONT_HEADING,
        )
        self._thumb.grid(row=0, column=0, rowspan=3, padx=(12, 12), pady=12, sticky="n")

        self._title = ctk.CTkLabel(
            self,
            text="",
            font=FONT_HEADING,
            text_color=TEXT,
            anchor="w",
            justify="left",
            wraplength=560,
        )
        self._title.grid(row=0, column=1, sticky="ew", pady=(12, 0))

        self._badge = ctk.CTkLabel(
            self,
            text="",
            font=FONT_BADGE,
            text_color="#FFFFFF",
            fg_color=ACCENT,
            corner_radius=6,
            width=46,
            height=20,
        )
        self._badge.grid(row=0, column=2, padx=(8, 12), pady=(12, 0), sticky="ne")

        self._meta = ctk.CTkLabel(
            self, text="", font=FONT_SMALL, text_color=MUTED, anchor="w"
        )
        self._meta.grid(row=1, column=1, columnspan=2, sticky="w")

        self._status = ctk.CTkLabel(
            self, text="", font=FONT_BODY, text_color=TEXT, anchor="w"
        )
        self._status.grid(row=2, column=1, sticky="w", pady=(2, 0))

        self._progress = ctk.CTkProgressBar(
            self, height=6, corner_radius=3, progress_color=ACCENT, fg_color=BORDER
        )
        self._progress.set(0)
        self._progress.grid(row=3, column=1, columnspan=2, sticky="ew", pady=(6, 0))

        self._button_bar = ctk.CTkFrame(self, fg_color="transparent")
        self._button_bar.grid(row=4, column=1, columnspan=2, sticky="e", pady=(6, 10))

    # ------------------------------------------------------------------
    def set_thumbnail(self, ctk_image) -> None:
        self._thumb_image = ctk_image
        self._thumb.configure(image=ctk_image, text="")

    def refresh(self) -> None:
        item = self.item
        self._title.configure(text=item.display_title)
        self._meta.configure(text=item.meta_line)
        self._badge.configure(text=item.fmt)
        status = item.status
        self._status.configure(text=status, text_color=status_color(status))
        if status.startswith("Completed"):
            self._progress.configure(progress_color=SUCCESS)
            self._progress.set(1.0)
        elif status.startswith("Failed"):
            self._progress.configure(progress_color="#E74C3C")
        elif status == STATUS_CANCELLED:
            self._progress.configure(progress_color=MUTED)
        else:
            self._progress.configure(progress_color=ACCENT)
            self._progress.set(max(0.0, min(1.0, item.progress / 100.0)))
        self._render_buttons()

    # ------------------------------------------------------------------
    def _button_specs(self) -> list[tuple[str, callable, str]]:
        status = self.item.status
        controller = self.controller
        item = self.item
        if status == STATUS_PAUSED:
            return [
                ("Resume", controller.on_resume, "accent"),
                ("Cancel", lambda: controller.on_cancel(item.id), "danger"),
            ]
        if status.startswith("Failed"):
            return [
                ("Retry", lambda: controller.on_retry(item.id), "accent"),
                ("Cancel", lambda: controller.on_dismiss(item.id), "danger"),
            ]
        if status.startswith("Completed"):
            return [
                ("Show in folder", lambda: controller.on_show_in_folder(item), "neutral"),
                ("Open file", lambda: controller.on_open_file(item), "accent"),
            ]
        if status == STATUS_CANCELLED:
            return [
                ("Retry", lambda: controller.on_retry(item.id), "accent"),
                ("Dismiss", lambda: controller.on_dismiss(item.id), "danger"),
            ]
        return [
            ("Pause", controller.on_pause, "accent"),
            ("Cancel", lambda: controller.on_cancel(item.id), "danger"),
        ]

    def _render_buttons(self) -> None:
        specs = self._button_specs()
        key = tuple(label for label, _, _ in specs)
        if key == self._button_key:
            return
        self._button_key = key
        for button in self._buttons:
            button.destroy()
        self._buttons = []
        for label, command, kind in specs:
            if kind == "danger":
                button = ctk.CTkButton(
                    self._button_bar,
                    text=label,
                    width=86,
                    height=26,
                    font=FONT_BUTTON,
                    fg_color="transparent",
                    hover_color="#3A2A2C",
                    border_width=1,
                    border_color="#E74C3C",
                    text_color="#F08A80",
                    command=command,
                )
            elif kind == "neutral":
                button = ctk.CTkButton(
                    self._button_bar,
                    text=label,
                    width=104,
                    height=26,
                    font=FONT_BUTTON,
                    fg_color="transparent",
                    hover_color="#33333C",
                    border_width=1,
                    border_color=BORDER,
                    text_color=TEXT,
                    command=command,
                )
            else:
                button = ctk.CTkButton(
                    self._button_bar,
                    text=label,
                    width=86,
                    height=26,
                    font=FONT_BUTTON,
                    fg_color=ACCENT,
                    hover_color=ACCENT_HOVER,
                    text_color="#FFFFFF",
                    command=command,
                )
            button.pack(side="right", padx=(6, 0))
            self._buttons.append(button)
