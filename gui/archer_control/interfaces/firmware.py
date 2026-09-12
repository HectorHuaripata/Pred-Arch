"""
Firmware: BIOS version and fwupd updates (refreshed on demand).
"""

import os
import threading
import time
from pathlib import Path

from gi.repository import GLib

from archer_control.common import ControlError, logger
from archer_control.constants import DEFAULT_PATH, DMI_BIOS_VERSION


class FirmwareInterface:
    """Value builder and Refresh for io.github.archer.Control1.Firmware."""

    def _firmware_static_values(self):
        # Deliberately no fwupdmgr here: it is a 30 s subprocess and belongs
        # behind Firmware.Refresh.
        bios = Path(DMI_BIOS_VERSION)
        try:
            bios_version = bios.read_text().strip()
        except OSError:
            bios_version = "Unknown"
        fwupd = any(os.access(os.path.join(p, "fwupdmgr"), os.X_OK)
                    for p in os.environ.get("PATH", DEFAULT_PATH).split(":"))
        return {
            "BiosVersion": bios_version,
            "FwupdAvailable": fwupd,
            "Updates": [],
            "LastRefresh": 0,
        }

    @staticmethod
    def _m_Firmware_Refresh(self, sender):
        if not self.store.value(self._iface("Firmware"), "FwupdAvailable"):
            raise ControlError("Unsupported", "fwupdmgr is not installed")
        if self._firmware_busy:
            raise ControlError("Busy", "a firmware refresh is already running")
        self._firmware_busy = True

        def worker():
            updates = []
            try:
                info = self.hw.get_firmware_info() or {}
                for dev in info.get("updates", []) or []:
                    releases = dev.get("Releases") or []
                    available = str(releases[0].get("Version", "")) if releases else ""
                    updates.append((str(dev.get("Name", dev.get("DeviceId", ""))),
                                    str(dev.get("Version", "")), available))
            except Exception as e:
                logger.warning(f"Firmware.Refresh failed: {e}")
            finally:
                self._firmware_busy = False
                GLib.idle_add(lambda: (self.store.update(self._iface("Firmware"), {
                    "Updates": updates, "LastRefresh": int(time.time())}), False)[1])

        threading.Thread(target=worker, name="fwupd-refresh", daemon=True).start()
