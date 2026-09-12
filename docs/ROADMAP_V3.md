# Archer v3 — roadmap

Fork of otectus/Archer 2.0.1 for the Predator Helios Neo 16S AI (PHN16S-71)
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

## Step 2 — Daemon behind the v2 contract

Contract: [`dbus/io.github.archer.Control1.xml`](../dbus/io.github.archer.Control1.xml) + [`DBUS_V2.md`](DBUS_V2.md).

- [ ] `PropertyStore` + `Gio.DBusConnection` registration of the XML; v1 kept as a shim in the same process.
- [ ] Telemetry: subscriber tracking via `NameOwnerChanged`, adaptive interval, delta-only emission, no subprocess.
- [ ] Resolve hwmon/thermal paths once; NVML via ctypes.
- [ ] `Thermal.Profile` watcher replaces `poll_profile_led` (same read, now also notifies clients).
- [ ] Lighting coalescer (50 ms, last-state-wins, per device).
- [ ] Typed errors; feature gate before polkit.
- [ ] `tests/dbus_smoke.py` v2 pass.
- Exit criterion: daemon idle CPU with no subscribers ≈ 0; old GUI still works.

## Step 3 — New GUI

Toolkit decision pending (see "Open decision" below). Whatever the toolkit:

- [ ] Sidebar with 5–6 sections grouping today's 10 pages: Overview · Performance (profile, fans, curves, game mode) · Lighting (keyboard, button, logo) · Battery & Power (limiter, calibration, USB, wake) · Display & Audio · System (firmware, driver, maintenance).
- [ ] Pages built on first visit, torn down never; each page binds to the properties it shows and nothing else.
- [ ] Hidden to tray ⇒ `Telemetry.Unsubscribe`; visible ⇒ `Subscribe(1000)`; Overview in front ⇒ `Subscribe(500)`.
- [ ] Overview: animated gauges for temps/usage, RPM as hero numbers, 5-minute sparkline, profile chip that follows the hardware button.
- [ ] Lighting: keyboard preview with four clickable zones, drag = apply, effect gallery, button/logo colour with profile mapping.
- [ ] Tray: minimal, quick profile switch, temperature in tooltip. No Pillow.
- [ ] Theme follows the system (light/dark, accent); Spanish and English.
- Exit criterion: every control reflects external changes within one sampling interval; no "Apply" buttons except `Display.SetMode`.

## Step 4 — Measure

Same procedure as the baseline (`/proc/<pid>/status`, 10 s tick sample with
the window hidden). Targets: GUI ≤ 40 MB RSS hidden, ≤ 0.05 % CPU hidden,
daemon ≈ 0 % with no subscribers.

## Open decision — GUI toolkit

| | Qt 6 / QML (PySide6 first, C++ if needed) | GTK4 / libadwaita |
|---|---|---|
| Fit on Plasma | native (Breeze, system accent) | looks like GNOME |
| Live values | QML property bindings + `Behavior on` | hand-driven `Adw.TimedAnimation` |
| Gauges | `Canvas`/`Shape`, trivial | `Gtk.Snapshot`, more code |
| Tray | `QSystemTrayIcon` | SNI by hand (as today) |
| Idle RSS | ~60–80 MB Python · ~25–35 MB C++ | ~50–70 MB Python · ~20 MB Rust |

Recommendation: Qt 6 / QML with PySide6, because the machine runs KDE Plasma
and live bindings are the whole point of the rewrite.
