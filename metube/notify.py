"""Silent Windows toast notification on full queue completion."""

from __future__ import annotations

import logging

log = logging.getLogger("metube.notify")


def queue_finished(completed: int, failed: int, enabled: bool = True) -> bool:
    """Show the aggregate toast. Returns True when a toast was shown."""
    if not enabled or (completed + failed) <= 0:
        return False
    message = f"Queue finished: {completed} completed, {failed} failed."
    try:
        from winotify import Notification

        toast = Notification(
            app_id="MeTube",
            title="MeTube",
            msg=message,
            duration="short",
        )
        toast.show()
        log.info("toast shown: %s", message)
        return True
    except Exception:  # noqa: BLE001 - notifications must never break the app
        log.warning("could not raise toast", exc_info=True)
        return False
