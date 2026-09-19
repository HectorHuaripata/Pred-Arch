"""
Storage: drives with temperature, local filesystems with usage.
"""


class StorageInterface:
    """Value builder for io.github.archer.Control1.Storage (no methods)."""

    def _storage_values(self):
        probe = getattr(self, "_storage", None)
        if probe is None:
            return {"Drives": [], "Filesystems": []}
        return {
            "Drives": [(n, m, int(s), int(t)) for n, m, s, t in probe.drive_readings()],
            "Filesystems": [(mp, dev, fs, int(sz), int(used)) for mp, dev, fs, sz, used in probe.filesystems()],
        }

    def _storage_refresh(self):
        self.store.update(self._iface("Storage"), self._storage_values())
