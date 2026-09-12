"""
PropertyStore: last-emitted value of every property and the delta emitter.
"""

from gi.repository import GLib

from archer_control.common import logger
from archer_control.constants import OBJECT_PATH, PROPS_IFACE


class PropertyStore:
    """Last-emitted value of every property, and the delta emitter.

    Samplers and setters never emit directly: they hand a dict of new values
    to update(), which compares against what clients last saw and sends one
    PropertiesChanged per interface with only the differences.
    """

    def __init__(self, conn, node_info):
        self._conn = conn
        self._sigs = {}
        self._values = {}
        for iface in node_info.interfaces:
            self._sigs[iface.name] = {p.name: p.signature for p in iface.properties}
            self._values[iface.name] = {}

    def get(self, iface, name):
        sig = self._sigs[iface][name]
        value = self._values[iface].get(name)
        if value is None:
            value = self._zero(sig)
        return GLib.Variant(sig, value)

    def get_all(self, iface):
        return {name: self.get(iface, name) for name in self._sigs[iface]}

    def value(self, iface, name, default=None):
        return self._values[iface].get(name, default)

    def seed(self, iface, values):
        """Set initial values without emitting."""
        for name, value in values.items():
            if name in self._sigs[iface]:
                self._values[iface][name] = value

    def update(self, iface, values):
        """Store new values; emit PropertiesChanged for the ones that differ."""
        changed = {}
        for name, value in values.items():
            if name not in self._sigs[iface]:
                logger.warning(f"PropertyStore: unknown {iface}.{name}")
                continue
            if self._values[iface].get(name) != value:
                self._values[iface][name] = value
                changed[name] = GLib.Variant(self._sigs[iface][name], value)
        if changed:
            try:
                self._conn.emit_signal(
                    None, OBJECT_PATH, PROPS_IFACE, "PropertiesChanged",
                    GLib.Variant("(sa{sv}as)", (iface, changed, [])),
                )
            except Exception as e:
                logger.warning(f"PropertiesChanged emit failed: {e}")
        return bool(changed)

    @staticmethod
    def _zero(sig):
        if sig == "s":
            return ""
        if sig == "b":
            return False
        if sig in ("y", "i", "u", "t"):
            return 0
        if sig == "d":
            return 0.0
        if sig.startswith("a{"):
            return {}
        if sig.startswith("a"):
            return []
        if sig == "(uu)":
            return (0, 0)
        if sig == "(yyy)":
            return (0, 0, 0)
        if sig == "(bdsi)":
            return (False, 0.0, "unknown", -1)
        return None


# ---------------------------------------------------------------------------
# Telemetry sampler
# ---------------------------------------------------------------------------

