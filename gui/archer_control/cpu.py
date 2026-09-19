"""
CPU frequency policy through cpufreq / intel_pstate sysfs.

Generic: works with any cpufreq driver that exposes the standard files;
energy-performance preference (EPP) needs intel_pstate or amd-pstate in
active mode, turbo needs intel_pstate's no_turbo or cpufreq's boost.
Hybrid topology (P-cores / E-cores) is read from /sys/devices/cpu_core and
/sys/devices/cpu_atom when present.
"""

import logging
from pathlib import Path

logger = logging.getLogger("archer-daemon")

CPU_ROOT = Path("/sys/devices/system/cpu")
INTEL_PSTATE = CPU_ROOT / "intel_pstate"
CPUFREQ_BOOST = CPU_ROOT / "cpufreq/boost"


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def _write(path, value):
    try:
        Path(path).write_text(str(value))
        return True
    except OSError as e:
        logger.warning(f"cpufreq write {path} <- {value!r}: {e}")
        return False


def _cpu_dirs():
    return sorted(CPU_ROOT.glob("cpu[0-9]*"), key=lambda p: int(p.name[3:]))


def _parse_cpu_list(text):
    """"0-7,16" -> [0..7, 16]"""
    cpus = []
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-")
            cpus.extend(range(int(lo), int(hi) + 1))
        else:
            cpus.append(int(part))
    return cpus


class CpuPolicy:
    """Reads and writes the policy that applies to every CPU."""

    def __init__(self):
        self.cpus = _cpu_dirs()
        cpu0 = self.cpus[0] / "cpufreq" if self.cpus else None
        self.driver = _read(cpu0 / "scaling_driver") if cpu0 else None
        self.epp_choices = (_read(cpu0 / "energy_performance_available_preferences") or "").split() if cpu0 else []
        self.governors = (_read(cpu0 / "scaling_available_governors") or "").split() if cpu0 else []
        self.performance_cores = _parse_cpu_list(_read("/sys/devices/cpu_core/cpus"))
        self.efficiency_cores = _parse_cpu_list(_read("/sys/devices/cpu_atom/cpus"))
        self.turbo_path = None
        if (INTEL_PSTATE / "no_turbo").exists():
            self.turbo_path = ("no_turbo", INTEL_PSTATE / "no_turbo")
        elif CPUFREQ_BOOST.exists():
            self.turbo_path = ("boost", CPUFREQ_BOOST)
        self._freq_paths = [c / "cpufreq/scaling_cur_freq" for c in self.cpus]

    # -- reads -----------------------------------------------------------

    @property
    def available(self):
        return bool(self.cpus) and self.driver is not None

    def epp(self):
        return _read(self.cpus[0] / "cpufreq/energy_performance_preference") if self.cpus else None

    def governor(self):
        return _read(self.cpus[0] / "cpufreq/scaling_governor") if self.cpus else None

    def turbo(self):
        """True when turbo/boost is allowed; None if the driver has no knob."""
        if self.turbo_path is None:
            return None
        kind, path = self.turbo_path
        raw = _read(path)
        if raw is None:
            return None
        return raw == "0" if kind == "no_turbo" else raw == "1"

    def average_mhz(self):
        """Mean scaling_cur_freq over all CPUs, in MHz. ~0.2 ms for 24 CPUs."""
        total = count = 0
        for path in self._freq_paths:
            raw = _read(path)
            if raw and raw.isdigit():
                total += int(raw)
                count += 1
        return total // count // 1000 if count else 0

    # -- writes ----------------------------------------------------------

    def set_epp(self, preference):
        if preference not in self.epp_choices:
            return False
        return all(_write(c / "cpufreq/energy_performance_preference", preference) for c in self.cpus)

    def set_governor(self, governor):
        if governor not in self.governors:
            return False
        return all(_write(c / "cpufreq/scaling_governor", governor) for c in self.cpus)

    def set_turbo(self, enabled):
        if self.turbo_path is None:
            return False
        kind, path = self.turbo_path
        value = ("0" if enabled else "1") if kind == "no_turbo" else ("1" if enabled else "0")
        return _write(path, value)
