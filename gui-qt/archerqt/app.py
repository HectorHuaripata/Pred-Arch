"""
Archer Qt application: window, tray, and the visibility → telemetry rule.
"""

import logging
import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QSettings, Qt, QUrl, Signal, Slot, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from archerqt.bus import ArcherBus
from archerqt.history import History

logger = logging.getLogger("archer-qt")

HERE = Path(__file__).resolve().parent
QML_DIR = HERE.parent / "qml"
ASSET_DIRS = (HERE.parent / "assets", HERE.parent.parent / "gui" / "assets", Path("/opt/archer/assets"))

# Telemetry cadence by what the user can see (docs/ROADMAP_V3.md, step 3).
INTERVAL_HIDDEN_MS = 0
INTERVAL_VISIBLE_MS = 1000
INTERVAL_OVERVIEW_MS = 1000

PROFILE_LABELS = {
    "low-power": "Eco",
    "quiet": "Quiet",
    "balanced": "Balanced",
    "balanced-performance": "Balanced+",
    "performance": "Performance",
}


def _find_asset(name):
    for d in ASSET_DIRS:
        p = d / name
        if p.is_file():
            return str(p)
    return ""


class AppController(QObject):
    """Things QML needs that are not D-Bus: window/tray plumbing."""

    overviewVisibleChanged = Signal()
    windowVisibleChanged = Signal()
    chartRangeChanged = Signal()

    def __init__(self, bus, parent=None):
        super().__init__(parent)
        self._bus = bus
        self._overview_visible = True
        self._window_visible = False
        self._tray = None
        self._profile_actions = {}
        self._window = None
        self._settings = QSettings("archer", "archer-qt")
        self._chart_range = int(self._settings.value("overview/chartRange", 600))

    # QML tells us which page is in front; we decide the cadence.
    @Property(bool, notify=overviewVisibleChanged)
    def overviewVisible(self):
        return self._overview_visible

    @overviewVisible.setter
    def overviewVisible(self, value):
        value = bool(value)
        if value != self._overview_visible:
            self._overview_visible = value
            self.overviewVisibleChanged.emit()
            self._update_interval()

    @Property(bool, notify=windowVisibleChanged)
    def windowVisible(self):
        return self._window_visible

    @Slot(bool)
    def setWindowVisible(self, value):
        value = bool(value)
        if value != self._window_visible:
            self._window_visible = value
            self.windowVisibleChanged.emit()
            self._update_interval()

    # Seconds of temperature history shown on the Overview; remembered.
    @Property(int, notify=chartRangeChanged)
    def chartRange(self):
        return self._chart_range

    @chartRange.setter
    def chartRange(self, seconds):
        seconds = int(seconds)
        if seconds != self._chart_range:
            self._chart_range = seconds
            self._settings.setValue("overview/chartRange", seconds)
            self.chartRangeChanged.emit()

    @Property(bool, constant=True)
    def hasTray(self):
        return self._tray is not None

    @Property(str, constant=True)
    def iconPath(self):
        return _find_asset("archer.svg")

    def _update_interval(self):
        if not self._window_visible:
            ms = INTERVAL_HIDDEN_MS
        elif self._overview_visible:
            ms = INTERVAL_OVERVIEW_MS
        else:
            ms = INTERVAL_VISIBLE_MS
        self._bus.setTelemetryInterval(ms)

    # -- tray ------------------------------------------------------------

    def attach_window(self, window):
        self._window = window
        window.visibleChanged.connect(self.setWindowVisible)
        self.setWindowVisible(window.isVisible())

    def build_tray(self, app):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("No system tray available; closing the window quits")
            return
        icon = QIcon(_find_asset("archer-tray.png") or _find_asset("archer.svg"))
        self._tray = QSystemTrayIcon(icon, app)
        self._tray.setToolTip("Archer")
        menu = QMenu()
        self._profile_menu = menu.addMenu("Performance profile")
        menu.addSeparator()
        open_action = QAction("Open Archer", menu)
        open_action.triggered.connect(self.show_window)
        menu.addAction(open_action)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(app.quit)
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

        thermal = self._bus.interfaces["Thermal"]
        thermal.profileChoicesChanged.connect(self._rebuild_profile_menu)
        thermal.profileChanged.connect(self._sync_profile_menu)
        telemetry = self._bus.interfaces["Telemetry"]
        telemetry.cpuTempChanged.connect(self._update_tooltip)
        telemetry.gpuTempChanged.connect(self._update_tooltip)
        thermal.profileChanged.connect(self._update_tooltip)
        self._rebuild_profile_menu()

    def _rebuild_profile_menu(self):
        self._profile_menu.clear()
        self._profile_actions = {}
        thermal = self._bus.interfaces["Thermal"]
        for choice in thermal.profileChoices or []:
            action = QAction(PROFILE_LABELS.get(choice, choice), self._profile_menu)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, c=choice: self._bus.call("Thermal", "SetProfile", [c]))
            self._profile_menu.addAction(action)
            self._profile_actions[choice] = action
        self._sync_profile_menu()

    def _sync_profile_menu(self):
        current = self._bus.interfaces["Thermal"].profile
        for choice, action in self._profile_actions.items():
            action.setChecked(choice == current)

    def _update_tooltip(self):
        t = self._bus.interfaces["Telemetry"]
        p = self._bus.interfaces["Thermal"].profile or ""
        if self._window_visible and t.cpuTemp is not None:
            text = f"Archer · {PROFILE_LABELS.get(p, p)} · CPU {t.cpuTemp} °C · GPU {t.gpuTemp} °C"
        else:
            # Hidden: no telemetry is flowing, so do not show stale numbers.
            text = f"Archer · {PROFILE_LABELS.get(p, p)}"
        self._tray.setToolTip(text)

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            if self._window and self._window.isVisible():
                self._window.hide()
            else:
                self.show_window()

    # The daemon runs as root and cannot restart the user's pipewire; the
    # client that sees NoiseSuppression change does it (docs/DBUS_V2.md).
    def watch_audio(self):
        audio = self._bus.interfaces["Audio"]
        self._audio_seen = audio.noiseSuppression
        audio.noiseSuppressionChanged.connect(self._on_noise_changed)

    def _on_noise_changed(self):
        value = self._bus.interfaces["Audio"].noiseSuppression
        if self._audio_seen is None or value == self._audio_seen:
            self._audio_seen = value
            return
        self._audio_seen = value
        QProcess.startDetached("systemctl", ["--user", "restart", "pipewire.service"])
        if self._tray:
            self._tray.showMessage("Archer", "Noise suppression %s — PipeWire restarted."
                                   % ("enabled" if value else "disabled"))

    @Slot()
    def show_window(self):
        if self._window:
            self._window.show()
            self._window.raise_()
            self._window.requestActivate()


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    argv = list(sys.argv if argv is None else argv)

    # Breeze-styled controls on Plasma; Fusion elsewhere.
    if "QT_QUICK_CONTROLS_STYLE" not in os.environ:
        QQuickStyle.setStyle("org.kde.desktop" if os.environ.get("XDG_CURRENT_DESKTOP", "").upper().startswith("KDE")
                             else "Fusion")

    QApplication.setApplicationName("Archer")
    QApplication.setOrganizationName("archer")
    QApplication.setOrganizationDomain("archer.github.io")
    QApplication.setDesktopFileName("io.github.archer")
    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(_find_asset("archer.svg")))
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    # Let Python handle SIGINT while Qt's loop runs.
    keepalive = QTimer(); keepalive.start(500); keepalive.timeout.connect(lambda: None)

    bus = ArcherBus()
    controller = AppController(bus)
    # Context properties are not owned by the engine: every object handed
    # to QML must stay referenced here for the life of the application.
    history = History()

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("Bus", bus)
    ctx.setContextProperty("App", controller)
    ctx.setContextProperty("History", history)
    for short, obj in bus.interfaces.items():
        ctx.setContextProperty(short, obj)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        logger.error("Main.qml failed to load")
        return 1
    window = engine.rootObjects()[0]

    controller.build_tray(app)
    controller.attach_window(window)
    controller.watch_audio()
    if "--hidden" not in argv:
        window.show()

    rc = app.exec()
    # Tear the QML tree down while the context objects still exist, or
    # every binding logs "Cannot read property of null" on exit.
    del engine
    return rc
