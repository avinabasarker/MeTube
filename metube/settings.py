"""Settings persistence (atomic) and defaults."""

from __future__ import annotations

from typing import Any

from . import config
from .utils import read_json, write_json

DEFAULTS: dict[str, Any] = {
    "first_run": True,
    "download_folder": "",
    "default_format": "MP3",
    "default_quality": "Best Available",
    "delay_min": 3,
    "delay_max": 5,
    "auto_update_ytdlp": True,
    "finish_notification": True,
    "keep_awake": True,
}


class Settings:
    """Dict-like settings bag with attribute access."""

    def __init__(self, data: dict[str, Any] | None = None):
        merged = dict(DEFAULTS)
        if isinstance(data, dict):
            merged.update({k: v for k, v in data.items() if k in DEFAULTS})
        self._data = merged

    # -- dict-ish ------------------------------------------------------
    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    # -- typed accessors ----------------------------------------------
    @property
    def download_folder(self) -> str:
        return str(self._data.get("download_folder") or "")

    @property
    def delay_min(self) -> int:
        try:
            return int(self._data.get("delay_min", 3))
        except (TypeError, ValueError):
            return 3

    @property
    def delay_max(self) -> int:
        try:
            return int(self._data.get("delay_max", 5))
        except (TypeError, ValueError):
            return 5

    @property
    def default_format(self) -> str:
        value = str(self._data.get("default_format") or "MP3")
        return value if value in ("MP3", "M4A", "MP4") else "MP3"

    @property
    def default_quality(self) -> str:
        return str(self._data.get("default_quality") or "Best Available")

    def validated_delays(self) -> tuple[int, int]:
        low = self.delay_min
        high = self.delay_max
        if low < 2:
            low = 2
        if high < low:
            high = low
        return low, high


def settings_exist() -> bool:
    """First run <=> settings.json absent (Section 5.1)."""
    return config.settings_path().exists()


def load_settings() -> Settings:
    if not settings_exist():
        return Settings()
    raw = read_json(config.settings_path(), {})
    return Settings(raw if isinstance(raw, dict) else {})


def save_settings(settings: Settings | dict[str, Any]) -> None:
    data = settings.as_dict() if isinstance(settings, Settings) else dict(settings)
    write_json(config.settings_path(), data)


def reset_for_first_run() -> None:
    """Reset settings (Settings screen button).

    Section 5.1 defines first run as "settings.json absent", so the reset
    removes the file: that is the only way the next launch can show the
    folder picker again.
    """
    try:
        config.settings_path().unlink(missing_ok=True)
    except OSError:
        pass
