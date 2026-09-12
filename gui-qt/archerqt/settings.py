"""
User preferences and tunable parameters.

Two kinds of values live here, both reachable from QML as `Settings`:

* preferences the user changes in the UI and expects to find again
  (`chartRange`), persisted with QSettings;
* parameters with sensible defaults that a packager or power user may
  override in the same settings file without touching code (telemetry
  cadences, colour thresholds). They are read once at startup.

The settings file is the standard Qt location, e.g.
~/.config/archer/archer-qt.conf.
"""

from PySide6.QtCore import Property, QObject, QSettings, Signal

ORGANIZATION = "archer"
APPLICATION = "archer-qt"

# Telemetry cadence by what the user can see, in milliseconds. 0 means
# unsubscribed. The daemon clamps requests to 250–5000 ms.
DEFAULT_INTERVAL_HIDDEN_MS = 0
DEFAULT_INTERVAL_VISIBLE_MS = 1000
DEFAULT_INTERVAL_OVERVIEW_MS = 1000
# The temperature chart samples the properties on this period.
DEFAULT_CHART_SAMPLE_MS = 1000
DEFAULT_CHART_RANGE_S = 600

# Colour thresholds for the gauges.
DEFAULT_TEMP_WARN_C = 70
DEFAULT_TEMP_HOT_C = 85
DEFAULT_MEMORY_HOT_PERCENT = 90


class AppSettings(QObject):
    """Exposed to QML as `Settings`. Read once at startup; `chartRange` is
    the only value written back."""

    chartRangeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = QSettings(ORGANIZATION, APPLICATION)
        self._chart_range = self._int("overview/chartRange", DEFAULT_CHART_RANGE_S)
        self._interval_hidden = self._int("telemetry/hiddenMs", DEFAULT_INTERVAL_HIDDEN_MS)
        self._interval_visible = self._int("telemetry/visibleMs", DEFAULT_INTERVAL_VISIBLE_MS)
        self._interval_overview = self._int("telemetry/overviewMs", DEFAULT_INTERVAL_OVERVIEW_MS)
        self._chart_sample = self._int("overview/chartSampleMs", DEFAULT_CHART_SAMPLE_MS)
        self._temp_warn = self._int("thresholds/tempWarnC", DEFAULT_TEMP_WARN_C)
        self._temp_hot = self._int("thresholds/tempHotC", DEFAULT_TEMP_HOT_C)
        self._memory_hot = self._int("thresholds/memoryHotPercent", DEFAULT_MEMORY_HOT_PERCENT)

    def _int(self, key, default):
        try:
            return int(self._store.value(key, default))
        except (TypeError, ValueError):
            return default

    # -- persisted preference -------------------------------------------

    @Property(int, notify=chartRangeChanged)
    def chartRange(self):
        """Seconds of temperature history shown on the Overview."""
        return self._chart_range

    @chartRange.setter
    def chartRange(self, seconds):
        seconds = int(seconds)
        if seconds != self._chart_range:
            self._chart_range = seconds
            self._store.setValue("overview/chartRange", seconds)
            self.chartRangeChanged.emit()

    # -- tunables (constant for the life of the process) ----------------

    @Property(int, constant=True)
    def intervalHiddenMs(self):
        """Telemetry interval while the window is hidden (0 = unsubscribed)."""
        return self._interval_hidden

    @Property(int, constant=True)
    def intervalVisibleMs(self):
        """Telemetry interval while a page other than Overview is in front."""
        return self._interval_visible

    @Property(int, constant=True)
    def intervalOverviewMs(self):
        """Telemetry interval while the Overview is in front."""
        return self._interval_overview

    @Property(int, constant=True)
    def chartSampleMs(self):
        """Period of the temperature chart's sampling timer."""
        return self._chart_sample

    @Property(int, constant=True)
    def tempWarnC(self):
        """Temperature from which gauges turn to the warning colour."""
        return self._temp_warn

    @Property(int, constant=True)
    def tempHotC(self):
        """Temperature from which gauges turn to the critical colour."""
        return self._temp_hot

    @Property(int, constant=True)
    def memoryHotPercent(self):
        """Memory usage from which the gauge turns to the critical colour."""
        return self._memory_hot
