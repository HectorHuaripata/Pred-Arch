"""
Application controller: the little that QML needs beyond D-Bus.

* decides the telemetry cadence from what the user can see (window
  hidden → unsubscribe; a page in front → the configured interval);
* owns the tray and the show/hide behaviour;
* performs session-side reactions the root daemon cannot, such as
  restarting the user's PipeWire when noise suppression is toggled.
"""

import logging

from PySide6.QtCore import Property, QCoreApplication, QObject, QProcess, Signal, Slot

from archerqt import paths
from archerqt.tray import TrayIcon

logger = logging.getLogger("archer-qt")

PIPEWIRE_RESTART = ("systemctl", ["--user", "restart", "pipewire.service"])


def _tr(text):
    return QCoreApplication.translate("Controller", text)


class AppController(QObject):
    overviewVisibleChanged = Signal()
    windowVisibleChanged = Signal()

    def __init__(self, bus, settings, catalog, parent=None):
        super().__init__(parent)
        self._bus = bus
        self._settings = settings
        self._overview_visible = True
        self._window_visible = False
        self._window = None
        self._noise_seen = None
        self._tray = TrayIcon(bus, catalog, self)
        self._tray.activated.connect(self.toggleWindow)
        self._tray.quitRequested.connect(QCoreApplication.quit)
        bus.interfaces["Audio"].noiseSuppressionChanged.connect(self._on_noise_changed)

    # -- properties for QML ----------------------------------------------

    @Property(bool, notify=overviewVisibleChanged)
    def overviewVisible(self):
        """QML sets this when the Overview page is the one in front."""
        return self._overview_visible

    @overviewVisible.setter
    def overviewVisible(self, value):
        value = bool(value)
        if value != self._overview_visible:
            self._overview_visible = value
            self.overviewVisibleChanged.emit()
            self._update_cadence()

    @Property(bool, notify=windowVisibleChanged)
    def windowVisible(self):
        return self._window_visible

    @Property(bool, constant=True)
    def hasTray(self):
        return self._tray.available

    @Property(str, constant=True)
    def iconPath(self):
        return paths.asset("archer.svg")

    # -- window ------------------------------------------------------------

    def attach_window(self, window):
        self._window = window
        window.visibleChanged.connect(self._on_window_visible)
        self._on_window_visible(window.isVisible())

    def _on_window_visible(self, visible):
        visible = bool(visible)
        if visible != self._window_visible:
            self._window_visible = visible
            self.windowVisibleChanged.emit()
            self._tray.set_window_visible(visible)
            self._update_cadence()

    @Slot()
    def showWindow(self):
        if self._window:
            self._window.show()
            self._window.raise_()
            self._window.requestActivate()

    @Slot()
    def toggleWindow(self):
        if self._window and self._window.isVisible():
            self._window.hide()
        else:
            self.showWindow()

    # -- cadence -----------------------------------------------------------

    def _update_cadence(self):
        if not self._window_visible:
            ms = self._settings.intervalHiddenMs
        elif self._overview_visible:
            ms = self._settings.intervalOverviewMs
        else:
            ms = self._settings.intervalVisibleMs
        self._bus.setTelemetryInterval(ms)

    # -- session-side reactions --------------------------------------------

    def _on_noise_changed(self):
        """The daemon renames the PipeWire filter file; restarting the
        user's PipeWire has to happen in the user's session — here."""
        value = self._bus.interfaces["Audio"].noiseSuppression
        if self._noise_seen is None or value == self._noise_seen:
            self._noise_seen = value            # initial load, not a change
            return
        self._noise_seen = value
        program, args = PIPEWIRE_RESTART
        QProcess.startDetached(program, args)
        self._tray.notify("Archer", _tr("Noise suppression enabled — PipeWire restarted.")
                          if value else _tr("Noise suppression disabled — PipeWire restarted."))
