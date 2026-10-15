"""Dark palette and typography. One source of truth for every colour."""

from __future__ import annotations

BG = "#1B1B1F"
CARD = "#24242A"
CARD_HOVER = "#2C2C34"
ACCENT = "#6C5CE7"
ACCENT_HOVER = "#5A49D6"
BORDER = "#3A3A42"
TEXT = "#EAEAEA"
MUTED = "#9A9AA5"
SUCCESS = "#2ECC71"
FAILURE = "#E74C3C"
WARNING = "#F0A020"

FONT_FAMILY = "Segoe UI"


def font(size: int = 13, weight: str = "normal") -> tuple:
    return (FONT_FAMILY, size, weight)


FONT_TITLE = font(22, "bold")
FONT_HEADING = font(15, "bold")
FONT_BODY = font(13)
FONT_SMALL = font(11)
FONT_TINY = font(10)
FONT_BUTTON = font(12, "bold")
FONT_BADGE = font(10, "bold")
FONT_ICON = font(16, "bold")


def status_color(status: str) -> str:
    if not status:
        return TEXT
    if status.startswith("Completed"):
        return SUCCESS
    if status.startswith("Failed"):
        return FAILURE
    if status == "Cancelled":
        return MUTED
    if status == "Paused":
        return WARNING
    if status.startswith(("Starting", "Retrying", "Cooling")):
        return WARNING
    if status.startswith(("Downloading", "Converting")):
        return ACCENT
    return TEXT
