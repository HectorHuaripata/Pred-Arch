# Archer control panel (Qt 6 / QML)

The v3 GUI. Talks only to `io.github.archer.Control1` (see
`docs/DBUS_V2.md`); the daemon must be 2.1+ with `archer_control.py`.

```
archer_qt.py            entry point; --hidden starts in the tray
archerqt/bus.py         XML → one QObject per D-Bus interface, Qt properties
                        in lowerCamel (Telemetry.cpuTemp), Bus.call()
archerqt/app.py         window, tray (QSystemTrayIcon), telemetry cadence by
                        visibility, pipewire restart on NoiseSuppression
qml/Main.qml            sidebar + lazily created pages
qml/pages/              Overview · Performance · Lighting · Battery & Power ·
                        Display & Audio · System
qml/components/         Gauge (Shapes), Sparkline, BoundSwitch/BoundSlider
                        (revert on daemon error), ChoiceButton, KeyboardPreview
```

Dependencies on Arch: `pyside6 qt6-declarative kirigami qqc2-desktop-style`.

Run from the tree: `python3 gui-qt/archer_qt.py`.

Telemetry cadence: hidden → `Unsubscribe`; visible → `Subscribe(1000)`.
Measured on the PHN16S-71 (Plasma 6, Wayland, OpenGL): 71 MB private RSS,
0 % CPU hidden, ~2.4 % on the Overview page, ~0.3 % on other pages.
