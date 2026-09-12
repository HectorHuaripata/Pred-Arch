"""
Power: game mode, EPP, panel/boot toggles, ACPI wake sources.
"""

from pathlib import Path

from archer_control.common import ControlError


class PowerInterface:
    """Value builder and setters for io.github.archer.Control1.Power."""

    def _power_values(self):
        epp_path = self.hw._find_epp_path()
        epp = ""
        if epp_path:
            try:
                epp = Path(epp_path).read_text().strip()
            except OSError:
                epp = ""
        sources = []
        if "usb_wake_policy" in self.hw.features:
            for s in self.hw.get_usb_wake_sources() or []:
                sources.append((str(s.get("device", "")), bool(s.get("enabled", False))))
        return {
            "GameMode": bool(self.hw.get_game_mode().get("active", False)),
            "Epp": epp,
            "LcdOverride": bool(self.hw.get_lcd_override()),
            "BootAnimationSound": bool(self.hw.get_boot_animation_sound()),
            "UsbWakeSources": sources,
        }

    def _m_Power_SetGameMode(self, sender, enabled):
        if enabled:
            self.hw.activate_game_mode()
        else:
            self.hw.deactivate_game_mode()
        self.store.update(self._iface("Power"), self._power_values())
        self.store.update(self._iface("Thermal"), self._thermal_values())

    def _m_Power_SetLcdOverride(self, sender, enabled):
        if not self.hw.set_lcd_override(bool(enabled)):
            raise ControlError("HardwareFailure", "lcd_override write failed")
        self.hw.settings.set("lcd_override", bool(enabled))
        self.store.update(self._iface("Power"), self._power_values())

    def _m_Power_SetBootAnimationSound(self, sender, enabled):
        if not self.hw.set_boot_animation_sound(bool(enabled)):
            raise ControlError("HardwareFailure", "boot_animation_sound write failed")
        self.hw.settings.set("boot_animation_sound", bool(enabled))
        self.store.update(self._iface("Power"), self._power_values())

    def _m_Power_SetUsbWake(self, sender, device, enabled):
        if not self.hw.set_usb_wake(device, bool(enabled)):
            raise ControlError("InvalidArgument", f"unknown wake device {device!r}")
        self.store.update(self._iface("Power"), self._power_values())
