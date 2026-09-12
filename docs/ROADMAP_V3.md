# Archer v3 — roadmap

Pred-Arch: fork of otectus/Archer 2.0.1 for the Predator Helios Neo 16S AI (PHN16S-71)
and, by extension, any Acer where the ENE K5130 drives the keyboard. Goal: a
control panel that is live, light while hidden, and native to the desktop it
runs on. The diagnosis this plan comes from is the radiography of 2026-09-11.

Baseline to beat (window hidden to tray, 20 min uptime):

| | GUI | Daemon |
|---|---|---|
| RSS | 82 MB (+37 MB swap) | 19 MB |
| VSZ | 1.8 GB | 55 MB |
| Threads | 11 | 1 |
| CPU idle | 0.4 % | 0.7 % |

## Step 1 — Consolidate  ✅ done (branch `ene-keyboard`, pushed)

- Commit the pending ENE retry (`bbb91eb`).
- Bring the two `/opt/archer` hotfixes into the repo (`c089b1d`).
- Fold the early-start drop-in into the unit (`b22571b`).
- Delete `~/archer-fixes-backup`. Branch `v3` from here.

## Step 2 — Daemon behind the v2 contract  ✅ done on `v3`

Contract: [`dbus/io.github.archer.Control1.xml`](../dbus/io.github.archer.Control1.xml) + [`DBUS_V2.md`](DBUS_V2.md).

- [x] `gui/archer_control/` (package: constants, store, telemetry, coalescer, one mixin per interface, service): `PropertyStore` + `Gio.DBusConnection` registration of the XML; v1 kept as a shim in the same process.
- [x] Telemetry: subscriber tracking via `NameOwnerChanged`, adaptive interval (250–5000 ms), delta-only emission, no subprocess; v1 `TelemetryUpdated` only while a v1 client is on the bus.
- [x] Sensor paths resolved once (`_resolve_sensor_paths`), `/proc/stat` delta in Python, NVML via ctypes, GPU temperature from the EC hwmon (`acer` temp2) so the dGPU is not woken.
- [x] `Thermal.Profile` follows `platform_profile` through `sysfs_notify` (POLLPRI, zero cost idle, ~170 ms end-to-end from `powerprofilesctl`); WMI attributes are never polled — each read is 13–20 ms of CPU on this platform.
- [x] Lighting coalescer (50 ms, last-state-wins, per device; first write synchronous so its error reaches the caller).
- [x] Typed errors (`…Error.NotAuthorized|Unsupported|InvalidArgument|HardwareFailure|Busy`); feature gate before polkit; polkit asynchronous.
- [x] `tests/dbus_v2_smoke.py` (runs the daemon in `--session-bus` mode) wired into CI.
- [ ] Deploy to `/opt/archer` and measure. On Arch the bus policy dir is `/usr/share/dbus-1/system.d` (the installer now detects it).
- Exit criterion met on the session bus: no sampling and no signals with zero subscribers; old GUI unaffected.

Developer loop: `cd gui && python3 archer_daemon.py --session-bus`, then
`busctl --user introspect io.github.archer.Control1 /io/github/archer/Control1`.

## Step 3 — New GUI  ✅ first cut on `v3` (`gui-qt/`)

Qt 6 / QML with PySide6, Kirigami + qqc2-desktop-style (Breeze under Plasma).

- [x] Sidebar with 6 sections: Overview · Performance · Lighting · Battery & Power · Display & Audio · System.
- [x] Pages created on first visit and kept; every control binds to the daemon property it shows (`archerqt/bus.py` generates the Qt properties from the XML).
- [x] Hidden to tray ⇒ `Telemetry.Unsubscribe`; visible ⇒ `Subscribe(1000)` (500 was measured to cost ~6 % CPU in full-window re-renders for no visible gain on integer readings).
- [x] Overview: GPU-drawn gauges (Shapes) for temps/usage, RPM hero numbers, 5-minute sparkline, profile bar that follows the hardware button.
- [x] Lighting: four-zone preview, click a zone to colour it alone, swatches + colour dialog applied live, effect gallery, speed/direction, lid logo, backlight timeout. No "Apply" anywhere.
- [x] Mode-button LED: one colour per profile (own colours, presets such as traffic light, factory reset; the mapping is echoed under the profile buttons) or one fixed colour kept across profile changes and resume.
- [x] Controls revert when the daemon refuses (typed errors → passive notification; `NotAuthorized` silent).
- [x] Tray: `QSystemTrayIcon` with quick profile switch and temperatures in the tooltip while visible.
- [x] Restructured for contribution: `paths` / `settings` / `catalog` / `tray` / `controller` modules, every string through `qsTr()` / `translate()`, no literal paths, thresholds or cadences in QML.
- [ ] Spanish translation (`gui-qt/translations/`, infrastructure in place).
- [ ] Fan-curve editor is a plain point list; a drag-able chart is a later polish.
- Exit criterion met: every control reflects external changes within one sampling interval; only `Display.SetMode` needs a confirmation step (logout).

## Step 4 — Measure

Same procedure as the baseline (`/proc/<pid>/status`, 10 s tick sample with
the window hidden). Targets: GUI ≤ 40 MB RSS hidden, ≤ 0.05 % CPU hidden,
daemon ≈ 0 % with no subscribers.

## Toolkit decision (settled: Qt 6 / QML, PySide6)

| | Qt 6 / QML (PySide6 first, C++ if needed) | GTK4 / libadwaita |
|---|---|---|
| Fit on Plasma | native (Breeze, system accent) | looks like GNOME |
| Live values | QML property bindings + `Behavior on` | hand-driven `Adw.TimedAnimation` |
| Gauges | `Canvas`/`Shape`, trivial | `Gtk.Snapshot`, more code |
| Tray | `QSystemTrayIcon` | SNI by hand (as today) |
| Idle RSS | ~60–80 MB Python · ~25–35 MB C++ | ~50–70 MB Python · ~20 MB Rust |

Chosen: Qt 6 / QML with PySide6, because the machine runs KDE Plasma and
live bindings are the whole point of the rewrite. C++ stays an option if
idle RSS ends up mattering.
