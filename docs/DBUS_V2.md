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
- **One object, eleven interfaces** (`System`, `Telemetry`, `Thermal`, `Battery`,
  `Lighting`, `Display`, `Power`, `Storage`, `Audio`, `Firmware`, `Maintenance`).
  A client watches only the interfaces it cares about.
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
5. `Battery` and the `Storage` interface are sampled every 10 s regardless
   of the interval (`SLOW_PERIOD_S`); neither changes faster than that.
   `Memory` (`(uu)` used/total MiB), `CpuFreqMhz` (average over online
   cores), `NpuUsage` (from the `intel_vpu` busy-time counter) and
   `GpuPowerW` (NVML) ride on the same tick as the temperatures.
6. Per-sample cost budget: no subprocess. `/proc/stat` is parsed in Python;
   hwmon and thermal paths are resolved **once** at startup (and again on
   `RestartDriversAndDaemon`); NVIDIA readings come from NVML through
   `ctypes` with a 2 s cache, `nvidia-smi` is never spawned on the hot path.

Everything outside `Telemetry` is event-driven: `Thermal.Profile` is watched
through the kernel's `sysfs_notify` on `platform_profile` (POLLPRI on the
file — the core notifies on every store and `linuwu_sense` calls
`platform_profile_notify()` from the hardware-button handler), lighting
properties change when a setter succeeds, `Display.Mode` when `envycontrol`
returns, `Firmware.Updates` when a `Refresh` finishes. A 30 s safety poll
refreshes ENE readiness and fan-curve state.

**Every WMI-backed sysfs attribute costs 13–20 ms of CPU to read on this
platform** (`platform_profile`, `battery_limiter`, `usb_charging`, …; the ACPI
interpreter runs the WMI method), and `four_zoned_kb/per_zone_mode` costs
~70 ms. That is why nothing in the daemon polls them: they are read once at
startup, after a setter, and on notification. The EC hwmon (`acer`) fans and
temperatures are ordinary reads (~0.1 ms).

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

## Battery: calibration is a cycle, not a setting

`Battery.Calibration` reflects a mode the embedded controller runs by
itself: full discharge, then a full charge, several hours in total.
`SetCalibration(true)` starts it, `SetCalibration(false)` cancels it, and
the firmware clears the flag when the cycle ends (the driver applies the
WMI calibration event). The daemon never persists or restores it, and
re-reads the flag — one WMI call — only while a cycle is known to be
running (on the 10 s telemetry tick with subscribers, on the 30 s safety
poll without), so clients see it finish. A client should present it as
start / progress / cancel; a switch would suggest a preference that
survives a reboot, which it is not.

## Power: CPU energy policy per profile

The `Power` interface exposes what the `intel_pstate` (or `cpufreq`) driver
offers on the machine: the energy-performance preference (`Epp`,
`EppChoices`), turbo (`Turbo`, `TurboAvailable`), the scaling governor
(`CpuGovernor`, `CpuGovernors`) and the hybrid topology (`CpuTopology` =
performance cores, efficiency cores). Missing sysfs files remove the
feature (`cpu_epp`, `cpu_turbo`, `cpu_governor` in `System.Features`) and
the setters raise `Unsupported`.

`SetEpp` applies at once **and is remembered for the active platform
profile** (`EppByProfile`). When the profile changes — from the panel, the
hardware button or `powerprofilesctl` — the daemon reapplies the stored
preference 500 ms later (`EPP_REAPPLY_DELAY_MS`), after
`power-profiles-daemon` has written its own default, so the user's choice
wins without fighting the OS on every write. `ClearEppOverride(profile)`
drops the override and the OS default applies again on the next change.
Turbo and governor are applied to every core, remembered in the daemon
settings and restored at startup (the kernel resets them on boot).

`DynamicBoost` is NVIDIA's `nvidia-powerd` service (shifts power budget
between CPU and dGPU on laptops with the feature); the setter enables or
disables the unit through `systemctl`, which is why it sits behind
`system-control` rather than `set-hardware`. `DynamicBoostAvailable` says
whether the binary is installed.

## Storage: overview, not management

`Storage.Drives` lists the physical block devices (name, model, size,
temperature from the `nvme` or `drivetemp` hwmon, −1 when none) and
`Storage.Filesystems` the mounted local filesystems (mount point, device,
fstype, size, used) — real devices only, no tmpfs, no snap loops, no
bind-mounted duplicates. Everything comes from `/sys/class/block`,
`/proc/self/mounts` and `statvfs`; no subprocess, no SMART commands (those
need `smartctl` and root ioctls and are a job for a dedicated tool).
The interface is read-only by design: a control panel should show a full
disk, not offer to reformat it.

## Audio: two layers

`Audio.NoiseSuppression` is a PipeWire filter (RNNoise) that the
`audio-enhance` installer module sets up; the daemon only renames the filter
file, and the client that sees the property change restarts PipeWire in its
own session. `NoiseSuppressionAvailable` says whether the filter is installed
at all; without it the setter raises `Unsupported`.

Everything else on the interface is processing that runs **inside the Intel
SOF DSP** and is exposed as ALSA mixer controls of the codec card: speaker
dynamic-range compression (`SpeakerDrc`), the 4-microphone beamformer
(`MicBeamforming`, `MicBeamAngle` in degrees from `MicBeamAngles`, 0 =
straight ahead, negative = left), microphone DRC (`MicDrc`) and the codec's
headphone auto-mute (`AutoMute`). The daemon reads and writes them with
`amixer` — a subprocess, tolerated because these are cold paths: once at
startup, once per user action, never sampled. Values are remembered in the
daemon settings and reapplied at startup (alsa-restore normally keeps them;
the reapply covers an unclean shutdown). A codec without the beamformer
control reports `DspAvailable = false` and the feature `audio_dsp` is absent,
so the setters raise `Unsupported` before polkit.

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
| `io.otectus.archer1.set-hardware` | `Battery.*`, `Lighting.*`, `Power.*` except the two below, `Audio.*` |
| `io.otectus.archer1.set-display` | `Display.SetMode` |
| `io.otectus.archer1.set-gamemode` | `Power.SetGameMode` |
| `io.otectus.archer1.system-control` | `Maintenance.*`, `Power.SetDynamicBoost` (enables a systemd unit) |

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
