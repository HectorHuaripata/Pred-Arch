# Archer control panel (Qt 6 / QML)

The v3 GUI. Talks only to `io.github.archer.Control1` (see
`docs/DBUS_V2.md`); needs daemon 2.1+ with `archer_control.py`.

## Layout

| Path | Role |
|---|---|
| `archer_qt.py` | entry point; `--hidden` starts in the tray |
| `archerqt/paths.py` | where the contract XML, icons and translations live (source tree, install prefix, `ARCHER_PREFIX`) |
| `archerqt/settings.py` | persisted preferences and tunables with defaults (`~/.config/archer/archer-qt.conf`) |
| `archerqt/catalog.py` | translatable vocabulary: profiles, capabilities, wake sources, USB levels, chart ranges |
| `archerqt/bus.py` | D-Bus bridge generated from the XML: one QObject per interface, `Telemetry.cpuTemp`, `Bus.call()` |
| `archerqt/history.py` | fixed-memory multi-resolution history for the temperature chart |
| `archerqt/tray.py` | tray icon: open/hide, quick profile switch, temperatures in the tooltip |
| `archerqt/controller.py` | visibility → telemetry cadence; session-side reactions (PipeWire restart) |
| `archerqt/app.py` | wiring and `main()` |
| `qml/Main.qml` | sidebar and lazily created pages |
| `qml/pages/` | Overview · Performance · Lighting · Battery & Power · Display & Audio · System |
| `qml/components/` | Gauge (Shapes), Sparkline, BoundSwitch / BoundSlider (revert on daemon error), ChoiceButton, KeyboardPreview, Card, Hint, Eyebrow, Swatch |
| `translations/` | Qt Linguist catalogues |

## Conventions

* Python is PEP 8 / snake_case. Anything QML sees — Qt properties, slots,
  signals — is camelCase, the Qt convention.
* No literal words in QML except through `qsTr()`; identifiers coming from
  the daemon are mapped to labels in `catalog.py`, once.
* No literal paths: `paths.py` resolves them. No literal thresholds or
  cadences in QML: `settings.py` owns them with defaults.
* Sizes in QML are multiples of `Kirigami.Units`; colours come from
  `Kirigami.Theme`, so the panel follows the system colour scheme.
* Controls bind to daemon properties and apply as they move; a refused
  change reverts the control (`BoundSwitch`, `BoundSlider`, `ChoiceButton`).

## Running

From the tree: `python3 gui-qt/archer_qt.py`. Against a development
daemon without touching the installed one:

    python3 gui/archer_daemon.py --session-bus &
    ARCHER_BUS=session python3 gui-qt/archer_qt.py

Dependencies on Arch: `pyside6 qt6-declarative kirigami qqc2-desktop-style`.

## Behaviour and cost

Telemetry cadence: hidden → `Unsubscribe`; visible → `Subscribe(1000)`
(both configurable in the settings file). Measured on the PHN16S-71
(Plasma 6, Wayland, OpenGL): ~70 MB private RSS, 0 % CPU hidden, ~2 % on
the Overview page, ~0.3 % elsewhere. The temperature history is three ring
buffers (1 s × 10 min, 10 s × 1 h, 60 s × 1 day) of about 20 KB in total.
