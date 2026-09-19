"""
Entry point: builds the Qt application, wires the D-Bus bridge, settings,
catalog, history and controller into the QML engine, and runs.

Command line:
    --hidden    start in the tray without showing the window
Only one panel runs per session: launching it again shows the existing
window (io.github.archer.Panel on the session bus).
Environment:
    ARCHER_PREFIX   where the daemon files are installed (default /opt/archer)
    ARCHER_BUS      "session" to talk to `archer_daemon.py --session-bus`
    QT_QUICK_CONTROLS_STYLE  overrides the automatic style choice
"""

import logging
import os
import signal
import sys

from PySide6.QtCore import QLocale, QTimer, QTranslator, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from archerqt import __version__, paths
from archerqt.bus import ArcherBus
from archerqt.camera import Camera
from archerqt.catalog import Catalog
from archerqt.display_modes import DisplayModes
from archerqt.controller import AppController
from archerqt.history import History
from archerqt.settings import ORGANIZATION, AppSettings
from archerqt.single_instance import SingleInstance

logger = logging.getLogger("archer-qt")

APP_NAME = "Archer"
DESKTOP_FILE = "io.github.archer"
PLASMA_STYLE = "org.kde.desktop"
FALLBACK_STYLE = "Fusion"


def _choose_style():
    """Breeze-styled controls on Plasma, Fusion elsewhere, unless the
    user already chose."""
    if "QT_QUICK_CONTROLS_STYLE" in os.environ:
        return
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    QQuickStyle.setStyle(PLASMA_STYLE if desktop.startswith("KDE") else FALLBACK_STYLE)


def _install_translator(app):
    translator = QTranslator(app)
    if translator.load(QLocale(), "archer", "_", str(paths.translations_dir())):
        app.installTranslator(translator)
    return translator                            # must outlive the app


def _let_python_handle_sigint(app):
    """Ctrl-C quits cleanly instead of being swallowed by the Qt loop."""
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    keepalive = QTimer(app)
    keepalive.timeout.connect(lambda: None)
    keepalive.start(500)


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    argv = list(sys.argv if argv is None else argv)

    _choose_style()
    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationVersion(__version__)
    QApplication.setOrganizationName(ORGANIZATION)
    QApplication.setDesktopFileName(DESKTOP_FILE)
    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(paths.asset("archer.svg")))
    _let_python_handle_sigint(app)
    _translator = _install_translator(app)   # noqa: F841 — keep referenced

    # One panel per session. A second launch raises the first one's window
    # and exits before touching the daemon or the tray.
    dev = os.environ.get("ARCHER_BUS") == "session"
    instance = SingleInstance(name=SingleInstance.NAME + (".Dev" if dev else ""),
                              path=SingleInstance.PATH + ("/Dev" if dev else ""))
    if not instance.acquire():
        instance.activate_existing()
        return 0

    # Context objects are not owned by the engine; everything handed to
    # QML must stay referenced here for the life of the application.
    settings = AppSettings()
    catalog = Catalog()
    bus = ArcherBus()
    history = History()
    panel_modes = DisplayModes()
    camera = Camera()
    controller = AppController(bus, settings, catalog)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("Bus", bus)
    context.setContextProperty("App", controller)
    context.setContextProperty("Settings", settings)
    context.setContextProperty("Catalog", catalog)
    context.setContextProperty("History", history)
    context.setContextProperty("Panel", panel_modes)
    context.setContextProperty("Camera", camera)
    for name, interface in bus.interfaces.items():
        context.setContextProperty(name, interface)
    engine.load(QUrl.fromLocalFile(str(paths.qml_dir() / "Main.qml")))
    if not engine.rootObjects():
        logger.error("Main.qml failed to load")
        return 1

    window = engine.rootObjects()[0]
    controller.attach_window(window)
    instance.serve(controller.showWindow)
    if "--hidden" not in argv:
        window.show()

    exit_code = app.exec()
    # Tear the QML tree down while the context objects still exist, or
    # every binding logs "Cannot read property of null" on exit.
    del engine
    return exit_code
