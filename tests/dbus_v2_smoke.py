"""
Smoke test for the v2 contract (io.github.archer.Control1).

Starts `gui/archer_daemon.py --session-bus` as a child on the current
session bus (run under `dbus-run-session` in CI), then checks the parts of
docs/DBUS_V2.md that a client depends on:

  - all nine interfaces answer GetAll with the XML's property set
  - no sampling and no signals while nobody is subscribed
  - Subscribe() starts PropertiesChanged deltas at the requested cadence
  - the fastest live subscriber sets the interval; a subscriber that dies
    is dropped through NameOwnerChanged
  - Unsubscribe() stops everything again
  - invalid arguments surface as typed D-Bus errors

Reads real sysfs where present, so it also runs on a machine with no Acer
hardware (values are simply zero). No root needed.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from gi.repository import Gio, GLib

REPO_ROOT = Path(__file__).resolve().parent.parent
DAEMON = REPO_ROOT / "gui" / "archer_daemon.py"
XML = REPO_ROOT / "dbus" / "io.github.archer.Control1.xml"

NAME = "io.github.archer.Control1"
PATH = "/io/github/archer/Control1"
PROPS = "org.freedesktop.DBus.Properties"


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


class Client:
    def __init__(self):
        self.conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.events = []
        self.conn.signal_subscribe(
            NAME, PROPS, "PropertiesChanged", PATH, None,
            Gio.DBusSignalFlags.NONE, self._on_changed)
        self.loop = GLib.MainLoop()

    def _on_changed(self, conn, sender, path, iface, signal, params):
        iface_name, changed, _ = params.unpack()
        self.events.append((iface_name.rsplit(".", 1)[-1], changed))

    def spin(self, ms):
        GLib.timeout_add(ms, self.loop.quit)
        self.loop.run()

    def call(self, iface, method, args=None, sig=None):
        return self.conn.call_sync(
            NAME, PATH, f"{NAME}.{iface}", method,
            GLib.Variant(sig, args) if sig else None, None,
            Gio.DBusCallFlags.NONE, 5000, None)

    def prop(self, iface, name):
        return self.conn.call_sync(
            NAME, PATH, PROPS, "Get", GLib.Variant("(ss)", (f"{NAME}.{iface}", name)),
            None, Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]

    def get_all(self, iface):
        return self.conn.call_sync(
            NAME, PATH, PROPS, "GetAll", GLib.Variant("(s)", (f"{NAME}.{iface}",)),
            None, Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]

    def wait_for_name(self, timeout_s=10):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            owner = self.conn.call_sync(
                "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                "NameHasOwner", GLib.Variant("(s)", (NAME,)), None,
                Gio.DBusCallFlags.NONE, 1000, None).unpack()[0]
            if owner:
                return True
            time.sleep(0.2)
        return False


SUBSCRIBER_SNIPPET = f"""
from gi.repository import Gio, GLib
c = Gio.bus_get_sync(Gio.BusType.SESSION, None)
c.call_sync('{NAME}', '{PATH}', '{NAME}.Telemetry', 'Subscribe',
            GLib.Variant('(u)', (250,)), None, Gio.DBusCallFlags.NONE, 5000, None)
GLib.MainLoop().run()
"""


def main():
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", "/tmp")
    daemon = subprocess.Popen(
        [sys.executable, str(DAEMON), "--session-bus"],
        cwd=str(DAEMON.parent), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        c = Client()
        if not c.wait_for_name():
            out = daemon.stdout.read() if daemon.poll() is not None else "(still running)"
            fail(f"{NAME} never appeared on the bus\n{out}")
        print(f"OK: {NAME} registered")

        # 1. Every interface in the XML answers GetAll with exactly its properties.
        node = Gio.DBusNodeInfo.new_for_xml(XML.read_text())
        for iface in node.interfaces:
            short = iface.name.rsplit(".", 1)[-1]
            got = set(c.get_all(short))
            expected = {p.name for p in iface.properties}
            if got != expected:
                fail(f"{short}: properties {sorted(got ^ expected)} differ from XML")
        print(f"OK: {len(node.interfaces)} interfaces match the XML")

        # 2. Idle: no interval, no subscribers, no telemetry signals.
        if c.prop("Telemetry", "IntervalMs") != 0 or c.prop("Telemetry", "Subscribers") != 0:
            fail("daemon is sampling with no subscribers")
        c.spin(1200)
        if any(i == "Telemetry" for i, _ in c.events):
            fail("Telemetry PropertiesChanged emitted with no subscribers")
        print("OK: idle daemon emits nothing")

        # 3. Subscribe(500) -> IntervalMs 500, deltas arrive.
        c.events.clear()
        c.call("Telemetry", "Subscribe", (500,), "(u)")
        c.spin(100)
        if c.prop("Telemetry", "IntervalMs") != 500:
            fail(f"IntervalMs after Subscribe(500) = {c.prop('Telemetry', 'IntervalMs')}")
        c.spin(1800)
        tel = [ch for i, ch in c.events if i == "Telemetry"]
        if not tel:
            fail("no Telemetry PropertiesChanged within 1.8 s of subscribing")
        for ch in tel:
            if not ch:
                fail("empty PropertiesChanged emitted")
        print(f"OK: {len(tel)} Telemetry deltas after Subscribe(500)")

        # 4. A faster second subscriber wins; when it dies it is dropped.
        sub2 = subprocess.Popen([sys.executable, "-c", SUBSCRIBER_SNIPPET])
        try:
            c.spin(700)
            if c.prop("Telemetry", "IntervalMs") != 250 or c.prop("Telemetry", "Subscribers") != 2:
                fail("second subscriber at 250 ms did not take effect")
        finally:
            sub2.kill()
            sub2.wait()
        c.spin(800)
        if c.prop("Telemetry", "IntervalMs") != 500 or c.prop("Telemetry", "Subscribers") != 1:
            fail("dead subscriber was not dropped via NameOwnerChanged")
        print("OK: fastest subscriber wins, dead subscriber dropped")

        # 5. Unsubscribe -> idle again.
        c.call("Telemetry", "Unsubscribe")
        c.spin(200)
        if c.prop("Telemetry", "IntervalMs") != 0 or c.prop("Telemetry", "Subscribers") != 0:
            fail("Unsubscribe did not stop sampling")
        c.events.clear()
        c.spin(1200)
        if any(i == "Telemetry" for i, _ in c.events):
            fail("Telemetry still emitting after Unsubscribe")
        print("OK: Unsubscribe stops sampling")

        # 6. Typed errors. Profile validity depends on the host; the USB level
        #    and direction checks are pure argument validation.
        for iface, method, args, sig, expected in (
            ("Battery", "SetUsbCharging", (15,), "(u)", ("InvalidArgument", "Unsupported")),
            ("Lighting", "SetEffect", ("Wave", 100, (0, 0, 255), 5, "up"), "(sy(yyy)ys)",
             ("InvalidArgument", "Unsupported")),
            ("Thermal", "SetFanCurve", ("cpu", [(90, 50), (40, 20)]), "(sa(uu))",
             ("InvalidArgument", "Unsupported")),
        ):
            try:
                c.call(iface, method, args, sig)
                fail(f"{iface}.{method} accepted an invalid argument")
            except GLib.Error as e:
                remote = Gio.dbus_error_get_remote_error(e) or ""
                kind = remote.rsplit(".", 1)[-1]
                if kind not in expected:
                    fail(f"{iface}.{method}: got {remote!r}, expected one of {expected}")
        print("OK: invalid arguments raise typed errors")

        print("PASS: v2 contract smoke complete")
    finally:
        daemon.terminate()
        try:
            daemon.wait(timeout=5)
        except subprocess.TimeoutExpired:
            daemon.kill()


if __name__ == "__main__":
    main()
