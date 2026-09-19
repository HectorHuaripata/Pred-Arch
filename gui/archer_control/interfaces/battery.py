"""
Battery: charge limiter, calibration, USB charging while asleep.

Calibration is not a setting but a cycle the embedded controller runs on
its own (full discharge, then a full charge, several hours). Writing 1
starts it, writing 0 cancels it, and the firmware clears the flag itself
when the cycle ends (the driver applies the WMI calibration event). The
daemon therefore never persists it, and re-reads the flag — one WMI call —
only while a cycle is known to be running, so clients see it finish.
"""

from archer_control.common import ControlError


class BatteryInterface:
    """Value builder and setters for io.github.archer.Control1.Battery."""

    def _battery_values(self):
        usb = self.hw.get_usb_charging()
        try:
            usb = int(usb) if usb is not None else 0
        except ValueError:
            usb = 0
        return {
            "Limiter": bool(self.hw.get_battery_limiter()),
            "Calibration": bool(self.hw.get_battery_calibration()),
            "UsbCharging": usb,
        }

    def _m_Battery_SetLimiter(self, sender, enabled):
        if not self.hw.set_battery_limiter(bool(enabled)):
            raise ControlError("HardwareFailure", "battery_limiter write failed")
        self.hw.settings.set("battery_limiter", bool(enabled))
        self.store.update(self._iface("Battery"), self._battery_values())

    def _m_Battery_SetCalibration(self, sender, enabled):
        if not self.hw.set_battery_calibration(bool(enabled)):
            raise ControlError("HardwareFailure", "battery_calibration write failed")
        self.store.update(self._iface("Battery"), self._battery_values())

    def _calibration_watch(self):
        """Re-read the calibration flag while a cycle is running so the
        property drops to false when the EC finishes or aborts it."""
        if self.store.value(self._iface("Battery"), "Calibration"):
            self.store.update(self._iface("Battery"),
                              {"Calibration": bool(self.hw.get_battery_calibration())})

    def _m_Battery_SetUsbCharging(self, sender, level):
        if level not in (0, 10, 20, 30):
            raise ControlError("InvalidArgument", "level must be 0, 10, 20 or 30")
        if not self.hw.set_usb_charging(int(level)):
            raise ControlError("HardwareFailure", "usb_charging write failed")
        self.hw.settings.set("usb_charging", int(level))
        self.store.update(self._iface("Battery"), self._battery_values())
