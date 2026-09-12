"""
Archer daemon — D-Bus contract v2, io.github.archer.Control1.

Serves the interfaces described in dbus/io.github.archer.Control1.xml on top
of the existing HardwareManager. Everything the daemon knows is a typed,
read-only property; changes go out as org.freedesktop.DBus.Properties
.PropertiesChanged carrying only the values that differ from the last
emission. Setters are methods so polkit can be run against the caller.

This module uses GDBus (Gio) rather than dbus-python: the v1 service keeps
its own connection and the two coexist in one process during the migration
(see docs/DBUS_V2.md, "Compatibility").
"""

import ctypes
import logging
import os
import threading
import time
from pathlib import Path

from gi.repository import Gio, GLib

logger = logging.getLogger("archer-daemon")

BUS_NAME = "io.github.archer.Control1"
OBJECT_PATH = "/io/github/archer/Control1"
ERROR_PREFIX = BUS_NAME + ".Error."
PROPS_IFACE = "org.freedesktop.DBus.Properties"

XML_NAME = "io.github.archer.Control1.xml"
# The introspection XML is looked up next to this file (installed layout)
# and in ../dbus (repository layout).
XML_CANDIDATES = (
    Path(__file__).resolve().parent / XML_NAME,
    Path(__file__).resolve().parent.parent / "dbus" / XML_NAME,
)

# Sampling bounds for Telemetry.Subscribe, in ms.
INTERVAL_MIN_MS = 250
INTERVAL_MAX_MS = 5000
# Battery does not move faster than this, whatever the subscriber asked for.
BATTERY_PERIOD_S = 10
# platform_profile changes are delivered by the kernel through sysfs_notify
# (POLLPRI on the file): the core notifies on every store, and linuwu_sense
# calls platform_profile_notify() from the hardware-button handler. Reading
# the attribute costs ~13 ms of CPU on this platform (the ACPI interpreter
# runs the WMI method), so it is read only when notified, plus a slow
# safety poll that also refreshes ENE readiness and fan-curve state.
PLATFORM_PROFILE_PATH = "/sys/firmware/acpi/platform_profile"
SLOW_POLL_S = 30
# Lighting setters coalesce bursts (a slider drag) into one write per device
# every this many ms. The ENE tolerates 20 Hz comfortably.
LIGHTING_FLUSH_MS = 50

NOISE_CONF = "/etc/pipewire/filter-chain.conf.d/archer-noise-suppress.conf"
MODPROBE_CONF = "/etc/modprobe.d/linuwu-sense.conf"
MODPROBE_PARAMS = ("nitro_v4", "predator_v4", "enable_all")
FAN_CURVE_TARGETS = ("cpu", "gpu")

# Effect names for the sysfs/WMI four_zone_mode fallback, indexed by the
# driver's mode number. The ENE backend supplies its own verified list.
WMI_EFFECTS = ("Static", "Breathing", "Neon", "Wave", "Shifting", "Zoom")

# Archer's direction convention on the wire: 1 = right to left, 2 = left to
# right. The contract uses words.
DIRECTION_TO_WIRE = {"left": 1, "right": 2}
WIRE_TO_DIRECTION = {1: "left", 2: "right"}

# "Interface.Method" -> polkit action. Same ids as v1 so the installed
# policy file keeps working. Methods not listed need no authorization.
POLKIT_ACTIONS = {
    "Thermal.SetProfile": "io.otectus.archer1.set-profile",
    "Thermal.SetFanSpeed": "io.otectus.archer1.set-fan",
    "Thermal.SetFanAuto": "io.otectus.archer1.set-fan",
    "Thermal.SetFanCurve": "io.otectus.archer1.set-fan",
    "Thermal.ClearFanCurve": "io.otectus.archer1.set-fan",
    "Battery.SetLimiter": "io.otectus.archer1.set-hardware",
    "Battery.SetCalibration": "io.otectus.archer1.set-hardware",
    "Battery.SetUsbCharging": "io.otectus.archer1.set-hardware",
    "Lighting.SetZones": "io.otectus.archer1.set-hardware",
    "Lighting.SetZoneMask": "io.otectus.archer1.set-hardware",
    "Lighting.SetBrightness": "io.otectus.archer1.set-hardware",
    "Lighting.SetEffect": "io.otectus.archer1.set-hardware",
    "Lighting.SetOff": "io.otectus.archer1.set-hardware",
    "Lighting.SetButtonFollowsProfile": "io.otectus.archer1.set-hardware",
    "Lighting.SetButtonColor": "io.otectus.archer1.set-hardware",
    "Lighting.SetLogo": "io.otectus.archer1.set-hardware",
    "Lighting.SetBacklightTimeout": "io.otectus.archer1.set-hardware",
    "Display.SetMode": "io.otectus.archer1.set-display",
    "Power.SetGameMode": "io.otectus.archer1.set-gamemode",
    "Power.SetLcdOverride": "io.otectus.archer1.set-hardware",
    "Power.SetBootAnimationSound": "io.otectus.archer1.set-hardware",
    "Power.SetUsbWake": "io.otectus.archer1.set-hardware",
    "Audio.SetNoiseSuppression": "io.otectus.archer1.set-hardware",
    "Maintenance.SetModprobeParameter": "io.otectus.archer1.system-control",
    "Maintenance.ClearModprobeParameter": "io.otectus.archer1.system-control",
    "Maintenance.RestartDaemon": "io.otectus.archer1.system-control",
    "Maintenance.RestartDriversAndDaemon": "io.otectus.archer1.system-control",
}

# "Interface.Method" -> any-of feature names. Checked before polkit so a
# machine without the feature never shows an auth prompt for it.
FEATURE_GATES = {
    "Thermal.SetProfile": ("thermal_profiles",),
    "Thermal.SetFanSpeed": ("fan_control", "fan_speed"),
    "Thermal.SetFanAuto": ("fan_control", "fan_speed"),
    "Thermal.SetFanCurve": ("fan_control", "fan_speed"),
    "Thermal.ClearFanCurve": ("fan_control", "fan_speed"),
    "Battery.SetLimiter": ("battery_limiter",),
    "Battery.SetCalibration": ("battery_calibration",),
    "Battery.SetUsbCharging": ("usb_charging",),
    "Lighting.SetZones": ("keyboard_per_zone",),
    "Lighting.SetZoneMask": ("keyboard_per_zone",),
    "Lighting.SetBrightness": ("keyboard_per_zone", "keyboard_effects"),
    "Lighting.SetEffect": ("keyboard_effects",),
    "Lighting.SetOff": ("keyboard_per_zone", "keyboard_effects"),
    "Lighting.SetButtonFollowsProfile": ("ene_ready",),
    "Lighting.SetButtonColor": ("ene_ready",),
    "Lighting.SetLogo": ("ene_ready",),
    "Lighting.SetBacklightTimeout": ("backlight_timeout",),
    "Display.SetMode": ("display_mode",),
    "Power.SetGameMode": ("game_mode",),
    "Power.SetLcdOverride": ("lcd_override",),
    "Power.SetBootAnimationSound": ("boot_animation_sound",),
    "Power.SetUsbWake": ("usb_wake_policy",),
}


class ControlError(Exception):
    """A typed D-Bus error. `kind` is the suffix after ERROR_PREFIX."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.name = ERROR_PREFIX + kind


def _load_node_info(xml_path=None):
    candidates = [Path(xml_path)] if xml_path else XML_CANDIDATES
    for path in candidates:
        if path.is_file():
            return Gio.DBusNodeInfo.new_for_xml(path.read_text())
    raise FileNotFoundError(
        f"{XML_NAME} not found in {[str(p) for p in candidates]}")


def _hex_to_rgb(value):
    v = str(value).lstrip("#")
    if len(v) != 6:
        return (0, 0, 0)
    try:
        return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))
    except ValueError:
        return (0, 0, 0)


def _rgb_to_hex(rgb):
    r, g, b = rgb
    return f"{r:02x}{g:02x}{b:02x}"


def _byte(value, name):
    if not 0 <= int(value) <= 255:
        raise ControlError("InvalidArgument", f"{name} must be 0-255")
    return int(value)


# ---------------------------------------------------------------------------
# Property store
# ---------------------------------------------------------------------------

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

class TelemetrySampler:
    """Reads the hot-path sensors only while someone is subscribed.

    Subscriptions are keyed by the caller's unique bus name and dropped when
    that name leaves the bus, so a crashed client cannot keep the daemon
    sampling. The effective interval is the fastest one requested.
    """

    IFACE = BUS_NAME + ".Telemetry"

    def __init__(self, hw, store, conn):
        self.hw = hw
        self.store = store
        self._conn = conn
        self._subs = {}        # sender -> (interval_ms, watch_id)
        self._timer = 0
        self._interval = 0
        self._last_battery = 0.0
        self._extra_listeners = []   # callables(interval_ms) for the v1 shim

    # -- public --------------------------------------------------------

    def subscribe(self, sender, interval_ms):
        interval = max(INTERVAL_MIN_MS, min(INTERVAL_MAX_MS, int(interval_ms)))
        if sender in self._subs:
            _, watch_id = self._subs[sender]
        else:
            watch_id = Gio.bus_watch_name_on_connection(
                self._conn, sender, Gio.BusNameWatcherFlags.NONE,
                None, self._on_vanished)
        self._subs[sender] = (interval, watch_id)
        self._reschedule()

    def unsubscribe(self, sender):
        entry = self._subs.pop(sender, None)
        if entry:
            Gio.bus_unwatch_name(entry[1])
            self._reschedule()

    @property
    def interval_ms(self):
        return self._interval

    def sample_now(self):
        """One synchronous sample, used to seed properties at startup."""
        self._tick(force_battery=True)

    # -- internals -----------------------------------------------------

    def _on_vanished(self, conn, name):
        if name in self._subs:
            logger.info(f"Telemetry subscriber {name} left the bus")
            self.unsubscribe(name)

    def _reschedule(self):
        interval = min((i for i, _ in self._subs.values()), default=0)
        if interval != self._interval:
            if self._timer:
                GLib.source_remove(self._timer)
                self._timer = 0
            self._interval = interval
            if interval:
                self._timer = GLib.timeout_add(interval, self._tick)
                # First reading right away so a fresh client is not left
                # looking at stale values for a whole interval.
                GLib.idle_add(lambda: (self._tick(force_battery=True), False)[1])
        self.store.update(self.IFACE, {
            "IntervalMs": self._interval,
            "Subscribers": len(self._subs),
        })

    def _tick(self, force_battery=False):
        try:
            cpu_rpm, gpu_rpm = self.hw.get_fan_rpm()
            values = {
                "CpuTemp": int(self.hw.get_cpu_temp()),
                "GpuTemp": int(self.hw.get_gpu_temp()),
                "CpuUsage": max(0, min(100, int(self.hw.get_cpu_usage()))),
                "GpuUsage": max(0, min(100, int(self.hw.get_gpu_usage()))),
                "FanRpm": (int(cpu_rpm or 0), int(gpu_rpm or 0)),
                "PowerSourceAc": bool(self.hw.get_power_source()),
            }
            now = time.monotonic()
            if force_battery or now - self._last_battery >= BATTERY_PERIOD_S:
                self._last_battery = now
                values["Battery"] = self._battery()
            self.store.update(self.IFACE, values)
        except Exception as e:
            # A transient sysfs hiccup must not kill the timer.
            logger.warning(f"Telemetry sample failed: {e}")
        return True

    def _battery(self):
        info = self.hw.get_battery_info() or {}
        if not info.get("present"):
            return (False, 0.0, "unknown", -1)
        status = str(info.get("status", "unknown")).lower()
        if status == "not charging":
            status = "idle"         # plugged in, limiter or full threshold holding
        elif status not in ("charging", "discharging", "full"):
            status = "unknown"
        seconds = info.get("seconds_remaining")
        return (
            True,
            float(info.get("percentage", 0)),
            status,
            int(seconds) if seconds is not None else -1,
        )


# ---------------------------------------------------------------------------
# Lighting coalescer
# ---------------------------------------------------------------------------

class LightingCoalescer:
    """Last-state-wins write scheduler, one slot per LED device.

    The first request in a quiet period is written immediately and its
    error, if any, is returned to the caller. Requests arriving inside the
    following LIGHTING_FLUSH_MS window replace each other and the newest is
    written when the window closes; failures there are logged, and the
    property (which only updates on a successful write) is the client's
    confirmation.
    """

    def __init__(self):
        self._pending = {}    # device -> callable
        self._timer = 0

    def request(self, device, write_fn):
        if self._timer:
            self._pending[device] = write_fn
            return
        write_fn()            # may raise; caller reports
        self._timer = GLib.timeout_add(LIGHTING_FLUSH_MS, self._flush)

    def _flush(self):
        pending, self._pending = self._pending, {}
        for device, fn in pending.items():
            try:
                fn()
            except Exception as e:
                logger.warning(f"Coalesced lighting write for {device} failed: {e}")
        if self._pending:
            # New requests arrived while flushing; keep the window open.
            return True
        self._timer = 0
        return False


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------

class ArcherControl:
    """Registers the v2 object and routes calls to HardwareManager."""

    def __init__(self, hw, bus_type=Gio.BusType.SYSTEM, xml_path=None,
                 ene_module=None):
        self.hw = hw
        self.ene = ene_module
        self._bus_type = bus_type
        self._conn = Gio.bus_get_sync(bus_type, None)
        self._node = _load_node_info(xml_path)
        self.store = PropertyStore(self._conn, self._node)
        self.telemetry = TelemetrySampler(hw, self.store, self._conn)
        self._lighting = LightingCoalescer()
        self._display_busy = False
        self._firmware_busy = False
        self._reg_ids = []
        self._last_profile = None

        for iface in self._node.interfaces:
            reg = self._conn.register_object(
                OBJECT_PATH, iface, self._on_method_call,
                self._on_get_property, None)
            self._reg_ids.append(reg)

        self._seed_all()
        self._profile_fd = None
        self._profile_watch = 0
        self._watch_profile_notify()
        self._owner_id = Gio.bus_own_name_on_connection(
            self._conn, BUS_NAME, Gio.BusNameOwnerFlags.NONE,
            lambda c, n: logger.info(f"D-Bus service registered ({n})"),
            lambda c, n: logger.error(f"Lost or could not acquire bus name {n}"),
        )
        GLib.timeout_add_seconds(SLOW_POLL_S, self._watch_slow_state)

    def stop(self):
        if self._profile_watch:
            GLib.source_remove(self._profile_watch)
            self._profile_watch = 0
        if self._profile_fd is not None:
            os.close(self._profile_fd)
            self._profile_fd = None
        if self._owner_id:
            Gio.bus_unown_name(self._owner_id)
            self._owner_id = 0
        for reg in self._reg_ids:
            self._conn.unregister_object(reg)
        self._reg_ids = []

    # -- helpers -------------------------------------------------------

    def _iface(self, short):
        return f"{BUS_NAME}.{short}"

    def _has_feature(self, names):
        feats = set(self.hw.features)
        if getattr(self.hw, "ene_ready", False):
            feats.add("ene_ready")
        return any(n in feats for n in names)

    def _ene(self):
        return self.ene if getattr(self.hw, "ene_ready", False) else None

    # -- GDBus callbacks ----------------------------------------------

    def _on_get_property(self, conn, sender, path, iface, name):
        try:
            return self.store.get(iface, name)
        except KeyError:
            return None

    def _on_method_call(self, conn, sender, path, iface, method, params,
                        invocation):
        short = iface[len(BUS_NAME) + 1:]
        key = f"{short}.{method}"
        handler = getattr(self, f"_m_{short}_{method}", None)
        if handler is None:
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.UnknownMethod", key)
            return

        gate = FEATURE_GATES.get(key)
        if gate and not self._has_feature(gate):
            invocation.return_dbus_error(
                ERROR_PREFIX + "Unsupported",
                f"{key} is not available on this machine (needs {'/'.join(gate)})")
            return

        action = POLKIT_ACTIONS.get(key)
        if action is None or self._bus_type != Gio.BusType.SYSTEM:
            if action is not None:
                logger.warning(f"{key}: polkit skipped, not on the system bus")
            self._run(handler, sender, params, invocation)
            return

        self._authorize(sender, action,
                        lambda ok: self._run(handler, sender, params, invocation)
                        if ok else invocation.return_dbus_error(
                            ERROR_PREFIX + "NotAuthorized",
                            f"polkit denied {action}"))

    def _run(self, handler, sender, params, invocation):
        try:
            handler(sender, *params.unpack())
            invocation.return_value(None)
        except ControlError as e:
            invocation.return_dbus_error(e.name, str(e))
        except Exception as e:
            logger.exception("v2 method failed")
            invocation.return_dbus_error(ERROR_PREFIX + "HardwareFailure", str(e))

    def _authorize(self, sender, action, done):
        """Asynchronous polkit check; the main loop stays alive while the
        agent prompts, so telemetry keeps flowing during a password dialog."""
        subject = ("system-bus-name", {"name": GLib.Variant("s", sender)})
        args = GLib.Variant("((sa{sv})sa{ss}us)",
                            (subject, action, {}, 1, ""))  # 1 = AllowUserInteraction

        def _cb(conn, result):
            try:
                reply = conn.call_finish(result)
                ok = bool(reply.unpack()[0][0])
            except Exception as e:
                logger.warning(f"polkit check for {action} failed: {e}")
                ok = False
            if not ok:
                logger.warning(f"Polkit denied {action} for {sender}")
            done(ok)

        self._conn.call(
            "org.freedesktop.PolicyKit1", "/org/freedesktop/PolicyKit1/Authority",
            "org.freedesktop.PolicyKit1.Authority", "CheckAuthorization",
            args, GLib.VariantType("((bba{ss}))"), Gio.DBusCallFlags.NONE,
            120_000, None, _cb)

    # -- seeding and slow-state watching ------------------------------

    def _seed_all(self):
        s = self.store
        s.seed(self._iface("System"), self._system_values())
        s.seed(self._iface("Thermal"), self._thermal_values())
        s.seed(self._iface("Battery"), self._battery_values())
        s.seed(self._iface("Lighting"), self._lighting_values())
        s.seed(self._iface("Display"), self._display_values())
        s.seed(self._iface("Power"), self._power_values())
        s.seed(self._iface("Audio"), {"NoiseSuppression": os.path.exists(NOISE_CONF)})
        s.seed(self._iface("Firmware"), self._firmware_static_values())
        s.seed(self._iface("Maintenance"), {"ModprobeParameter": self._read_modprobe()})
        self.telemetry.sample_now()
        self._last_profile = s.value(self._iface("Thermal"), "Profile")

    def _watch_profile_notify(self):
        """Arm a POLLPRI watch on platform_profile. Zero cost until the
        kernel signals a change, whoever wrote it."""
        if not os.path.exists(PLATFORM_PROFILE_PATH):
            return
        try:
            self._profile_fd = os.open(PLATFORM_PROFILE_PATH, os.O_RDONLY)
            # A sysfs attribute must be read once before poll() reports
            # changes, and re-read after each event to re-arm it.
            os.read(self._profile_fd, 64)
            channel = GLib.IOChannel.unix_new(self._profile_fd)
            self._profile_watch = GLib.io_add_watch(
                channel, GLib.PRIORITY_DEFAULT,
                GLib.IOCondition.PRI | GLib.IOCondition.ERR,
                self._on_profile_notify)
            logger.info("Watching platform_profile through sysfs_notify")
        except OSError as e:
            logger.warning(f"platform_profile notify watch unavailable: {e}")
            if self._profile_fd is not None:
                os.close(self._profile_fd)
                self._profile_fd = None

    def _on_profile_notify(self, channel, condition):
        try:
            os.lseek(self._profile_fd, 0, os.SEEK_SET)
            profile = os.read(self._profile_fd, 64).decode(errors="replace").strip()
        except OSError as e:
            logger.warning(f"platform_profile read after notify failed: {e}")
            return True
        self._on_profile_value(profile)
        return True

    def _on_profile_value(self, profile):
        if profile and profile != self._last_profile:
            self._last_profile = profile
            # Keeps the button LED in step; a no-op without the ENE.
            self.hw.poll_profile_led()
            logger.info(f"platform_profile is now {profile}")
        self.store.update(self._iface("Thermal"), self._thermal_values(profile))

    def _watch_slow_state(self):
        """Every SLOW_POLL_S: ENE readiness, fan-curve state, and one
        profile read as a safety net for the notify watch. One WMI read."""
        try:
            self._on_profile_value(self.hw.get_thermal_profile())
            self.store.update(self._iface("System"), {
                "EneReady": bool(getattr(self.hw, "ene_ready", False)),
                "Features": list(self.hw.features),
            })
            self.store.update(self._iface("Lighting"), {"Backend": self._backend()})
        except Exception as e:
            logger.warning(f"slow-state watch failed: {e}")
        return True

    # -- value builders -----------------------------------------------

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

    def _battery_values(self):
        usb = self.hw.get_usb_charging()
        try:
            usb = int(usb) if usb is not None else 0
        except ValueError:
            usb = 0
        return {
            "Limiter": bool(self.hw.get_battery_limiter()),
            "Calibration": bool(self.hw.get_battery_calibration()),
            "UsbCharging": usb,
        }

    def _backend(self):
        if getattr(self.hw, "ene_ready", False):
            return "ene"
        if "keyboard_per_zone" in self.hw.features or "keyboard_effects" in self.hw.features:
            return "wmi"
        return "none"

    def _effect_names(self):
        if self.ene is not None and hasattr(self.ene, "EFFECTS"):
            return [name for name, _ in self.ene.EFFECTS]
        return list(WMI_EFFECTS)

    def _lighting_values(self):
        st = self.hw.settings
        pz = st.get("per_zone_mode") or {}
        fx = st.get("four_zone_mode") or {}
        names = self._effect_names()
        last = st.get("last_keyboard_mode")
        if last == "off":
            effect = "off"
        elif last == "effect":
            idx = int(fx.get("mode", 0))
            effect = names[idx] if 0 <= idx < len(names) else "static"
        else:
            effect = "static"
        brightness = int((fx if last == "effect" else pz).get("brightness", pz.get("brightness", 100)))
        zones = [_hex_to_rgb(pz.get(f"zone{i}", "ffffff")) for i in range(1, 5)]
        button_colours = st.get("button_colours") or {}
        if self.ene is not None and hasattr(self.ene, "PROFILE_COLOURS"):
            merged = dict(self.ene.PROFILE_COLOURS)
            merged.update(button_colours)
            button_colours = merged
        logo = st.get("logo") or {}
        return {
            "Backend": self._backend(),
            "Zones": zones,
            "Brightness": max(0, min(255, brightness)),
            "Effect": effect,
            "EffectChoices": names,
            "EffectColor": (int(fx.get("red", 0)), int(fx.get("green", 0)), int(fx.get("blue", 255))),
            "EffectSpeed": max(0, min(255, int(fx.get("speed", 5)))),
            "EffectDirection": WIRE_TO_DIRECTION.get(int(fx.get("direction", 2)), "right"),
            "ButtonFollowsProfile": bool(st.get("button_follows_profile", True)),
            "ButtonColors": {k: _hex_to_rgb(v) for k, v in button_colours.items()},
            "LogoColor": _hex_to_rgb(logo.get("colour", "ffffff")),
            "LogoBrightness": max(0, min(255, int(logo.get("brightness", 100)))),
            "BacklightTimeout": bool(self.hw.get_backlight_timeout()),
        }

    def _display_values(self):
        if "display_mode" not in self.hw.features:
            return {"Mode": "unknown", "Choices": [], "HasMux": False, "ActiveGpu": "unknown"}
        dm = self.hw.get_display_mode() or {}
        mux = self.hw.detect_mux() or {}
        return {
            "Mode": str(dm.get("mode", "unknown")),
            "Choices": list(dm.get("available_modes", [])),
            "HasMux": bool(mux.get("has_mux", False)),
            "ActiveGpu": str(mux.get("active_gpu", "unknown")),
        }

    def _power_values(self):
        epp_path = self.hw._find_epp_path()
        epp = ""
        if epp_path:
            try:
                epp = Path(epp_path).read_text().strip()
            except OSError:
                epp = ""
        sources = []
        if "usb_wake_policy" in self.hw.features:
            for s in self.hw.get_usb_wake_sources() or []:
                sources.append((str(s.get("device", "")), bool(s.get("enabled", False))))
        return {
            "GameMode": bool(self.hw.get_game_mode().get("active", False)),
            "Epp": epp,
            "LcdOverride": bool(self.hw.get_lcd_override()),
            "BootAnimationSound": bool(self.hw.get_boot_animation_sound()),
            "UsbWakeSources": sources,
        }

    def _firmware_static_values(self):
        # Deliberately no fwupdmgr here: it is a 30 s subprocess and belongs
        # behind Firmware.Refresh.
        bios = Path("/sys/class/dmi/id/bios_version")
        try:
            bios_version = bios.read_text().strip()
        except OSError:
            bios_version = "Unknown"
        fwupd = any(os.access(os.path.join(p, "fwupdmgr"), os.X_OK)
                    for p in os.environ.get("PATH", "/usr/bin:/usr/local/bin").split(":"))
        return {
            "BiosVersion": bios_version,
            "FwupdAvailable": fwupd,
            "Updates": [],
            "LastRefresh": 0,
        }

    @staticmethod
    def _read_modprobe():
        try:
            for line in Path(MODPROBE_CONF).read_text().splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[0] == "options" and parts[1] == "linuwu_sense":
                    return parts[2].split("=")[0]
        except OSError:
            pass
        return ""

    # -- System ---------------------------------------------------------

    def _m_System_Ping(self, sender):
        return None

    # -- Telemetry ------------------------------------------------------

    def _m_Telemetry_Subscribe(self, sender, interval_ms):
        self.telemetry.subscribe(sender, interval_ms)

    def _m_Telemetry_Unsubscribe(self, sender):
        self.telemetry.unsubscribe(sender)

    # -- Thermal --------------------------------------------------------

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

    # -- Battery --------------------------------------------------------

    def _m_Battery_SetLimiter(self, sender, enabled):
        if not self.hw.set_battery_limiter(bool(enabled)):
            raise ControlError("HardwareFailure", "battery_limiter write failed")
        self.hw.settings.set("battery_limiter", bool(enabled))
        self.store.update(self._iface("Battery"), self._battery_values())

    def _m_Battery_SetCalibration(self, sender, enabled):
        if not self.hw.set_battery_calibration(bool(enabled)):
            raise ControlError("HardwareFailure", "battery_calibration write failed")
        self.hw.settings.set("battery_calibration", bool(enabled))
        self.store.update(self._iface("Battery"), self._battery_values())

    def _m_Battery_SetUsbCharging(self, sender, level):
        if level not in (0, 10, 20, 30):
            raise ControlError("InvalidArgument", "level must be 0, 10, 20 or 30")
        if not self.hw.set_usb_charging(int(level)):
            raise ControlError("HardwareFailure", "usb_charging write failed")
        self.hw.settings.set("usb_charging", int(level))
        self.store.update(self._iface("Battery"), self._battery_values())

    # -- Lighting -------------------------------------------------------

    def _lighting_refresh(self):
        self.store.update(self._iface("Lighting"), self._lighting_values())

    def _m_Lighting_SetZones(self, sender, zones, brightness):
        if len(zones) != 4:
            raise ControlError("InvalidArgument", "exactly four zones")
        hexes = [_rgb_to_hex(tuple(_byte(c, "colour") for c in z)) for z in zones]
        b = _byte(brightness, "brightness")

        def write():
            if not self.hw.set_per_zone_mode(*hexes, b):
                raise ControlError("HardwareFailure", "per-zone write failed")
            self.hw.settings.set("per_zone_mode", {
                "zone1": hexes[0], "zone2": hexes[1], "zone3": hexes[2],
                "zone4": hexes[3], "brightness": b})
            self.hw.settings.set("last_keyboard_mode", "per_zone")
            self._lighting_refresh()

        self._lighting.request("keyboard", write)

    def _m_Lighting_SetZoneMask(self, sender, zone_mask, color):
        mask = int(zone_mask) & 0x0F
        if not mask:
            raise ControlError("InvalidArgument", "zone_mask selects no zone")
        rgb = tuple(_byte(c, "colour") for c in color)
        pz = dict(self.hw.settings.get("per_zone_mode") or {})
        hexes = [pz.get(f"zone{i}", "ffffff") for i in range(1, 5)]
        for i in range(4):
            if mask & (1 << i):
                hexes[i] = _rgb_to_hex(rgb)
        b = int(pz.get("brightness", 100))
        self._m_Lighting_SetZones(sender, [_hex_to_rgb(h) for h in hexes], b)

    def _m_Lighting_SetBrightness(self, sender, brightness):
        b = _byte(brightness, "brightness")
        st = self.hw.settings
        if st.get("last_keyboard_mode") == "effect":
            fx = dict(st.get("four_zone_mode") or {})
            fx["brightness"] = b
            self._apply_effect(fx)
        else:
            pz = dict(st.get("per_zone_mode") or {})
            zones = [_hex_to_rgb(pz.get(f"zone{i}", "ffffff")) for i in range(1, 5)]
            self._m_Lighting_SetZones(sender, zones, b)

    def _apply_effect(self, fx):
        def write():
            ok = self.hw.set_four_zone_mode(
                fx["mode"], fx["speed"], fx["brightness"], fx["direction"],
                fx["red"], fx["green"], fx["blue"])
            if not ok:
                raise ControlError("HardwareFailure", "effect write failed")
            self.hw.settings.set("four_zone_mode", fx)
            self.hw.settings.set("last_keyboard_mode", "effect")
            self._lighting_refresh()

        self._lighting.request("keyboard", write)

    def _m_Lighting_SetEffect(self, sender, effect, brightness, color, speed, direction):
        names = self._effect_names()
        lowered = [n.lower() for n in names]
        if effect.lower() not in lowered:
            raise ControlError("InvalidArgument", f"effect must be one of {names}")
        if direction not in DIRECTION_TO_WIRE:
            raise ControlError("InvalidArgument", "direction must be 'left' or 'right'")
        r, g, b = (_byte(c, "colour") for c in color)
        fx = {
            "mode": lowered.index(effect.lower()),
            "speed": max(0, min(9, int(speed))),
            "brightness": _byte(brightness, "brightness"),
            "direction": DIRECTION_TO_WIRE[direction],
            "red": r, "green": g, "blue": b,
        }
        self._apply_effect(fx)

    def _m_Lighting_SetOff(self, sender):
        ene = self._ene()

        def write():
            if ene is not None:
                ene.set_off()
            else:
                pz = self.hw.settings.get("per_zone_mode") or {}
                if not self.hw.set_per_zone_mode("000000", "000000", "000000", "000000",
                                                 int(pz.get("brightness", 0))):
                    raise ControlError("HardwareFailure", "keyboard off write failed")
            self.hw.settings.set("last_keyboard_mode", "off")
            self._lighting_refresh()

        self._lighting.request("keyboard", write)

    def _m_Lighting_SetButtonFollowsProfile(self, sender, enabled):
        self.hw.settings.set("button_follows_profile", bool(enabled))
        if enabled:
            self.hw._sync_button_led(self.hw.get_thermal_profile())
        self._lighting_refresh()

    def _m_Lighting_SetButtonColor(self, sender, profile, color):
        ene = self._ene()
        if ene is None:
            raise ControlError("Unsupported", "button LED needs the ENE backend")
        rgb = tuple(_byte(c, "colour") for c in color)
        colours = dict(self.hw.settings.get("button_colours") or {})
        colours[str(profile)] = _rgb_to_hex(rgb)
        self.hw.settings.set("button_colours", colours)
        if profile == self.hw.get_thermal_profile():
            self._lighting.request("button", lambda: ene.set_button(_rgb_to_hex(rgb)))
        self._lighting_refresh()

    def _m_Lighting_SetLogo(self, sender, color, brightness):
        ene = self._ene()
        if ene is None:
            raise ControlError("Unsupported", "lid logo needs the ENE backend")
        rgb = tuple(_byte(c, "colour") for c in color)
        b = _byte(brightness, "brightness")

        def write():
            ene.set_logo(_rgb_to_hex(rgb), b)
            self.hw.settings.set("logo", {"colour": _rgb_to_hex(rgb), "brightness": b})
            self._lighting_refresh()

        self._lighting.request("logo", write)

    def _m_Lighting_SetBacklightTimeout(self, sender, enabled):
        if not self.hw.set_backlight_timeout(bool(enabled)):
            raise ControlError("HardwareFailure", "backlight_timeout write failed")
        self.hw.settings.set("backlight_timeout", bool(enabled))
        self._lighting_refresh()

    # -- Display --------------------------------------------------------

    def _m_Display_SetMode(self, sender, mode):
        choices = self.store.value(self._iface("Display"), "Choices") or []
        if mode not in choices:
            raise ControlError("InvalidArgument", f"mode must be one of {choices}")
        if self._display_busy:
            raise ControlError("Busy", "a display mode change is already running")
        self._display_busy = True

        def worker():
            try:
                result = self.hw.set_display_mode(mode)
                if not result.get("success"):
                    logger.warning(f"Display.SetMode({mode}): {result.get('error')}")
            finally:
                self._display_busy = False
                GLib.idle_add(lambda: (self.store.update(
                    self._iface("Display"), self._display_values()), False)[1])

        threading.Thread(target=worker, name="display-mode", daemon=True).start()

    # -- Power ----------------------------------------------------------

    def _m_Power_SetGameMode(self, sender, enabled):
        if enabled:
            self.hw.activate_game_mode()
        else:
            self.hw.deactivate_game_mode()
        self.store.update(self._iface("Power"), self._power_values())
        self.store.update(self._iface("Thermal"), self._thermal_values())

    def _m_Power_SetLcdOverride(self, sender, enabled):
        if not self.hw.set_lcd_override(bool(enabled)):
            raise ControlError("HardwareFailure", "lcd_override write failed")
        self.hw.settings.set("lcd_override", bool(enabled))
        self.store.update(self._iface("Power"), self._power_values())

    def _m_Power_SetBootAnimationSound(self, sender, enabled):
        if not self.hw.set_boot_animation_sound(bool(enabled)):
            raise ControlError("HardwareFailure", "boot_animation_sound write failed")
        self.hw.settings.set("boot_animation_sound", bool(enabled))
        self.store.update(self._iface("Power"), self._power_values())

    def _m_Power_SetUsbWake(self, sender, device, enabled):
        if not self.hw.set_usb_wake(device, bool(enabled)):
            raise ControlError("InvalidArgument", f"unknown wake device {device!r}")
        self.store.update(self._iface("Power"), self._power_values())

    # -- Audio ----------------------------------------------------------

    def _m_Audio_SetNoiseSuppression(self, sender, enabled):
        disabled = NOISE_CONF + ".disabled"
        try:
            if enabled:
                if os.path.exists(disabled) and not os.path.exists(NOISE_CONF):
                    os.rename(disabled, NOISE_CONF)
            elif os.path.exists(NOISE_CONF):
                os.rename(NOISE_CONF, disabled)
        except OSError as e:
            raise ControlError("HardwareFailure", str(e))
        self.hw.settings.set("audio_enhancement", {"noise_suppression": bool(enabled)})
        # The client that sees this flip restarts pipewire in its own session.
        self.store.update(self._iface("Audio"), {"NoiseSuppression": os.path.exists(NOISE_CONF)})

    # -- Firmware -------------------------------------------------------

    def _m_Firmware_Refresh(self, sender):
        if not self.store.value(self._iface("Firmware"), "FwupdAvailable"):
            raise ControlError("Unsupported", "fwupdmgr is not installed")
        if self._firmware_busy:
            raise ControlError("Busy", "a firmware refresh is already running")
        self._firmware_busy = True

        def worker():
            updates = []
            try:
                info = self.hw.get_firmware_info() or {}
                for dev in info.get("updates", []) or []:
                    releases = dev.get("Releases") or []
                    available = str(releases[0].get("Version", "")) if releases else ""
                    updates.append((str(dev.get("Name", dev.get("DeviceId", ""))),
                                    str(dev.get("Version", "")), available))
            except Exception as e:
                logger.warning(f"Firmware.Refresh failed: {e}")
            finally:
                self._firmware_busy = False
                GLib.idle_add(lambda: (self.store.update(self._iface("Firmware"), {
                    "Updates": updates, "LastRefresh": int(time.time())}), False)[1])

        threading.Thread(target=worker, name="fwupd-refresh", daemon=True).start()

    # -- Maintenance ----------------------------------------------------

    def _m_Maintenance_SetModprobeParameter(self, sender, parameter):
        if parameter not in MODPROBE_PARAMS:
            raise ControlError("InvalidArgument", f"parameter must be one of {MODPROBE_PARAMS}")
        if not self.hw.set_modprobe_parameter(parameter):
            raise ControlError("HardwareFailure", f"could not write {MODPROBE_CONF}")
        self.store.update(self._iface("Maintenance"), {"ModprobeParameter": self._read_modprobe()})

    def _m_Maintenance_ClearModprobeParameter(self, sender):
        if not self.hw.remove_modprobe_parameter():
            raise ControlError("HardwareFailure", f"could not remove {MODPROBE_CONF}")
        self.store.update(self._iface("Maintenance"), {"ModprobeParameter": self._read_modprobe()})

    def _m_Maintenance_RestartDaemon(self, sender):
        self.hw.restart_daemon()

    def _m_Maintenance_RestartDriversAndDaemon(self, sender):
        self.hw.restart_drivers_and_daemon()
