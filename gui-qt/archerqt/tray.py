"""
System tray icon: open/hide the window, switch the performance profile,
show temperatures in the tooltip while telemetry is flowing.
"""

import logging

from PySide6.QtCore import QCoreApplication, QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from archerqt import paths

logger = logging.getLogger("archer-qt")


def _tr(text):
    return QCoreApplication.translate("Tray", text)


class TrayIcon(QObject):
    """Wraps QSystemTrayIcon. `available` is False when the desktop has no
    tray, in which case closing the window quits instead of hiding."""

    activated = Signal()      # left click / double click
    quitRequested = Signal()

    def __init__(self, bus, catalog, parent=None):
        super().__init__(parent)
        self._bus = bus
        self._catalog = catalog
        self._icon = None
        self._profile_actions = {}
        self._window_visible = False
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("No system tray available; closing the window quits")
            return
        self._build()

    @property
    def available(self):
        """Whether a tray icon exists on this desktop."""
        return self._icon is not None

    def set_window_visible(self, visible):
        """Tooltip shows temperatures only while telemetry flows (window visible)."""
        self._window_visible = visible
        self._update_tooltip()

    def notify(self, title, text):
        """Desktop notification through the tray, if there is one."""
        if self._icon:
            self._icon.showMessage(title, text)

    # -- construction ----------------------------------------------------

    def _build(self):
        icon = QIcon(paths.asset("archer-tray.png") or paths.asset("archer.svg"))
        self._icon = QSystemTrayIcon(icon, self)
        menu = QMenu()
        self._profile_menu = menu.addMenu(_tr("Performance profile"))
        menu.addSeparator()
        open_action = QAction(_tr("Open Archer"), menu)
        open_action.triggered.connect(self.activated)
        menu.addAction(open_action)
        quit_action = QAction(_tr("Quit"), menu)
        quit_action.triggered.connect(self.quitRequested)
        menu.addAction(quit_action)
        self._menu = menu                      # keep alive; the tray does not own it
        self._icon.setContextMenu(menu)
        self._icon.activated.connect(self._on_activated)
        self._icon.show()

        thermal = self._bus.interfaces["Thermal"]
        thermal.profileChoicesChanged.connect(self._rebuild_profiles)
        thermal.profileChanged.connect(self._sync_profiles)
        thermal.profileChanged.connect(self._update_tooltip)
        telemetry = self._bus.interfaces["Telemetry"]
        telemetry.cpuTempChanged.connect(self._update_tooltip)
        telemetry.gpuTempChanged.connect(self._update_tooltip)
        self._rebuild_profiles()

    def _rebuild_profiles(self):
        self._profile_menu.clear()
        self._profile_actions = {}
        for choice in self._bus.interfaces["Thermal"].profileChoices or []:
            action = QAction(self._catalog.profileLabel(choice), self._profile_menu)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, c=choice: self._bus.call("Thermal", "SetProfile", [c]))
            self._profile_menu.addAction(action)
            self._profile_actions[choice] = action
        self._sync_profiles()

    def _sync_profiles(self):
        current = self._bus.interfaces["Thermal"].profile
        for choice, action in self._profile_actions.items():
            action.setChecked(choice == current)

    def _update_tooltip(self):
        if not self._icon:
            return
        telemetry = self._bus.interfaces["Telemetry"]
        profile = self._catalog.profileLabel(self._bus.interfaces["Thermal"].profile or "")
        if self._window_visible and telemetry.cpuTemp is not None:
            text = _tr("Archer · {profile} · CPU {cpu} °C · GPU {gpu} °C").format(
                profile=profile, cpu=telemetry.cpuTemp, gpu=telemetry.gpuTemp)
        else:
            # Hidden: no telemetry is flowing, so do not show stale numbers.
            text = _tr("Archer · {profile}").format(profile=profile)
        self._icon.setToolTip(text)

    def _on_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.activated.emit()
