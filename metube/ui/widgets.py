"""Reusable widgets: true-placeholder textbox, thumbnail loader, toasts."""

from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from ..theme import BORDER, CARD, MUTED, TEXT

log = logging.getLogger("metube.ui.widgets")

PLACEHOLDER_TAG = "_metube_placeholder"


class PlaceholderTextbox(ctk.CTkTextbox):
    """CTkTextbox with a real placeholder (muted, non-blocking).

    Regression B7: v1 pre-filled real text so the user had to delete it before
    pasting.  Here the hint is a tagged run that disappears on focus and is
    never returned by :meth:`get_input`.
    """

    def __init__(self, master, placeholder: str = "", **kwargs):
        kwargs.setdefault("wrap", "word")
        kwargs.setdefault("fg_color", CARD)
        kwargs.setdefault("border_color", BORDER)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("text_color", TEXT)
        super().__init__(master, **kwargs)
        self._placeholder = placeholder
        self._showing_placeholder = False
        try:
            self.tag_config(PLACEHOLDER_TAG, foreground=MUTED)
        except Exception:  # noqa: BLE001 - tag config is cosmetic
            log.debug("could not configure placeholder tag", exc_info=True)
        self.bind("<FocusIn>", self._on_focus_in, add="+")
        self.bind("<FocusOut>", self._on_focus_out, add="+")
        self.after(80, self.show_placeholder)

    # ------------------------------------------------------------------
    def _raw_text(self) -> str:
        return super().get("1.0", "end-1c")

    def show_placeholder(self) -> None:
        if self._showing_placeholder:
            return
        if self._raw_text().strip():
            return
        self.delete("1.0", "end")
        self.insert("1.0", self._placeholder, PLACEHOLDER_TAG)
        self._showing_placeholder = True

    def hide_placeholder(self) -> None:
        if not self._showing_placeholder:
            return
        self.delete("1.0", "end")
        self._showing_placeholder = False

    def _on_focus_in(self, _event=None) -> None:
        if self._showing_placeholder:
            self.hide_placeholder()

    def _on_focus_out(self, _event=None) -> None:
        if not self._raw_text().strip():
            self.show_placeholder()

    # ------------------------------------------------------------------
    def get_input(self) -> str:
        if self._showing_placeholder:
            return ""
        return self._raw_text().strip()

    def clear_input(self) -> None:
        self._showing_placeholder = False
        self.delete("1.0", "end")
        self.show_placeholder()

    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        if self._showing_placeholder:
            self.delete("1.0", "end")
            self._showing_placeholder = False
            self.show_placeholder()


class ThumbnailLoader:
    """Loads thumbnails off-thread and hands PIL images back via the event queue."""

    def __init__(self, events, size: tuple[int, int] = (96, 54)) -> None:
        self.events = events
        self.size = size
        self._inflight: set[str] = set()
        self._lock = threading.Lock()

    def request(self, item_id: str, path: str) -> None:
        if not path or not Path(path).is_file():
            return
        with self._lock:
            if path in self._inflight:
                return
            self._inflight.add(path)
        threading.Thread(
            target=self._load, args=(item_id, path), name="ThumbLoader", daemon=True
        ).start()

    def _load(self, item_id: str, path: str) -> None:
        image = None
        try:
            from PIL import Image, ImageOps

            with Image.open(path) as raw:
                rgb = raw.convert("RGB")
                image = ImageOps.fit(rgb, self.size, method=Image.LANCZOS)
        except Exception:  # noqa: BLE001 - thumbnails are cosmetic
            log.debug("thumbnail load failed: %s", path, exc_info=True)
        finally:
            with self._lock:
                self._inflight.discard(path)
        try:
            self.events.put_nowait(
                {"type": "thumb_ready", "id": item_id, "path": path, "image": image}
            )
        except Exception:  # noqa: BLE001
            pass


class Toast(ctk.CTkToplevel):
    """Transient message pinned to the bottom of the main window.

    It is a borderless, top-most Toplevel whose window carries
    ``WS_EX_LAYERED | WS_EX_TRANSPARENT``, so Windows routes every mouse event
    straight through it to whatever is underneath.  That matters: as an
    in-window frame it sat exactly on the paste box and the "Add to Queue"
    button and silently ate their clicks for a few seconds after every queue
    finish or notice - a real acceptance run lost a typed URL to it.
    """

    def __init__(self, master) -> None:
        super().__init__(master)
        self._master_window = master
        self._hide_job = None
        self.withdraw()
        try:
            self.overrideredirect(True)
            self.attributes("-topmost", True)
        except tk.TclError:
            log.debug("could not make the toast borderless", exc_info=True)
        self.configure(fg_color=CARD)
        self._label = ctk.CTkLabel(self, text="", font=("Segoe UI", 12), text_color=TEXT)
        self._label.pack(padx=16, pady=8)
        self._make_click_through()

    def _make_click_through(self) -> None:
        """Mark the toast window click-through (Windows only, best effort)."""
        if os.name != "nt":
            return
        try:
            import ctypes

            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            LWA_ALPHA = 0x00000002
            user32 = ctypes.windll.user32
            handles = [int(self.winfo_id())]
            # Tk wraps a toplevel in an outer window; both must be transparent
            # for hit-testing or the outer one still swallows the click.
            parent = int(user32.GetParent(handles[0]) or 0)
            if parent:
                handles.append(parent)
            for handle in handles:
                style = user32.GetWindowLongW(handle, GWL_EXSTYLE)
                if not style & WS_EX_TRANSPARENT:
                    user32.SetWindowLongW(
                        handle, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT
                    )
                user32.SetLayeredWindowAttributes(handle, 0, 255, LWA_ALPHA)
        except Exception:  # noqa: BLE001 - a cosmetic toast must never break input
            log.debug("could not make the toast click-through", exc_info=True)

    def show(self, text: str, duration: int = 3200) -> None:
        self._label.configure(text=text)
        self.update_idletasks()
        try:
            master = self._master_window
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_reqwidth()) // 2
            y = (
                master.winfo_rooty()
                + master.winfo_height()
                - self.winfo_reqheight()
                - 16
            )
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:  # noqa: BLE001
            log.debug("could not position the toast", exc_info=True)
        try:
            self.deiconify()
            self.lift()
        except tk.TclError:
            log.debug("could not show the toast", exc_info=True)
        # Tk creates/maps the real window on first show: re-apply afterwards.
        self._make_click_through()
        self.after(60, self._make_click_through)
        if self._hide_job is not None:
            try:
                self.after_cancel(self._hide_job)
            except Exception:  # noqa: BLE001
                pass
        self._hide_job = self.after(duration, self.hide)

    def hide(self) -> None:
        self._hide_job = None
        try:
            self.withdraw()
        except tk.TclError:
            pass
