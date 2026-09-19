"""
Drives and filesystems, for the Overview.

Drives come from /sys/class/block (whole devices only), their temperature
from the hwmon a drive driver registers (nvme, drivetemp for SATA) matched
by the hwmon's device path. Filesystem usage is statvfs on real, local
mounts read from /proc/mounts. Everything is a sysfs/procfs read; no
subprocess, no SMART ioctls (those would need nvme-cli/smartmontools and
are left to a future Firmware/Health refresh).
"""

import os
from pathlib import Path

BLOCK_ROOT = Path("/sys/class/block")
HWMON_ROOT = Path("/sys/class/hwmon")
DRIVE_HWMON_NAMES = ("nvme", "drivetemp")
LOCAL_FS = ("btrfs", "ext4", "ext3", "xfs", "f2fs", "vfat", "exfat", "ntfs", "ntfs3", "zfs", "bcachefs")
SECTOR_BYTES = 512


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def _is_whole_disk(dev):
    return (dev / "device").exists() and not (dev / "partition").exists()


class StorageProbe:
    """Resolve drive → temperature file once; read cheaply afterwards."""

    def __init__(self):
        self.drives = []           # (name, model, size_bytes, temp_path or None)
        temp_by_device = {}
        for hwmon in HWMON_ROOT.glob("hwmon*"):
            if (_read(hwmon / "name") or "") not in DRIVE_HWMON_NAMES:
                continue
            try:
                device = (hwmon / "device").resolve()
            except OSError:
                continue
            temp = hwmon / "temp1_input"
            if temp.exists():
                temp_by_device[str(device)] = temp
        for dev in sorted(BLOCK_ROOT.iterdir()):
            if not _is_whole_disk(dev) or dev.name.startswith(("loop", "zram", "ram", "dm-", "sr")):
                continue
            try:
                size = int(_read(dev / "size") or 0) * SECTOR_BYTES
            except ValueError:
                size = 0
            model = _read(dev / "device/model") or _read(dev / "device/name") or dev.name
            temp_path = None
            try:
                device = (dev / "device").resolve()
                for known, path in temp_by_device.items():
                    if str(device).startswith(known) or known.startswith(str(device)):
                        temp_path = path
                        break
            except OSError:
                pass
            self.drives.append((dev.name, " ".join(model.split()), size, temp_path))

    def drive_readings(self):
        """[(name, model, size_bytes, temp_c or -1), …]"""
        out = []
        for name, model, size, temp_path in self.drives:
            raw = _read(temp_path) if temp_path else None
            try:
                temp = int(raw) // 1000 if raw else -1
            except ValueError:
                temp = -1
            out.append((name, model, size, temp))
        return out

    @staticmethod
    def filesystems():
        """[(mountpoint, device, fstype, size_bytes, used_bytes), …] for local
        filesystems, one entry per device (btrfs subvolumes share a device)."""
        seen = set()
        out = []
        try:
            with open("/proc/mounts") as f:
                lines = f.readlines()
        except OSError:
            return out
        for line in lines:
            parts = line.split()
            if len(parts) < 3:
                continue
            device, mountpoint, fstype = parts[0], parts[1], parts[2]
            if fstype not in LOCAL_FS or not device.startswith("/dev/") or device in seen:
                continue
            try:
                st = os.statvfs(mountpoint)
            except OSError:
                continue
            seen.add(device)
            size = st.f_blocks * st.f_frsize
            used = (st.f_blocks - st.f_bfree) * st.f_frsize
            out.append((mountpoint.replace("\\040", " "), device, fstype, size, used))
        return out
