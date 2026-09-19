"""
TelemetrySampler: reads the hot-path sensors only while someone is subscribed.
"""

import time

from gi.repository import Gio, GLib

from archer_control.common import logger
from archer_control.constants import BATTERY_PERIOD_S, BUS_NAME, INTERVAL_MAX_MS, INTERVAL_MIN_MS, SLOW_PERIOD_S


class TelemetrySampler:
    """Reads the hot-path sensors only while someone is subscribed.

    Subscriptions are keyed by the caller's unique bus name and dropped when
    that name leaves the bus, so a crashed client cannot keep the daemon
    sampling. The effective interval is the fastest one requested.
    """

    IFACE = BUS_NAME + ".Telemetry"

    def __init__(self, hw, store, conn, cpu=None, npu=None, slow_hook=None):
        self.hw = hw
        self.store = store
        self._conn = conn
        self._cpu = cpu                  # CpuPolicy or None
        self._npu = npu                  # NpuProbe or None
        self._slow_hook = slow_hook      # called every SLOW_PERIOD_S while sampling
        self._last_slow = 0.0
        self._subs = {}        # sender -> (interval_ms, watch_id)
        self._timer = 0
        self._interval = 0
        self._last_battery = 0.0
        self._extra_listeners = []   # callables(interval_ms) for the v1 shim

    # -- public --------------------------------------------------------

    def subscribe(self, sender, interval_ms):
        interval = max(INTERVAL_MIN_MS, min(INTERVAL_MAX_MS, int(interval_ms)))
        if sender in self._subs:
            _, watch_id = self._subs[sender]
        else:
            watch_id = Gio.bus_watch_name_on_connection(
                self._conn, sender, Gio.BusNameWatcherFlags.NONE,
                None, self._on_vanished)
        self._subs[sender] = (interval, watch_id)
        self._reschedule()

    def unsubscribe(self, sender):
        entry = self._subs.pop(sender, None)
        if entry:
            Gio.bus_unwatch_name(entry[1])
            self._reschedule()

    @property
    def interval_ms(self):
        return self._interval

    def sample_now(self):
        """One synchronous sample, used to seed properties at startup."""
        self._tick(force_battery=True)

    # -- internals -----------------------------------------------------

    def _on_vanished(self, conn, name):
        if name in self._subs:
            logger.info(f"Telemetry subscriber {name} left the bus")
            self.unsubscribe(name)

    def _reschedule(self):
        interval = min((i for i, _ in self._subs.values()), default=0)
        if interval != self._interval:
            if self._timer:
                GLib.source_remove(self._timer)
                self._timer = 0
            self._interval = interval
            if interval:
                self._timer = GLib.timeout_add(interval, self._tick)
                # First reading right away so a fresh client is not left
                # looking at stale values for a whole interval.
                GLib.idle_add(lambda: (self._tick(force_battery=True), False)[1])
        self.store.update(self.IFACE, {
            "IntervalMs": self._interval,
            "Subscribers": len(self._subs),
        })

    def _tick(self, force_battery=False):
        try:
            cpu_rpm, gpu_rpm = self.hw.get_fan_rpm()
            values = {
                "CpuTemp": int(self.hw.get_cpu_temp()),
                "GpuTemp": int(self.hw.get_gpu_temp()),
                "CpuUsage": max(0, min(100, int(self.hw.get_cpu_usage()))),
                "GpuUsage": max(0, min(100, int(self.hw.get_gpu_usage()))),
                "FanRpm": (int(cpu_rpm or 0), int(gpu_rpm or 0)),
                "PowerSourceAc": bool(self.hw.get_power_source()),
                "Memory": tuple(int(v) for v in self.hw.get_memory()),
                "CpuFreqMhz": int(self._cpu.average_mhz()) if self._cpu else 0,
                "NpuUsage": int(self._npu.usage_percent()) if self._npu and self._npu.available else 0,
                "GpuPowerW": float(self.hw.get_gpu_power()),
            }
            now = time.monotonic()
            if force_battery or now - self._last_battery >= BATTERY_PERIOD_S:
                self._last_battery = now
                values["Battery"] = self._battery()
            self.store.update(self.IFACE, values)
            if self._slow_hook and (force_battery or now - self._last_slow >= SLOW_PERIOD_S):
                self._last_slow = now
                self._slow_hook()
        except Exception as e:
            # A transient sysfs hiccup must not kill the timer.
            logger.warning(f"Telemetry sample failed: {e}")
        return True

    def _battery(self):
        info = self.hw.get_battery_info() or {}
        if not info.get("present"):
            return (False, 0.0, "unknown", -1)
        status = str(info.get("status", "unknown")).lower()
        if status == "not charging":
            status = "idle"         # plugged in, limiter or full threshold holding
        elif status not in ("charging", "discharging", "full"):
            status = "unknown"
        seconds = info.get("seconds_remaining")
        return (
            True,
            float(info.get("percentage", 0)),
            status,
            int(seconds) if seconds is not None else -1,
        )


# ---------------------------------------------------------------------------
# Lighting coalescer
# ---------------------------------------------------------------------------
