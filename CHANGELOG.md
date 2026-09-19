# Changelog

All notable changes to Archer Compatibility Suite are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Audio processing in the DSP.** The Intel SOF firmware behind the
  Realtek ALC245 exposes speaker dynamic-range compression, a steerable
  4-microphone beamformer (−90…+90°), microphone DRC and headphone
  auto-mute as ALSA controls. `Audio` publishes them as typed properties
  with setters; the panel's Display & Audio page gets Speakers and
  Microphone cards. Zero CPU: the DSP does the work. Values persist and are
  reapplied at daemon start.
- Audio page also shows whether the RNNoise filter is installed and whether
  a WebRTC echo-cancel module is configured in the user's PipeWire session.
- System page explains what fwupd would and would not update on an Acer
  (BIOS comes from Acer's site; fwupd covers SSD and Thunderbolt).
- **CPU energy policy.** `Power` exposes the `intel_pstate` energy-
  performance preference, turbo, scaling governor and the P/E-core
  topology. The preference is remembered **per platform profile** and
  reapplied after `power-profiles-daemon` writes its default, so "Quiet"
  can mean `power` and "Performance" can mean `performance` without
  touching the OS profile. NVIDIA Dynamic Boost (`nvidia-powerd`) can be
  enabled from the same page. Performance page gets a CPU card and a
  Discrete GPU card (with live power draw).
- **Storage overview.** New read-only `Storage` interface: drives with
  model, size and hwmon temperature, plus mounted local filesystems with
  usage bars on the Overview page. Sampled every 10 s from sysfs; no
  subprocess, no SMART.
- Overview: NPU load gauge (`intel_vpu` busy time) when the accelerator is
  present, average CPU frequency and GPU power under the gauges, memory
  used/total.
- **Panel refresh rate** on the Display & Audio page, read from and
  applied through `kscreen-doctor` in the user's session (Plasma keeps the
  choice per display). Shown disabled, with the reason, when the built-in
  panel is switched off.
- **Camera page.** Every v4l2 control of the first video device
  (brightness, white balance, power-line frequency, exposure, privacy…)
  rendered from its type — sliders, switches, menu buttons — with a
  restore-defaults button. Session side through `v4l2-ctl`; the daemon is
  not involved. New installer dependency `v4l-utils`.

### Changed

- **Battery calibration is a cycle, not a switch.** The Battery & Power
  page now offers "Start calibration cycle" behind a confirmation, shows
  the phase (draining / charging back up, with the percentage) while the
  EC runs it and a Cancel button. The daemon stopped persisting the flag
  and re-reads it while a cycle is running, so the panel sees the EC
  finish instead of showing an "on" switch forever.

### Fixed

- **Noise suppression toggle reported success without the filter.** It now
  raises `Unsupported` with the installer module to run.
- **One panel per session.** Launching Archer while it was already running
  started another full instance: another telemetry subscription, another
  tray icon, ~70 MB more, and two windows able to send contradictory
  commands. The panel now owns `io.github.archer.Panel` on the session bus;
  a second launch calls `Activate()` on the running one — which shows and
  raises its window — and exits. Hardware writes were already serialised
  by the daemon; this removes the duplicate front ends.

## [2.1.1] — 2026-09-12

### Fixed

- **Linuwu-Sense builds on kernel 7.2**: the installer patches the three
  `strncpy` calls (no longer implicitly declared) to `memcpy` after cloning
  the driver; all three copy `min(count, sizeof - 1)` bytes and terminate
  by hand. Without it the module is missing after a kernel upgrade and the
  panel shows the profile as "unknown".
- **Installer aborts on a failed system upgrade** instead of installing
  modules on freshly synced databases (a partial upgrade broke every Qt
  application on the reference machine).
- Installer no longer reports "Linuwu-Sense driver not detected" when it
  is loaded (`grep -q` under `pipefail` killed `dkms status` with SIGPIPE).
- Daemon: `GLib` imported at module level; `schedule_ene_retry()` raised
  `NameError` when the ENE controller was slow to appear.
- CI: the v1 D-Bus smoke ran service and client in one process and
  deadlocked; it now spawns the service. The smoke job uses the distro
  Python that can import `python3-dbus`; actions bumped to Node 24
  versions; flake8 covers `gui-qt/`.

## [2.1.0] — 2026-09-11

First Pred-Arch release: a fork of Archer Compatibility Suite 2.0.1 for the
Predator Helios Neo 16S AI (PHN16S-71). New control panel,
new D-Bus contract, daemon hot path rewritten. Developed with the support
of Claude (Anthropic) as a pair-programming assistant; verified on the
hardware by the maintainer.

### Added

- **D-Bus contract v2** `io.github.archer.Control1` (`gui/archer_control.py`,
  `dbus/io.github.archer.Control1.xml`, `docs/DBUS_V2.md`): typed read-only
  properties over nine interfaces, `PropertiesChanged` deltas, explicit
  polkit-gated setters, typed errors. Telemetry is sampled only while a
  client is subscribed (250–5000 ms, fastest live subscriber wins, dropped
  on `NameOwnerChanged`).
- **Qt 6 / QML control panel** (`gui-qt/`): PySide6 + Kirigami, Breeze on
  Plasma, follows the system colour scheme. Six sections, pages created on
  first visit, every control bound to the daemon property it shows and
  applied live — no Apply buttons. Hidden to the tray it unsubscribes and
  costs no CPU. Tray with quick profile switch.
- **ENE K5130 keyboard backend** (`gui/archer_ene.py`, `docs/ENE_PROTOCOL.md`)
  for models where the ACPI-WMI lighting path silently does nothing; verified
  effects, mode-button LED coloured by profile, lid logo, reapply after
  resume, late-appearing controller handled.
- `archer_daemon.py --session-bus` developer mode and `tests/dbus_v2_smoke.py`.

### Changed

- Daemon hot path: sensor paths resolved once, `/proc/stat` deltas instead of
  an `awk` fork per tick, NVML via ctypes, GPU temperature from the EC hwmon
  (no dGPU wake-ups), `platform_profile` followed through `sysfs_notify`
  instead of polling. WMI attributes cost 13–20 ms of CPU per read on this
  platform and are never polled.
- Daemon unit starts after `basic.target` instead of `multi-user.target`.
- Polkit: day-to-day actions (`set-profile`, `set-fan`, `set-hardware`,
  `set-gamemode`) are allowed without a password for the active local
  session. `set-display` and `system-control` still prompt.
- The legacy `TelemetryUpdated` signal is emitted only while a v1 client is
  on the bus.
- Installer detects the D-Bus policy directory (`/usr/share/dbus-1/system.d`
  on Arch) and ships the Qt panel; `archer-gui` launches it.

### Removed

- The GTK4/libadwaita panel (`gui/archer_gui.py`, `gui/archer/`) and its
  `gtk4`, `libadwaita`, `python-pillow` dependencies. The installer removes
  it from `/opt/archer` on upgrade.

## [2.0.1] — 2026-05-01

Hardening sweep triggered by [#4](https://github.com/otectus/Archer/issues/4)
("Archer GUI not updating and some other problems"). Closes that issue and a
broad set of correctness/security bugs surfaced by audit.

GUI package version bumped in lockstep: `1.0.0` → `1.0.1`.

### Fixed

- **Installer no longer requires a reboot to connect.** `modules/gui.sh` now
  reloads `dbus.service` (with `kill -HUP $(pidof dbus-daemon)` fallback) after
  copying `io.otectus.Archer1.conf`, so the new policy takes effect immediately.
- **GUI no longer freezes when the daemon is slow.** Every D-Bus call from
  `gui/archer/client.py` now passes a 5s `timeout=` (longer for `envycontrol`,
  `fwupdmgr`, restart). Without it, dbus-python defaulted to no timeout and a
  single hung sysfs read in the daemon would freeze the polling thread forever.
- **Status label now reflects reality.** The window's "Connected" label was set
  once at startup and never updated. It now flips to "Daemon Offline" or
  "Stale" with exponential-backoff reconnect (5/10/20/60s) and surfaces the
  underlying error in a toast.
- **Audio noise-suppression toggle now actually takes effect.** The daemon's
  `systemctl --user restart pipewire.service` ran inside the *root* user
  manager, never touching the user's pipewire. Replaced with an
  `AudioEnhancementChanged` D-Bus signal that the GUI handles in the user's
  own session.
- **`restart_daemon` no longer "loses" the D-Bus reply.** The synchronous
  `systemctl restart` killed the daemon before the reply flushed. Now uses
  `systemd-run --on-active=2s --no-block` so the GUI sees a clean response.
- **`get_fan_rpm` now picks the right hwmon device.** Allowlists Acer-relevant
  chipsets (`linuwu_sense`, `acer_wmi`, `nct67xx`, `it87`, `dell_smm_hwmon`)
  before falling back to "first device with `fan1_input`".
- **Setter UI controls revert on daemon failure.** Battery limit switch, USB
  charging combo, LCD override switch, boot animation switch, backlight
  timeout switch now flip back to the previous value with an explanatory
  toast when the daemon refuses (was fire-and-forget — UI lied about state).
- **Tray init failures are no longer silent.** Logged at WARNING and surfaced
  in a toast on first window show so the close-to-tray hint isn't bogus.
- **`uninstall.sh` no longer rm-rfs `/.local/...` if `$HOME` is unset under
  sudo.** Guard added.

### Changed

- **Telemetry now arrives via D-Bus signal (`TelemetryUpdated`) instead of
  polling.** The daemon emits every 2s; the GUI subscribes and watches for
  staleness. The previous polling loop spawned a new thread every 2s and
  would silently pile up zombies if any single call hung. `GetMonitoringData`
  remains for the initial settings fetch and backward compat.
- **D-Bus is now mandatory.** The Unix-socket fallback in
  `gui/archer_daemon.py` (`DaemonServer` class, ~340 LOC) was unreachable
  from the user-mode GUI anyway (socket was 0o660 root:root). Removed.
  `gui/archer/client.py` similarly drops the socket-fallback path. A failed
  D-Bus startup now logs an actionable error pointing at the policy file
  and `dbus reload`.
- **Service unit hardened.** `gui/archer-daemon.service` now uses
  `RuntimeDirectory=archer` (so systemd creates `/run/archer/` with
  0755 root:root) and `ReadWritePaths=/etc/archer` (required by
  `ProtectSystem=full`). PID file moved from `/var/run/archer-daemon.pid`
  to `/run/archer/daemon.pid`. `Requires=dbus.service` added.
- **Install manifest moved to `/var/lib/archer/install-manifest.json`**
  (root-owned, 0644). Resolves the install-as-user / uninstall-as-sudo
  `$HOME` mismatch and stops local users tampering with manifest entries
  that `uninstall.sh` later sources. Manifests at the previous user-home
  paths (and the legacy DAMX path) are migrated automatically on the next
  install or uninstall run.
- **Per-module install rollback.** `INSTALLED_FILES` / `INSTALLED_DKMS` /
  `INSTALLED_PACKAGES` are snapshotted before each `module_install` and
  restored on failure, so the saved manifest only lists modules that
  actually installed cleanly.
- **Daemon hot-path probes are cached** (5s TTL). `nvidia-smi`, `lspci`,
  and `which envycontrol` results are reused across the GUI's monitoring
  ticks so a hung NVIDIA driver no longer drives the daemon thread into
  the ground.

### Security

- **Path-traversal in `uninstall.sh` closed.** The uninstall manifest source
  loop now refuses to `source` any module name that fails the
  `^[a-z][a-z0-9_-]+$` allowlist *and* isn't in the canonical `MODULE_IDS`
  array. A tampered `~/.local/share/archer/install-manifest.json` could
  previously inject e.g. `mod="../../tmp/evil"` and gain code execution
  under `sudo` when the user ran uninstall.
- **`run_cmd` shell-meta guard.** `gui/archer_daemon.py:run_cmd` now refuses
  any command containing `;`, `&&`, `||`, `$(`, or backticks unless the
  caller passes `shell_meta_ok=True`. No present callsite is exploitable;
  the guard catches future regressions where a user-supplied value flows
  into a shell string.
- **`MODULE_IDS` is now a single source of truth** in `lib/modules.sh`,
  consumed by both `install.sh` (validating `--modules`) and `uninstall.sh`
  (validating manifest entries before `source`).

### Added

- **`tests/dbus_smoke.py` + `tests/dbus_smoke.sh`.** Headless smoke harness
  that boots `ArcherDBusService` against a private session bus with a mocked
  `HardwareManager`, asserts the required methods + signals appear in the
  introspection XML, and waits for the first `TelemetryUpdated` emit.
- **CI: `python-syntax` and `dbus-introspect-smoke` jobs.**
  `python -m py_compile` for every `gui/**/*.py`; smoke harness via
  `dbus-run-session` so CI fails loudly on signal/method regressions.
- **`.github/ISSUE_TEMPLATE/gui-not-updating.md`** with required fields:
  distro+kernel, daemon status, journal, `busctl introspect`, GUI logs.
  Would have closed #4 in one round trip.
- **README → Troubleshooting** section covering "Daemon Offline / Stale"
  and "GUI hangs forever" with the exact triage commands.
- **`is_known_module` allowlist with ~25 lines of bats tests** covering
  path-traversal, shell-metacharacter, and well-formed-but-unknown IDs.

### Removed

- **`gui/install-gui.sh`** legacy wrapper. Use `./install.sh --modules gui`.
- **`DaemonServer` class and `/var/run/archer.sock`** from the daemon.
- **Unix-socket fallback path** from `gui/archer/client.py`.

### Migration notes for upgraders from 2.0.0

- The first run of `./install.sh` after upgrading copies your existing
  `~/.local/share/archer/install-manifest.json` (and any legacy
  `~/.local/share/damx/install-manifest.json`) into `/var/lib/archer/`.
  Nothing else needed.
- If the daemon is currently running with a `/var/run/archer-daemon.pid`
  PID file, the new unit's `RuntimeDirectory=archer` will create
  `/run/archer/` on next start. Old `/var/run/archer.sock` is removed by
  the uninstall path; no manual cleanup required.
- A short `systemctl reload dbus.service` happens during the GUI module
  install. On most desktops this is invisible; you may briefly see your DE's
  panel/applets reconnect.

## [2.0.0] — 2026-04-20

Initial release with D-Bus IPC + polkit authorization, 13 installer modules,
GTK4/Adwaita control panel, install manifest, and CI/test scaffolding.
