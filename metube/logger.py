"""Logging: rotating app.log plus a crash.log written by the global handler."""

from __future__ import annotations

import datetime as _dt
import logging
import logging.handlers
import sys
import traceback
from pathlib import Path

from . import config

_LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(threadName)s] %(name)s: %(message)s"
_configured = False


def setup_logging() -> logging.Logger:
    """Configure the root logger once. Safe to call repeatedly."""
    global _configured
    logger = logging.getLogger("metube")
    if _configured:
        return logger

    logs = config.logs_dir()
    logs.mkdir(parents=True, exist_ok=True)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = logging.handlers.RotatingFileHandler(
        logs / "app.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(handler)

    # stderr may be None in a --noconsole build; guard it.
    if sys.stderr is not None:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(stream)

    _configured = True
    logger.info("=" * 70)
    logger.info("MeTube %s starting", __import__("metube").__version__)
    logger.info("frozen=%s app_dir=%s", config.is_frozen(), config.app_dir())
    logger.info(
        "data_dir=%s  (%s)", config.data_dir(), config.data_dir_reason()
    )
    logger.info("settings.json=%s", config.settings_path())
    return logger


def get_logger(name: str = "metube") -> logging.Logger:
    return logging.getLogger(name)


def log_crash(context: str, exc: BaseException | None = None) -> str:
    """Append a full traceback to crash.log and return the formatted text."""
    path = config.crash_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if exc is not None:
        body = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
    else:
        body = "".join(traceback.format_exc())

    text = f"\n===== {stamp} :: {context} =====\n{body}"
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)
    except OSError:
        pass
    try:
        logging.getLogger("metube").error("CRASH in %s\n%s", context, body)
    except Exception:  # pragma: no cover - logging must never raise
        pass
    return text


def _message_box(title: str, text: str) -> None:
    """Native error box; --noconsole apps must never die silently (B11)."""
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)  # MB_ICONERROR
    except Exception:
        if sys.stderr is not None:
            try:
                sys.stderr.write(f"{title}\n{text}\n")
            except Exception:
                pass


def install_excepthooks() -> None:
    """Route uncaught exceptions (main + threads) into crash.log + a dialog."""

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        text = log_crash("uncaught", exc_value)
        _message_box(
            "MeTube - unexpected error",
            "MeTube hit an unexpected error and had to stop.\n\n"
            f"A full report was written to:\n{config.crash_log_path()}\n\n"
            + text.strip().splitlines()[-1][:400],
        )

    def _thread_hook(args):
        if issubclass(args.exc_type, SystemExit):
            return
        log_crash(f"thread {getattr(args.thread, 'name', '?')}", args.exc_value)

    sys.excepthook = _hook
    try:
        import threading

        threading.excepthook = _thread_hook
    except Exception:
        pass
