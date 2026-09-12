"""
LightingCoalescer: last-state-wins write scheduler, one slot per LED device.
"""

from gi.repository import GLib

from archer_control.common import logger
from archer_control.constants import LIGHTING_FLUSH_MS


class LightingCoalescer:
    """Last-state-wins write scheduler, one slot per LED device.

    The first request in a quiet period is written immediately and its
    error, if any, is returned to the caller. Requests arriving inside the
    following LIGHTING_FLUSH_MS window replace each other and the newest is
    written when the window closes; failures there are logged, and the
    property (which only updates on a successful write) is the client's
    confirmation.
    """

    def __init__(self):
        self._pending = {}    # device -> callable
        self._timer = 0

    def request(self, device, write_fn):
        if self._timer:
            self._pending[device] = write_fn
            return
        write_fn()            # may raise; caller reports
        self._timer = GLib.timeout_add(LIGHTING_FLUSH_MS, self._flush)

    def _flush(self):
        pending, self._pending = self._pending, {}
        for device, fn in pending.items():
            try:
                fn()
            except Exception as e:
                logger.warning(f"Coalesced lighting write for {device} failed: {e}")
        if self._pending:
            # New requests arrived while flushing; keep the window open.
            return True
        self._timer = 0
        return False


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------
