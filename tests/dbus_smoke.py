"""
Headless smoke test for the legacy v1 D-Bus service (io.otectus.Archer1).

The service runs in a child process against a mocked HardwareManager on
the session bus; this process is a plain client. Keeping the two in
separate processes matters: dbus-python cannot serve blocking calls to
itself over one shared connection while its main loop runs in a thread,
which is how the previous single-process version deadlocked (NoReply).

Checks: the name appears, Ping answers, the introspection XML carries the
required methods and signals, and TelemetryUpdated fires once a client is
known to the service (v1 emits only while a v1 client is on the bus).

Run under `dbus-run-session -- python3 tests/dbus_smoke.py`; no root and no
hardware needed.
"""

import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import dbus
import dbus.mainloop.glib
from gi.repository import GLib

REPO_ROOT = Path(__file__).resolve().parent.parent
GUI_DIR = REPO_ROOT / "gui"

DBUS_NAME = "io.otectus.Archer1"
DBUS_PATH = "/io/otectus/Archer1"
DBUS_IFACE = "io.otectus.Archer1"

REQUIRED_METHODS = (
    "Ping",
    "GetAllSettings",
    "GetMonitoringData",
    "GetSupportedFeatures",
    "SetThermalProfile",
    "SetAudioEnhancement",
)
REQUIRED_SIGNALS = (
    "TelemetryUpdated",
    "AudioEnhancementChanged",
    "ProfileChanged",
)

# The service process: ArcherDBusService on the session bus with a fake
# HardwareManager that returns plausible scalar telemetry.
SERVICE_SCRIPT = r"""
import sys
sys.path.insert(0, %(gui_dir)r)
import dbus, dbus.mainloop.glib
from gi.repository import GLib
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
import archer_dbus

class FakeSettings:
    def __init__(self):
        self._data = {"daemon_version": "smoke"}
    def get(self, k, default=None):
        return self._data.get(k, default)
    def set(self, k, v):
        self._data[k] = v
    @property
    def data(self):
        return dict(self._data)

class FakeHardware:
    features = ["smoke"]
    settings = FakeSettings()
    def get_monitoring_data(self):
        return {"cpu_temp": 42, "gpu_temp": 38, "battery_info": {"present": False}}
    def get_all_settings(self):
        return {"features": list(self.features), "battery_info": {"present": False}}

service = archer_dbus.ArcherDBusService(FakeHardware(), bus=dbus.SessionBus())
GLib.MainLoop().run()
"""


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def wait_for_name(bus, timeout_s=10):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if bus.name_has_owner(DBUS_NAME):
            return True
        time.sleep(0.2)
    return False


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    service = subprocess.Popen(
        [sys.executable, "-c", SERVICE_SCRIPT % {"gui_dir": str(GUI_DIR)}],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        bus = dbus.SessionBus()
        if not wait_for_name(bus):
            output = service.stdout.read() if service.poll() is not None else "(still running)"
            fail(f"{DBUS_NAME} never appeared on the bus\n{output}")
        print(f"OK: {DBUS_NAME} registered")

        proxy = bus.get_object(DBUS_NAME, DBUS_PATH)
        iface = dbus.Interface(proxy, DBUS_IFACE)

        ping_resp = str(iface.Ping(timeout=5))
        if "success" not in ping_resp:
            fail(f"Ping returned: {ping_resp!r}")
        print(f"OK: Ping -> {ping_resp}")

        introspect = dbus.Interface(proxy, "org.freedesktop.DBus.Introspectable")
        root = ET.fromstring(str(introspect.Introspect(timeout=5)))
        our_iface = [n for n in root.iter("interface") if n.attrib.get("name") == DBUS_IFACE]
        method_names = {m.attrib["name"] for n in our_iface for m in n.findall("method")}
        signal_names = {s.attrib["name"] for n in our_iface for s in n.findall("signal")}

        missing = [m for m in REQUIRED_METHODS if m not in method_names]
        if missing:
            fail(f"Missing D-Bus methods: {missing}")
        print(f"OK: methods present: {sorted(method_names)}")

        missing = [s for s in REQUIRED_SIGNALS if s not in signal_names]
        if missing:
            fail(f"Missing D-Bus signals: {missing}")
        print(f"OK: signals present: {sorted(signal_names)}")

        # Ping made us a known v1 client, so the 2 s telemetry timer must
        # now emit. Run the loop until the first signal or a 6 s timeout.
        loop = GLib.MainLoop()
        seen = []

        def on_telemetry(_payload):
            seen.append(True)
            loop.quit()

        proxy.connect_to_signal("TelemetryUpdated", on_telemetry, dbus_interface=DBUS_IFACE)
        GLib.timeout_add(6000, loop.quit)
        loop.run()
        if not seen:
            fail("TelemetryUpdated signal never fired within 6 s")
        print("OK: TelemetryUpdated fired")

        print("PASS: D-Bus smoke complete")
    finally:
        service.terminate()
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.kill()


if __name__ == "__main__":
    main()
