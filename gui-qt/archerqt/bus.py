"""
Bridge between io.github.archer.Control1 and QML.

One QObject per D-Bus interface, generated from the introspection XML at
import time: every D-Bus property becomes a Qt property (lowerCamel) with a
notify signal, so QML binds to `Telemetry.cpuTemp` and re-evaluates only
when the daemon says that value changed. Methods are reached through
`Bus.call("Thermal", "SetProfile", ["performance"])`; failures arrive on
`Bus.callFailed(iface, method, kind, message)`.

D-Bus itself is done with Gio, the same stack the daemon uses. Qt runs its
event loop on GLib on Linux, so GDBus callbacks land on the GUI thread
without any bridging.
"""

import logging
import os
import re

from gi.repository import Gio, GLib
from PySide6.QtCore import Property, QObject, Signal, Slot

from archerqt import paths

logger = logging.getLogger("archer-qt")

BUS_NAME = "io.github.archer.Control1"
OBJECT_PATH = "/io/github/archer/Control1"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
ERROR_PREFIX = BUS_NAME + ".Error."

def _lower_camel(name):
    return name[0].lower() + name[1:]


def _to_qml(value):
    """Python (from GLib.Variant.unpack) -> something QML can hold."""
    if isinstance(value, tuple):
        return [_to_qml(v) for v in value]
    if isinstance(value, list):
        return [_to_qml(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_qml(v) for k, v in value.items()}
    return value


def _split_signature(sig):
    """Top-level element signatures of a D-Bus signature string."""
    out, i = [], 0
    while i < len(sig):
        j = _complete_type_end(sig, i)
        out.append(sig[i:j])
        i = j
    return out


def _complete_type_end(sig, i):
    c = sig[i]
    if c == "a":
        return _complete_type_end(sig, i + 1)
    if c == "(":
        depth, j = 1, i + 1
        while depth:
            depth += {"(": 1, ")": -1}.get(sig[j], 0)
            j += 1
        return j
    if c == "{":
        depth, j = 1, i + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(sig[j], 0)
            j += 1
        return j
    return i + 1


def _coerce(value, sig):
    """JS/QML value -> Python shape GLib.Variant(sig, value) accepts."""
    c = sig[0]
    if c in "yiuxtnq":
        return int(round(float(value)))
    if c == "d":
        return float(value)
    if c == "b":
        return bool(value)
    if c in "sog":
        return str(value)
    if c == "(":
        parts = _split_signature(sig[1:-1])
        return tuple(_coerce(v, s) for v, s in zip(value, parts))
    if c == "a":
        inner = sig[1:]
        if inner[0] == "{":
            ksig, vsig = _split_signature(inner[1:-1])
            return {_coerce(k, ksig): _coerce(v, vsig) for k, v in dict(value).items()}
        return [_coerce(v, inner) for v in value]
    return value


def _load_node_info():
    return Gio.DBusNodeInfo.new_for_xml(paths.contract_xml().read_text())


def _make_interface_class(iface_info):
    """Build a QObject subclass with one Qt property per D-Bus property."""
    short = iface_info.name.rsplit(".", 1)[-1]
    attrs = {"__doc__": f"QML view of {iface_info.name}", "_dbus_name": iface_info.name,
             "_prop_names": {}}
    for prop in iface_info.properties:
        qname = _lower_camel(prop.name)
        attrs["_prop_names"][prop.name] = qname
        signal = Signal()
        attrs[qname + "Changed"] = signal

        def getter(self, _q=qname):
            return self._values.get(_q)

        attrs[qname] = Property("QVariant", getter, notify=signal)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._values = {}

    def apply(self, changed):
        """changed: {DBusName: python value}. Emits only what differs."""
        for dbus_name, value in changed.items():
            qname = self._prop_names.get(dbus_name)
            if qname is None:
                continue
            value = _to_qml(value)
            if self._values.get(qname) != value:
                self._values[qname] = value
                getattr(self, qname + "Changed").emit()

    attrs["__init__"] = __init__
    attrs["apply"] = apply
    return type(short + "Interface", (QObject,), attrs)


class ArcherBus(QObject):
    """Owns the GDBus connection and the per-interface objects."""

    connectedChanged = Signal()
    errorChanged = Signal()
    callFailed = Signal(str, str, str, str)      # iface, method, kind, message
    callSucceeded = Signal(str, str)             # iface, method

    def __init__(self, parent=None):
        super().__init__(parent)
        self._node = _load_node_info()
        self._connected = False
        self._error = ""
        self._telemetry_ms = 0
        self._conn = None
        self.interfaces = {}
        self._methods = {}      # (short, Method) -> in-signature
        for iface in self._node.interfaces:
            short = iface.name.rsplit(".", 1)[-1]
            self.interfaces[short] = _make_interface_class(iface)(self)
            for m in iface.methods:
                self._methods[(short, m.name)] = "".join(a.signature for a in m.in_args)

        # ARCHER_BUS=session pairs with `archer_daemon.py --session-bus`
        # for development without touching the installed daemon.
        bus_type = (Gio.BusType.SESSION if os.environ.get("ARCHER_BUS") == "session"
                    else Gio.BusType.SYSTEM)
        try:
            self._conn = Gio.bus_get_sync(bus_type, None)
        except GLib.Error as e:
            self._set_error(f"System bus unavailable: {e.message}")
            return
        self._conn.signal_subscribe(
            BUS_NAME, PROPS_IFACE, "PropertiesChanged", OBJECT_PATH, None,
            Gio.DBusSignalFlags.NONE, self._on_properties_changed)
        Gio.bus_watch_name_on_connection(
            self._conn, BUS_NAME, Gio.BusNameWatcherFlags.NONE,
            self._on_name_appeared, self._on_name_vanished)

    # -- Qt properties ---------------------------------------------------

    @Property(bool, notify=connectedChanged)
    def connected(self):
        return self._connected

    @Property(str, notify=errorChanged)
    def error(self):
        return self._error

    def _set_error(self, text):
        if text != self._error:
            self._error = text
            self.errorChanged.emit()

    # -- name watching ---------------------------------------------------

    def _on_name_appeared(self, conn, name, owner):
        logger.info(f"{name} owned by {owner}")
        self._set_error("")
        pending = list(self.interfaces.items())

        def fetch_next():
            if not pending:
                if not self._connected:
                    self._connected = True
                    self.connectedChanged.emit()
                if self._telemetry_ms:
                    self._send_subscribe(self._telemetry_ms)
                return
            short, obj = pending.pop(0)
            self._conn.call(
                BUS_NAME, OBJECT_PATH, PROPS_IFACE, "GetAll",
                GLib.Variant("(s)", (obj._dbus_name,)), None,
                Gio.DBusCallFlags.NONE, 5000, None, on_get_all, obj)

        def on_get_all(conn, result, obj):
            try:
                obj.apply(conn.call_finish(result).unpack()[0])
            except GLib.Error as e:
                logger.warning(f"GetAll {obj._dbus_name}: {e.message}")
            fetch_next()

        fetch_next()

    def _on_name_vanished(self, conn, name):
        logger.warning(f"{name} left the bus")
        if self._connected:
            self._connected = False
            self.connectedChanged.emit()
        self._set_error("Archer daemon is not running. "
                        "Check: systemctl status archer-daemon")

    def _on_properties_changed(self, conn, sender, path, iface, signal, params):
        iface_name, changed, _ = params.unpack()
        obj = self.interfaces.get(iface_name.rsplit(".", 1)[-1])
        if obj is not None:
            obj.apply(changed)

    # -- calls -----------------------------------------------------------

    @Slot(str, str, "QVariantList")
    @Slot(str, str)
    def call(self, iface, method, args=None):
        """Invoke a method. Result is reported through callSucceeded /
        callFailed; the property update is the real confirmation."""
        sig = self._methods.get((iface, method))
        if sig is None:
            self.callFailed.emit(iface, method, "InvalidArgument", f"unknown method {iface}.{method}")
            return
        if self._conn is None or not self._connected:
            self.callFailed.emit(iface, method, "Offline", "daemon offline")
            return
        args = list(args or [])
        try:
            parts = _split_signature(sig)
            payload = (GLib.Variant("(" + sig + ")",
                                    tuple(_coerce(a, s) for a, s in zip(args, parts)))
                       if parts else None)
        except (TypeError, ValueError, IndexError) as e:
            self.callFailed.emit(iface, method, "InvalidArgument", str(e))
            return

        def done(conn, result):
            try:
                conn.call_finish(result)
                self.callSucceeded.emit(iface, method)
            except GLib.Error as e:
                remote = Gio.dbus_error_get_remote_error(e) or ""
                kind = remote[len(ERROR_PREFIX):] if remote.startswith(ERROR_PREFIX) else "Error"
                message = re.sub(r"^.*?:\s*", "", e.message, count=1) if remote else e.message
                logger.warning(f"{iface}.{method} failed: {remote} {message}")
                self.callFailed.emit(iface, method, kind, message)

        # Long enough for a polkit prompt and envycontrol.
        self._conn.call(BUS_NAME, OBJECT_PATH, f"{BUS_NAME}.{iface}", method, payload,
                        None, Gio.DBusCallFlags.NONE, 180_000, None, done)

    # -- telemetry -------------------------------------------------------

    @Slot(int)
    def setTelemetryInterval(self, ms):
        """0 unsubscribes. Re-sent automatically after a daemon restart."""
        ms = int(ms)
        if ms == self._telemetry_ms:
            return
        self._telemetry_ms = ms
        if self._connected:
            self._send_subscribe(ms)

    def _send_subscribe(self, ms):
        if ms > 0:
            self.call("Telemetry", "Subscribe", [ms])
        else:
            self.call("Telemetry", "Unsubscribe")
