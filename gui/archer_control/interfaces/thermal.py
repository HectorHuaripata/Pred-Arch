"""
Thermal: platform profile, fan duty and fan curves.
"""

from archer_control.common import ControlError
from archer_control.constants import FAN_CURVE_TARGETS

class ThermalInterface:
    """Value builder and setters for io.github.archer.Control1.Thermal."""

    def _thermal_values(self, profile=None):
        """profile: pass the value when it was just read; every read of
        platform_profile is a ~13 ms WMI round trip on this hardware."""
        if profile is None:
            profile = self.hw.get_thermal_profile()
        cpu, gpu = self.hw.get_fan_speed()
        curves_state = self.hw.get_fan_curve_state() or {}
        curves = {}
        for target in FAN_CURVE_TARGETS:
            st = curves_state.get(target, {})
            pts = [(int(t), int(p)) for t, p in (st.get("points") or [])]
            curves[target] = (bool(st.get("active")), pts)
        if any(active for active, _ in curves.values()):
            mode = "curve"
        elif cpu or gpu:
            mode = "manual"
        else:
            mode = "auto"
        return {
            "Profile": str(profile),
            "ProfileChoices": list(self.hw.get_thermal_profile_choices()),
            "FanMode": mode,
            "FanSpeed": (int(cpu or 0), int(gpu or 0)),
            "FanCurves": curves,
        }


    def _m_Thermal_SetProfile(self, sender, profile):
        ok, err = self.hw.set_thermal_profile(profile)
        if not ok:
            kind = "InvalidArgument" if err and "Invalid" in err else "HardwareFailure"
            raise ControlError(kind, err or "profile write failed")
        self.hw.settings.set("thermal_profile", profile)
        self._last_profile = profile
        self.store.update(self._iface("Thermal"), self._thermal_values(profile))

    def _m_Thermal_SetFanSpeed(self, sender, cpu_percent, gpu_percent):
        for v in (cpu_percent, gpu_percent):
            if not 0 <= v <= 100:
                raise ControlError("InvalidArgument", "fan percent must be 0-100")
        self.hw.stop_fan_curve()
        if not self.hw.set_fan_speed(int(cpu_percent), int(gpu_percent)):
            raise ControlError("HardwareFailure", "fan_speed write failed")
        self.hw.settings.set("fan_speed", {"cpu": int(cpu_percent), "gpu": int(gpu_percent)})
        self.store.update(self._iface("Thermal"), self._thermal_values())

    def _m_Thermal_SetFanAuto(self, sender):
        self._m_Thermal_SetFanSpeed(sender, 0, 0)

    def _m_Thermal_SetFanCurve(self, sender, target, points):
        if target not in FAN_CURVE_TARGETS:
            raise ControlError("InvalidArgument", f"target must be one of {FAN_CURVE_TARGETS}")
        pts = [(int(t), int(p)) for t, p in points]
        if len(pts) < 2:
            raise ControlError("InvalidArgument", "a curve needs at least two points")
        if any(not 0 <= p <= 100 for _, p in pts) or any(not 0 <= t <= 120 for t, _ in pts):
            raise ControlError("InvalidArgument", "points are (temp_c 0-120, percent 0-100)")
        if pts != sorted(pts):
            raise ControlError("InvalidArgument", "points must be sorted by temperature")
        self.hw.start_fan_curve(target, [list(p) for p in pts])
        self.store.update(self._iface("Thermal"), self._thermal_values())

    def _m_Thermal_ClearFanCurve(self, sender, target):
        if target not in FAN_CURVE_TARGETS:
            raise ControlError("InvalidArgument", f"target must be one of {FAN_CURVE_TARGETS}")
        self.hw.stop_fan_curve(target)
        self.store.update(self._iface("Thermal"), self._thermal_values())

