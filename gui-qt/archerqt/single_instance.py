"""
Single-instance guard over the session bus.

The first panel owns the well-known name io.github.archer.Panel and
serves a one-method interface at /io/github/archer/Panel. A second launch
finds the name taken, asks the running instance to Activate() (show and
raise its window) and exits. This is the ordinary desktop mechanism —
the same shape as org.freedesktop.Application — done with Gio, the D-Bus
stack the panel already uses.

Why it matters for a hardware control panel: every instance would add a
telemetry subscription, a tray icon and ~70 MB, and two windows could
send contradictory commands back to back. The daemon serialises hardware
writes, so nothing can corrupt the EC, but one window is the only sane
state.
"""

import logging

from gi.repository import Gio, GLib

logger = logging.getLogger("archer-qt")

NAME = "io.github.archer.Panel"
PATH = "/io/github/archer/Panel"
IFACE = "io.github.archer.Panel"

# org.freedesktop.DBus.RequestName flags and replies
DO_NOT_QUEUE = 4
REPLY_PRIMARY_OWNER = 1
REPLY_ALREADY_OWNER = 4

INTROSPECTION = f"""
<node>
  <interface name="{IFACE}">
    <method name="Activate"/>
  </interface>
</node>
"""


class SingleInstance:
    """Call acquire() first; if it returns False, call activate_existing()
    and exit. Otherwise call serve(callback) once the window exists."""

    def __init__(self, bus_type=Gio.BusType.SESSION):
        self._conn = Gio.bus_get_sync(bus_type, None)
        self._registration = 0

    def acquire(self):
        """True when this process is now the one panel."""
        reply = self._conn.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "RequestName", GLib.Variant("(su)", (NAME, DO_NOT_QUEUE)),
            GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, 5000, None)
        return reply.unpack()[0] in (REPLY_PRIMARY_OWNER, REPLY_ALREADY_OWNER)

    def activate_existing(self):
        """Ask the running panel to show its window."""
        try:
            self._conn.call_sync(NAME, PATH, IFACE, "Activate", None, None,
                                 Gio.DBusCallFlags.NONE, 5000, None)
            logger.info("Archer is already running; activated the existing window")
        except GLib.Error as e:
            logger.warning(f"Could not activate the running instance: {e.message}")

    def serve(self, on_activate):
        """Answer Activate() with `on_activate()` on the main loop."""
        info = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION)

        def on_call(conn, sender, path, iface, method, params, invocation):
            if method == "Activate":
                on_activate()
                invocation.return_value(None)
            else:
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownMethod", method)

        self._registration = self._conn.register_object(
            PATH, info.interfaces[0], on_call, None, None)
