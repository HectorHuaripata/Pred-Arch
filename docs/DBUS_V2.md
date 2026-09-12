# D-Bus contract v2 — `io.github.archer.Control1`

The type-level definition lives in [`dbus/io.github.archer.Control1.xml`](../dbus/io.github.archer.Control1.xml).
This document covers what the XML cannot: cadence, error semantics,
authorization, and how the old `io.otectus.Archer1` interface is retired.

## Why a new contract

The v1 interface (`io.otectus.Archer1`) moves every payload as JSON inside a
D-Bus `string`. Measured consequences on the PHN16S-71 install (see the
radiography, 2026-09-11):

| v1 behaviour | Effect |
|---|---|
| `TelemetryUpdated` carries the whole monitoring blob every 2 s, whether or not anyone listens | daemon at 0.7 % CPU idle; GUI at 0.4 % CPU while hidden in the tray |
| `GetAllSettings` is one ~25-key dict fetched once at startup | nine of ten GUI pages never refresh |
| `ProfileChanged` exists, but nothing tells a client which *value* changed | the GUI never subscribed; the hardware mode button changes the profile invisibly |
| Errors are `{"success": false, "error": "..."}` strings | no typed error handling, no distinction between "not authorized" and "hardware said no" |

v2 makes every piece of state a typed, individually observable D-Bus
property, and makes the daemon do work only while someone is watching.

## Shape

- **Bus**: system. **Name**: `io.github.archer.Control1`. **Object**: `/io/github/archer/Control1`.
- **One object, nine interfaces** (`System`, `Telemetry`, `Thermal`, `Battery`,
  `Lighting`, `Display`, `Power`, `Audio`, `Firmware`, `Maintenance`). A client
  watches only the interfaces it cares about.
- **State is read-only properties.** Mutations are explicit methods so the
  daemon can run polkit against the caller — `org.freedesktop.DBus.Properties.Set`
  is not implemented.
- **Change notification is `PropertiesChanged`** with only the properties whose
  value differs from the last emission. No custom signals.

## Telemetry cadence

The `Telemetry` interface is the only hot path, so it is the only one with
rules beyond "emit when changed":

1. **Nothing is sampled while `Subscribers == 0`.** No sysfs reads, no timers.
2. A client calls `Subscribe(interval_ms)`; the daemon clamps the request to
   250–5000 ms and samples at the **fastest interval among live subscribers**.
   `IntervalMs` reports the effective value.
3. Subscriptions are keyed by the caller's unique bus name and **dropped on
   `NameOwnerChanged`**, so a crashed client cannot keep the daemon awake.
   `Unsubscribe` is for the polite case (window hidden to tray).
4. Each sample compares every property to the previous one and emits a single
   `PropertiesChanged` with the deltas. Temperatures are whole degrees and
   usage is an integer percent, so a quiet machine produces near-empty
   emissions.
5. `Battery` is sampled every 10 s regardless of the interval; it does not
   change faster than that.
6. Per-sample cost budget: no subprocess. `/proc/stat` is parsed in Python;
   hwmon and thermal paths are resolved **once** at startup (and again on
   `RestartDriversAndDaemon`); NVIDIA readings come from NVML through
   `ctypes` with a 2 s cache, `nvidia-smi` is never spawned on the hot path.

Everything outside `Telemetry` is event-driven: `Thermal.Profile` is watched
by polling `platform_profile` every 2 s (cheap single read, and it catches the
hardware button and any other writer), lighting properties change when a
setter succeeds, `Display.Mode` when `envycontrol` returns, `Firmware.Updates`
when a `Refresh` finishes.

## Lighting: immediate apply with coalescing

Every `Lighting.Set*` applies at once — there is no "Apply" step in v2. A
slider being dragged produces a burst of calls; the daemon keeps the **last
requested state per device** (keyboard, button, logo) and flushes it at most
every 50 ms. Callers get their reply when the request is *accepted*, not when
the LEDs are written; the property update is the confirmation. The ENE K5130
tolerates this rate in testing (see `ENE_PROTOCOL.md`); the WMI fallback is
rate-limited the same way.

`SetZoneMask` exposes the controller's native bitmask so a client can paint
half the keyboard in one write instead of four.

## Errors

Methods fail with D-Bus errors, never with a "success: false" payload:

| Error name | Meaning |
|---|---|
| `io.github.archer.Control1.Error.NotAuthorized` | polkit denied the action for this caller |
| `io.github.archer.Control1.Error.Unsupported` | the feature is not in `System.Features` on this machine |
| `io.github.archer.Control1.Error.InvalidArgument` | value out of range, unknown profile/effect/mode |
| `io.github.archer.Control1.Error.HardwareFailure` | the sysfs/HID write failed; message carries the errno text |
| `io.github.archer.Control1.Error.Busy` | a long operation (`Display.SetMode`, `Firmware.Refresh`) is already running |

Clients should treat `NotAuthorized` as "revert the control, no toast" (the
polkit agent already told the user) and everything else as "revert and show
the message".

## Authorization

The existing polkit action ids are kept and the policy file is reused:

| Action id | Methods |
|---|---|
| `io.otectus.archer1.set-profile` | `Thermal.SetProfile` |
| `io.otectus.archer1.set-fan` | `Thermal.SetFanSpeed`, `SetFanAuto`, `SetFanCurve`, `ClearFanCurve` |
| `io.otectus.archer1.set-hardware` | `Battery.*`, `Lighting.*`, `Power.*`, `Audio.*` |
| `io.otectus.archer1.set-display` | `Display.SetMode` |
| `io.otectus.archer1.set-gamemode` | `Power.SetGameMode` |
| `io.otectus.archer1.system-control` | `Maintenance.*` |

Read-only properties and `Telemetry.Subscribe` need no authorization. The
action ids get renamed to the `io.github.archer` namespace in v3.0 when the
v1 shim goes away (both names are accepted in the meantime).

## Compatibility and retirement of v1

- **Phase A** (this branch): the daemon serves **both** `io.otectus.Archer1`
  and `io.github.archer.Control1` from the same process. The old GUI keeps
  working unchanged. The v1 telemetry signal is only emitted while a v1
  client is connected (tracked the same way as v2 subscribers).
- **Phase B**: the new GUI ships and speaks v2 only. `install.sh` stops
  installing the old GUI.
- **Phase C** (v3.0): the v1 interface, its JSON helpers and the
  `io.otectus` policy ids are removed. `System.Version` reports `3.0.0`.

## Implementation notes

- The daemon moves from `dbus-python` to **`Gio.DBusConnection`**
  (`register_object` with this XML, `emit_signal` for `PropertiesChanged`,
  `invocation.get_sender()` for polkit). One D-Bus stack in the process, and
  it is the one the tray already uses.
- A `PropertyStore` helper owns the last-emitted value per interface and
  produces the delta dict; setters and samplers never emit directly.
- Feature gating: a method on an interface whose feature is absent raises
  `Unsupported` *before* polkit, so a client on an Aspire does not get an
  auth prompt for a fan it does not have.
- Smoke test: `tests/dbus_smoke.py` gains a v2 pass that subscribes at
  1000 ms, waits for two `PropertiesChanged`, unsubscribes and asserts
  `Subscribers` returns to 0 and `IntervalMs` to 0.
