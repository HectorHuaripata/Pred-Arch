"""
Small shared pieces: the typed error, colour helpers, XML loading.
"""

import logging
from pathlib import Path

from gi.repository import Gio

from archer_control.constants import ERROR_PREFIX, XML_CANDIDATES, XML_NAME

logger = logging.getLogger("archer-daemon")


class ControlError(Exception):
    """A typed D-Bus error. `kind` is the suffix after ERROR_PREFIX."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.name = ERROR_PREFIX + kind


def load_node_info(xml_path=None):
    candidates = [Path(xml_path)] if xml_path else XML_CANDIDATES
    for path in candidates:
        if path.is_file():
            return Gio.DBusNodeInfo.new_for_xml(path.read_text())
    raise FileNotFoundError(
        f"{XML_NAME} not found in {[str(p) for p in candidates]}")


def hex_to_rgb(value):
    v = str(value).lstrip("#")
    if len(v) != 6:
        return (0, 0, 0)
    try:
        return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))
    except ValueError:
        return (0, 0, 0)


def rgb_to_hex(rgb):
    r, g, b = rgb
    return f"{r:02x}{g:02x}{b:02x}"


def byte_arg(value, name):
    if not 0 <= int(value) <= 255:
        raise ControlError("InvalidArgument", f"{name} must be 0-255")
    return int(value)


# ---------------------------------------------------------------------------
# Property store
# ---------------------------------------------------------------------------
