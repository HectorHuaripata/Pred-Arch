"""
Multi-resolution history for the temperature chart.

Three fixed ring buffers per series, RRD-style: 1 s × 600 (10 min),
10 s × 360 (1 h), 60 s × 1440 (1 day). About 20 KB in total, allocated
once; a push costs a handful of float writes and the chart never reads
more than 1440 points whatever the range. Time the GUI was not sampling
(hidden, daemon away) is recorded as NaN so the axis stays wall-clock.
"""

import math
import time
from array import array

from PySide6.QtCore import QObject, Slot

NAN = float("nan")

# (seconds per point, points kept)
LEVELS = ((1, 600), (10, 360), (60, 1440))
SERIES = 2
# Longest gap worth replaying; beyond a day the buffers are all NaN anyway.
MAX_GAP_S = LEVELS[-1][0] * LEVELS[-1][1]


class _Ring:
    """Fixed-size ring of averaged points at one resolution (`step` seconds)."""

    __slots__ = ("step", "size", "data", "head", "count", "acc_sum", "acc_n", "acc_len")

    def __init__(self, step, size):
        self.step = step
        self.size = size
        self.data = [array("f", [NAN]) * size for _ in range(SERIES)]
        self.head = 0            # next write position
        self.count = 0           # points written so far (≤ size)
        self.acc_sum = [0.0] * SERIES
        self.acc_n = [0] * SERIES
        self.acc_len = 0         # raw seconds accumulated towards the next point

    def add_second(self, values):
        """Accumulate one second of samples; writes a point every `step` seconds."""
        for i, v in enumerate(values):
            if not math.isnan(v):
                self.acc_sum[i] += v
                self.acc_n[i] += 1
        self.acc_len += 1
        if self.acc_len >= self.step:
            for i in range(SERIES):
                self.data[i][self.head] = self.acc_sum[i] / self.acc_n[i] if self.acc_n[i] else NAN
                self.acc_sum[i] = 0.0
                self.acc_n[i] = 0
            self.acc_len = 0
            self.head = (self.head + 1) % self.size
            self.count = min(self.count + 1, self.size)

    def last(self, n, series):
        """The most recent n points, oldest first, as a plain list."""
        n = min(n, self.count)
        if n == 0:
            return []
        start = (self.head - n) % self.size
        d = self.data[series]
        if start + n <= self.size:
            return d[start:start + n].tolist()
        return d[start:].tolist() + d[:start + n - self.size].tolist()


class History(QObject):
    """Exposed to QML as `History`: push() one sample per second, window()
    to read a range back at a fitting resolution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rings = [_Ring(step, size) for step, size in LEVELS]
        self._last_push = 0.0

    @Slot(float, float)
    def push(self, a, b):
        """One sample per wall-clock second. Missed seconds become NaN."""
        now = time.monotonic()
        if self._last_push:
            missed = int(round(now - self._last_push)) - 1
            for _ in range(min(max(missed, 0), MAX_GAP_S)):
                self._add((NAN, NAN))
        self._last_push = now
        self._add((float(a), float(b)))

    def _add(self, values):
        for ring in self._rings:
            ring.add_second(values)

    @Slot(int, result="QVariantList")
    def window(self, seconds):
        """[stepSeconds, pointsA, pointsB] covering the last `seconds`,
        from the finest ring that holds that much time."""
        ring = self._rings[-1]
        for candidate in self._rings:
            if candidate.step * candidate.size >= seconds:
                ring = candidate
                break
        n = max(2, seconds // ring.step)
        return [ring.step, ring.last(n, 0), ring.last(n, 1)]
