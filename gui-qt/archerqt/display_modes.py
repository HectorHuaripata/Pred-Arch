"""
Refresh rate of the built-in panel, through KScreen (Plasma).

Session-side by design: which mode a display runs is the compositor's
business, not the root daemon's. `kscreen-doctor -j` lists outputs and
modes; `kscreen-doctor output.<name>.mode.<id>` switches. Both run
asynchronously (QProcess) so the panel never blocks. Absent kscreen-doctor
(non-Plasma desktops) the object reports available = false and the card
hides itself.
"""

import json
import logging
import shutil

from PySide6.QtCore import Property, QObject, QProcess, QProcessEnvironment, QTimer, Signal, Slot

logger = logging.getLogger("archer-qt")

KSCREEN_DOCTOR = "kscreen-doctor"
INTERNAL_PREFIXES = ("eDP", "LVDS", "DSI")
KSCREEN_TIMEOUT_MS = 8000


def _kscreen_process(parent):
    """kscreen-doctor is a Qt program: it must talk to the real compositor,
    so never let it inherit a QT_QPA_PLATFORM meant for this panel."""
    proc = QProcess(parent)
    env = QProcessEnvironment.systemEnvironment()
    env.remove("QT_QPA_PLATFORM")
    proc.setProcessEnvironment(env)
    return proc


class DisplayModes(QObject):
    """Exposed to QML as `Panel` (the daemon's own interface is `Display`)."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._available = shutil.which(KSCREEN_DOCTOR) is not None
        self._name = ""
        self._enabled = False
        self._resolution = ""
        self._rates = []          # [[hz, mode_id], …] at the current resolution
        self._current_hz = 0.0
        self._proc = None

    @Property(bool, constant=True)
    def available(self):
        """kscreen-doctor is present (Plasma)."""
        return self._available

    @Property(str, notify=changed)
    def outputName(self):
        return self._name

    @Property(bool, notify=changed)
    def panelEnabled(self):
        """False when the built-in panel is switched off (external monitor only)."""
        return self._enabled

    @Property(str, notify=changed)
    def resolution(self):
        return self._resolution

    @Property("QVariantList", notify=changed)
    def refreshRates(self):
        """Distinct refresh rates (Hz) at the current resolution, ascending."""
        return [hz for hz, _ in self._rates]

    @Property(float, notify=changed)
    def currentRefresh(self):
        return self._current_hz

    @Slot()
    def refresh(self):
        if not self._available or self._proc is not None:
            return
        self._proc = _kscreen_process(self)
        self._proc.finished.connect(self._on_listed)
        self._proc.start(KSCREEN_DOCTOR, ["-j"])
        # A hung compositor query must not leave the card empty forever.
        proc = self._proc
        QTimer.singleShot(KSCREEN_TIMEOUT_MS, lambda: proc.state() != QProcess.ProcessState.NotRunning and proc.kill())

    def _on_listed(self, exit_code, _status):
        proc, self._proc = self._proc, None
        if exit_code != 0:
            logger.warning("kscreen-doctor -j failed")
            return
        try:
            outputs = json.loads(bytes(proc.readAllStandardOutput()).decode())["outputs"]
        except (ValueError, KeyError):
            logger.warning("kscreen-doctor -j: unexpected output")
            return
        panel = next((o for o in outputs if o.get("name", "").startswith(INTERNAL_PREFIXES)), None)
        if panel is None:
            return
        self._name = panel["name"]
        self._enabled = bool(panel.get("enabled"))
        current = next((m for m in panel["modes"] if str(m["id"]) == str(panel.get("currentModeId"))), None)
        size = current["size"] if current else None
        self._resolution = f"{size['width']}×{size['height']}" if size else ""
        self._current_hz = round(float(current.get("refreshRate", 0))) if current else 0.0
        rates = {}
        for mode in panel["modes"]:
            if size and mode["size"] == size:
                hz = round(float(mode.get("refreshRate", 0)))
                rates.setdefault(hz, str(mode["id"]))
        self._rates = sorted(rates.items())
        self.changed.emit()

    @Slot(float)
    def setRefresh(self, hz):
        mode_id = dict(self._rates).get(round(float(hz)))
        if not self._available or not mode_id or not self._name:
            return
        proc = _kscreen_process(self)
        proc.finished.connect(lambda *_: self.refresh())
        proc.start(KSCREEN_DOCTOR, [f"output.{self._name}.mode.{mode_id}"])
