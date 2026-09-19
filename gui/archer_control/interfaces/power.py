"""
Power: game mode, EPP, panel/boot toggles, ACPI wake sources.
"""

import os
import subprocess
from pathlib import Path

from gi.repository import GLib

from archer_control.common import ControlError, logger
from archer_control.constants import EPP_REAPPLY_DELAY_MS, NVIDIA_POWERD_BIN, NVIDIA_POWERD_UNIT

EPP_SETTINGS_KEY = "epp_by_profile"
CPU_SETTINGS_KEY = "cpu_policy"
SYSTEMCTL_TIMEOUT_S = 15


class PowerInterface:
    """Value builder and setters for io.github.archer.Control1.Power."""

    # -- CPU policy: detection, restore, per-profile EPP ------------------

    def _init_cpu_policy(self):
        """Advertise what the cpufreq driver offers and reapply saved
        turbo/governor. Per-profile EPP is applied by _apply_epp_for_profile
        once the profile is known."""
        cpu = getattr(self, "_cpu", None)
        if cpu is None or not cpu.available:
            return
        if cpu.epp_choices and "cpu_epp" not in self.hw.features:
            self.hw.features.append("cpu_epp")
        if cpu.turbo() is not None and "cpu_turbo" not in self.hw.features:
            self.hw.features.append("cpu_turbo")
        if len(cpu.governors) > 1 and "cpu_governor" not in self.hw.features:
            self.hw.features.append("cpu_governor")
        if os.path.exists(NVIDIA_POWERD_BIN) and "nvidia_dynamic_boost" not in self.hw.features:
            self.hw.features.append("nvidia_dynamic_boost")
        saved = self.hw.settings.get(CPU_SETTINGS_KEY) or {}
        if "turbo" in saved and cpu.turbo() is not None:
            cpu.set_turbo(bool(saved["turbo"]))
        if saved.get("governor") in cpu.governors:
            cpu.set_governor(saved["governor"])

    def _apply_epp_for_profile(self, profile, delayed=True):
        """Reapply the user's EPP for `profile`, if any, after PPD had its say."""
        cpu = getattr(self, "_cpu", None)
        if cpu is None:
            return
        preference = (self.hw.settings.get(EPP_SETTINGS_KEY) or {}).get(profile)
        if not preference:
            return

        def apply():
            if cpu.set_epp(preference):
                logger.info(f"EPP {preference} applied for profile {profile}")
            self.store.update(self._iface("Power"), self._power_values())
            return False

        if delayed:
            GLib.timeout_add(EPP_REAPPLY_DELAY_MS, apply)
        else:
            apply()

    @staticmethod
    def _dynamic_boost_enabled():
        try:
            result = subprocess.run(["systemctl", "is-enabled", NVIDIA_POWERD_UNIT],
                                    capture_output=True, text=True, timeout=SYSTEMCTL_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.stdout.strip() == "enabled"

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
        cpu = getattr(self, "_cpu", None)
        turbo = cpu.turbo() if cpu else None
        return {
            "GameMode": bool(self.hw.get_game_mode().get("active", False)),
            "Epp": epp,
            "EppChoices": list(cpu.epp_choices) if cpu else [],
            "EppByProfile": dict(self.hw.settings.get(EPP_SETTINGS_KEY) or {}),
            "TurboAvailable": turbo is not None,
            "Turbo": bool(turbo),
            "CpuGovernor": (cpu.governor() or "") if cpu else "",
            "CpuGovernors": list(cpu.governors) if cpu else [],
            "CpuTopology": (len(cpu.performance_cores), len(cpu.efficiency_cores)) if cpu else (0, 0),
            "DynamicBoostAvailable": os.path.exists(NVIDIA_POWERD_BIN),
            "DynamicBoost": os.path.exists(NVIDIA_POWERD_BIN) and self._dynamic_boost_enabled(),
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

    # -- CPU policy setters ---------------------------------------------------

    def _m_Power_SetEpp(self, sender, preference):
        cpu = self._cpu
        if preference not in cpu.epp_choices:
            raise ControlError("InvalidArgument", f"preference must be one of {cpu.epp_choices}")
        if not cpu.set_epp(preference):
            raise ControlError("HardwareFailure", "energy_performance_preference write failed")
        by_profile = dict(self.hw.settings.get(EPP_SETTINGS_KEY) or {})
        by_profile[self.hw.get_thermal_profile()] = preference
        self.hw.settings.set(EPP_SETTINGS_KEY, by_profile)
        self.store.update(self._iface("Power"), self._power_values())

    def _m_Power_ClearEppOverride(self, sender, profile):
        by_profile = dict(self.hw.settings.get(EPP_SETTINGS_KEY) or {})
        by_profile.pop(profile, None)
        self.hw.settings.set(EPP_SETTINGS_KEY, by_profile)
        self.store.update(self._iface("Power"), self._power_values())

    def _m_Power_SetTurbo(self, sender, enabled):
        if not self._cpu.set_turbo(bool(enabled)):
            raise ControlError("HardwareFailure", "turbo knob write failed")
        saved = dict(self.hw.settings.get(CPU_SETTINGS_KEY) or {})
        saved["turbo"] = bool(enabled)
        self.hw.settings.set(CPU_SETTINGS_KEY, saved)
        self.store.update(self._iface("Power"), self._power_values())

    def _m_Power_SetCpuGovernor(self, sender, governor):
        cpu = self._cpu
        if governor not in cpu.governors:
            raise ControlError("InvalidArgument", f"governor must be one of {cpu.governors}")
        if not cpu.set_governor(governor):
            raise ControlError("HardwareFailure", "scaling_governor write failed")
        saved = dict(self.hw.settings.get(CPU_SETTINGS_KEY) or {})
        saved["governor"] = governor
        self.hw.settings.set(CPU_SETTINGS_KEY, saved)
        self.store.update(self._iface("Power"), self._power_values())

    def _m_Power_SetDynamicBoost(self, sender, enabled):
        action = "enable" if enabled else "disable"
        try:
            result = subprocess.run(["systemctl", action, "--now", NVIDIA_POWERD_UNIT],
                                    capture_output=True, text=True, timeout=SYSTEMCTL_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ControlError("HardwareFailure", f"systemctl {action} {NVIDIA_POWERD_UNIT}: {e}")
        if result.returncode != 0:
            raise ControlError("HardwareFailure", result.stderr.strip() or f"systemctl {action} failed")
        self.store.update(self._iface("Power"), self._power_values())
