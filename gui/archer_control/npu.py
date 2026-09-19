"""
Intel NPU utilisation through the accel class (ivpu driver).

npu_busy_time_us accumulates microseconds the NPU was busy; utilisation is
its delta over the wall-clock delta between two reads. The file stays
readable while the device sleeps in D3 and reading it does not wake it.
"""

import time
from pathlib import Path

ACCEL_ROOT = Path("/sys/class/accel")


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


class NpuProbe:
    def __init__(self):
        self.busy_path = None
        for accel in sorted(ACCEL_ROOT.glob("accel*")):
            candidate = accel / "device/npu_busy_time_us"
            if candidate.exists():
                self.busy_path = candidate
                break
        self._last = None      # (monotonic seconds, busy microseconds)

    @property
    def available(self):
        return self.busy_path is not None

    def usage_percent(self):
        """0-100 over the interval since the previous call; 0 on the first."""
        raw = _read(self.busy_path) if self.busy_path else None
        if raw is None or not raw.isdigit():
            return 0
        now, busy = time.monotonic(), int(raw)
        prev, self._last = self._last, (now, busy)
        if prev is None or now <= prev[0]:
            return 0
        percent = (busy - prev[1]) / ((now - prev[0]) * 1_000_000) * 100
        return max(0, min(100, int(round(percent))))
