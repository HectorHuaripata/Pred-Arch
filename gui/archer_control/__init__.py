"""
Archer daemon — D-Bus contract v2, io.github.archer.Control1.

Serves the interfaces described in dbus/io.github.archer.Control1.xml on
top of the existing HardwareManager. Everything the daemon knows is a
typed, read-only property; changes go out as
org.freedesktop.DBus.Properties.PropertiesChanged carrying only the values
that differ from the last emission. Setters are methods so polkit can be
run against the caller.

Layout
------
constants.py   names, paths, tunables, polkit and feature tables
common.py      typed error, colour helpers, XML loading
store.py       PropertyStore — last-emitted values, delta emitter
telemetry.py   TelemetrySampler — subscriber-driven sampling
coalescer.py   LightingCoalescer — last-state-wins LED writes
alsa_dsp.py    SofDsp — the codec card's DSP controls through amixer (cold path)
interfaces/    one mixin per D-Bus interface (value builder + handlers)
service.py     ArcherControl — registration, dispatch, polkit, watches

Uses GDBus (Gio); the v1 dbus-python service coexists in the same process
during the migration (docs/DBUS_V2.md, "Compatibility").
"""

from archer_control.common import ControlError
from archer_control.constants import BUS_NAME, ERROR_PREFIX, OBJECT_PATH
from archer_control.service import ArcherControl

__all__ = ["ArcherControl", "ControlError", "BUS_NAME", "ERROR_PREFIX", "OBJECT_PATH"]
