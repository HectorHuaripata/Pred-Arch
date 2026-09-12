"""
Resource lookup.

The panel runs from three places: the git tree (gui-qt/ next to dbus/ and
gui/assets/), an installed prefix (default /opt/archer, where the
installer puts qt/ next to the daemon files), or wherever ARCHER_PREFIX
points. Nothing here is hardcoded to one of them; every lookup walks the
candidate roots in order and returns the first hit.
"""

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
GUI_DIR = PACKAGE_DIR.parent                   # gui-qt/ in the tree, qt/ installed
SOURCE_TREE = GUI_DIR.parent                   # repository root when running from git

DEFAULT_PREFIX = Path("/opt/archer")
CONTRACT_XML = "io.github.archer.Control1.xml"


def install_prefix() -> Path:
    """Directory holding the daemon files (and qt/ for this panel)."""
    return Path(os.environ.get("ARCHER_PREFIX", DEFAULT_PREFIX))


def _first_existing(candidates):
    for path in candidates:
        if path.exists():
            return path
    return None


def qml_dir() -> Path:
    """Directory holding Main.qml."""
    return GUI_DIR / "qml"


def contract_xml() -> Path:
    """The D-Bus introspection XML, the single source of truth for the API."""
    found = _first_existing((
        GUI_DIR / CONTRACT_XML,
        SOURCE_TREE / "dbus" / CONTRACT_XML,
        install_prefix() / CONTRACT_XML,
    ))
    if found is None:
        raise FileNotFoundError(
            f"{CONTRACT_XML} not found next to the panel, in the source tree, "
            f"or under {install_prefix()} (set ARCHER_PREFIX)")
    return found


def asset(name: str) -> str:
    """Path of an icon or image, or "" when absent (callers fall back to
    a theme icon)."""
    found = _first_existing((
        GUI_DIR / "assets" / name,
        SOURCE_TREE / "gui" / "assets" / name,
        install_prefix() / "assets" / name,
    ))
    return str(found) if found else ""


def translations_dir() -> Path:
    """Directory the QTranslator loads archer_<locale>.qm from."""
    return GUI_DIR / "translations"
