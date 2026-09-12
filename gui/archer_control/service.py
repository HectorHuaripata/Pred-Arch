"""
ArcherControl: GDBus registration, dispatch, authorisation, seeding and
the sysfs_notify watch on platform_profile.
"""

import os

from gi.repository import Gio, GLib

from archer_control.coalescer import LightingCoalescer
from archer_control.common import ControlError, load_node_info, logger
from archer_control.constants import (BUS_NAME, ERROR_PREFIX, FEATURE_GATES, OBJECT_PATH,
                                      PLATFORM_PROFILE_PATH, POLKIT_ACTIONS, SLOW_POLL_S)
from archer_control.interfaces.audio import AudioInterface
from archer_control.interfaces.battery import BatteryInterface
from archer_control.interfaces.display import DisplayInterface
from archer_control.interfaces.firmware import FirmwareInterface
from archer_control.interfaces.lighting import LightingInterface
from archer_control.interfaces.maintenance import MaintenanceInterface
from archer_control.interfaces.power import PowerInterface
from archer_control.interfaces.system import SystemInterface
from archer_control.interfaces.telemetry import TelemetryInterface
from archer_control.interfaces.thermal import ThermalInterface
from archer_control.store import PropertyStore
from archer_control.telemetry import TelemetrySampler


class ArcherControl(SystemInterface, TelemetryInterface, ThermalInterface, BatteryInterface,
                    LightingInterface, DisplayInterface, PowerInterface, AudioInterface,
                    FirmwareInterface, MaintenanceInterface):
    """Registers the v2 object on the bus and routes calls to HardwareManager.

    Dispatch convention: a D-Bus call to `<Interface>.<Method>` runs the
    Python method `_m_<Interface>_<Method>(self, sender, *args)` provided
    by the interface mixins — hence the camelCase segment in those names.
    The feature gate (FEATURE_GATES) and polkit (POLKIT_ACTIONS) run
    before the handler; typed errors come back as D-Bus errors.
    """

    def __init__(self, hw, bus_type=Gio.BusType.SYSTEM, xml_path=None,
                 ene_module=None):
        self.hw = hw
        self.ene = ene_module
        self._bus_type = bus_type
        self._conn = Gio.bus_get_sync(bus_type, None)
        self._node = load_node_info(xml_path)
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
        s.seed(self._iface("Audio"), self._audio_values())
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

