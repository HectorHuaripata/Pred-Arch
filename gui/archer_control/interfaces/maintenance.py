"""
Maintenance: linuwu_sense module parameter, daemon and driver restarts.
"""

from pathlib import Path

from archer_control.common import ControlError
from archer_control.constants import MODPROBE_CONF, MODPROBE_PARAMS


class MaintenanceInterface:
    """Value builder and methods for io.github.archer.Control1.Maintenance."""

    @staticmethod
    def _read_modprobe():
        try:
            for line in Path(MODPROBE_CONF).read_text().splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[0] == "options" and parts[1] == "linuwu_sense":
                    return parts[2].split("=")[0]
        except OSError:
            pass
        return ""

    def _m_Maintenance_SetModprobeParameter(self, sender, parameter):
        if parameter not in MODPROBE_PARAMS:
            raise ControlError("InvalidArgument", f"parameter must be one of {MODPROBE_PARAMS}")
        if not self.hw.set_modprobe_parameter(parameter):
            raise ControlError("HardwareFailure", f"could not write {MODPROBE_CONF}")
        self.store.update(self._iface("Maintenance"), {"ModprobeParameter": self._read_modprobe()})

    def _m_Maintenance_ClearModprobeParameter(self, sender):
        if not self.hw.remove_modprobe_parameter():
            raise ControlError("HardwareFailure", f"could not remove {MODPROBE_CONF}")
        self.store.update(self._iface("Maintenance"), {"ModprobeParameter": self._read_modprobe()})

    def _m_Maintenance_RestartDaemon(self, sender):
        self.hw.restart_daemon()

    def _m_Maintenance_RestartDriversAndDaemon(self, sender):
        self.hw.restart_drivers_and_daemon()
