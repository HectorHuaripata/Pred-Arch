"""
Archer control panel — Qt 6 / QML front end for the Archer daemon.

Layout
------
paths.py       where the introspection XML, icons and translations live
settings.py    persisted user preferences and tunable parameters
catalog.py     translatable vocabulary shared by every page (profiles,
               capabilities, wake sources, chart ranges …)
bus.py         D-Bus bridge: one QObject per daemon interface, generated
               from the XML; Bus.call() for methods
history.py     fixed-memory multi-resolution history for the charts
tray.py        system tray icon and its menu
controller.py  what QML needs beyond D-Bus: window visibility → telemetry
               cadence, session-side reactions (pipewire restart)
app.py         wiring and the entry point

Naming
------
Python code follows PEP 8 (snake_case). Anything QML sees — Qt properties,
slots, signals — is camelCase, because that is the Qt/QML convention and
QML property names must start with a lowercase letter.
"""

__version__ = "2.1.0"
