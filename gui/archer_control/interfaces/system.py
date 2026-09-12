"""
System: static facts about the machine and the daemon.
"""


class SystemInterface:
    """Value builder and Ping for io.github.archer.Control1.System."""

    def _system_values(self):
        info = self.hw.get_system_info() or {}
        return {
            "Version": str(info.get("daemon_version", "")),
            "Features": list(self.hw.features),
            "Vendor": str(info.get("vendor", "")),
            "ProductName": str(info.get("product_name", "")),
            "LaptopType": str(self.hw.laptop_type),
            "Driver": "linuwu_sense" if self.hw.driver_base else "none",
            "DriverVersion": str(info.get("driver_version", "")),
            "Kernel": str(info.get("kernel", "")),
            "CpuModel": str(info.get("cpu_model", "")),
            "GpuModel": str(info.get("gpu_model", "")),
            "EneReady": bool(getattr(self.hw, "ene_ready", False)),
        }

    def _m_System_Ping(self, sender):
        return None
