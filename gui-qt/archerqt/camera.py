"""
Webcam controls through V4L2 (v4l2-ctl), generic for any UVC camera.

Session-side: the camera is a user device and its controls are plain V4L2
user controls (brightness, contrast, white balance, …). `v4l2-ctl` is run
asynchronously; the first video node that reports controls is the capture
device (metadata nodes report none). Absent v4l-utils or a camera, the
object reports available = false and the page hides its controls.
"""

import logging
import re
import shutil
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, Signal, Slot

logger = logging.getLogger("archer-qt")

V4L2_CTL = "v4l2-ctl"
VIDEO_NODES = sorted(Path("/dev").glob("video*"), key=lambda p: int(p.name[5:]))
_CONTROL_RE = re.compile(
    r"^\s*(?P<name>[a-z0-9_]+)\s+0x[0-9a-f]+\s+\((?P<type>\w+)\)\s*:\s*(?P<attrs>.*)$")
_MENU_RE = re.compile(r"^\s*(?P<index>\d+):\s*(?P<label>.+?)\s*$")
_ATTR_RE = re.compile(r"(\w+)=(-?\d+|\S+)")
SUPPORTED_TYPES = ("int", "bool", "menu")


class Camera(QObject):
    """Exposed to QML as `Camera`. `controls` is a list of dicts:
    name, label, type ("int"|"bool"|"menu"), min, max, step, default,
    value, menu ([labels] for menus), inactive (bool)."""

    controlsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._available = shutil.which(V4L2_CTL) is not None and bool(VIDEO_NODES)
        self._device = ""
        self._controls = []
        self._proc = None
        self._candidates = list(VIDEO_NODES)

    @Property(bool, constant=True)
    def available(self):
        return self._available

    @Property(str, notify=controlsChanged)
    def device(self):
        return self._device

    @Property("QVariantList", notify=controlsChanged)
    def controls(self):
        return self._controls

    @Slot()
    def refresh(self):
        """Re-read the controls (of the known device, or probe nodes in order)."""
        if not self._available or self._proc is not None:
            return
        if self._device:
            self._list(self._device)
        elif self._candidates:
            self._list(str(self._candidates.pop(0)), probing=True)

    def _list(self, device, probing=False):
        self._proc = QProcess(self)
        self._proc.finished.connect(lambda code, _s: self._on_listed(device, probing, code))
        self._proc.start(V4L2_CTL, ["-d", device, "--list-ctrls-menus"])

    def _on_listed(self, device, probing, exit_code):
        proc, self._proc = self._proc, None
        text = bytes(proc.readAllStandardOutput()).decode(errors="replace") if exit_code == 0 else ""
        controls = self._parse(text)
        if not controls:
            if probing and self._candidates:
                self._list(str(self._candidates.pop(0)), probing=True)
            return
        self._device = device
        self._controls = controls
        self.controlsChanged.emit()

    @staticmethod
    def _parse(text):
        controls, current = [], None
        for line in text.splitlines():
            m = _CONTROL_RE.match(line)
            if m:
                kind = m.group("type")
                if kind not in SUPPORTED_TYPES:
                    current = None
                    continue
                attrs = {k: v for k, v in _ATTR_RE.findall(m.group("attrs"))}
                try:
                    current = {
                        "name": m.group("name"),
                        "label": m.group("name").replace("_", " ").capitalize(),
                        "type": kind,
                        "min": int(attrs.get("min", 0)), "max": int(attrs.get("max", 1)),
                        "step": int(attrs.get("step", 1)),
                        "default": int(attrs.get("default", 0)), "value": int(attrs.get("value", 0)),
                        "menu": [], "inactive": "inactive" in attrs.get("flags", ""),
                    }
                except ValueError:
                    current = None
                    continue
                controls.append(current)
                continue
            mm = _MENU_RE.match(line)
            if mm and current is not None and current["type"] == "menu":
                current["menu"].append(mm.group("label"))
        return controls

    @Slot(str, int)
    def setControl(self, name, value):
        if not self._device:
            return
        proc = QProcess(self)
        proc.finished.connect(lambda *_: self.refresh())
        proc.start(V4L2_CTL, ["-d", self._device, f"--set-ctrl={name}={int(value)}"])

    @Slot()
    def resetDefaults(self):
        if not self._device or not self._controls:
            return
        args = ["-d", self._device] + [f"--set-ctrl={c['name']}={c['default']}" for c in self._controls]
        proc = QProcess(self)
        proc.finished.connect(lambda *_: self.refresh())
        proc.start(V4L2_CTL, args)
