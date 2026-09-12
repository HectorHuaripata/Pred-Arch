"""
Display: hybrid-graphics mode through envycontrol.
"""

import threading

from gi.repository import GLib

from archer_control.common import ControlError, logger

class DisplayInterface:
    """Value builder and SetMode for io.github.archer.Control1.Display."""

    def _display_values(self):
        if "display_mode" not in self.hw.features:
            return {"Mode": "unknown", "Choices": [], "HasMux": False, "ActiveGpu": "unknown"}
        dm = self.hw.get_display_mode() or {}
        mux = self.hw.detect_mux() or {}
        return {
            "Mode": str(dm.get("mode", "unknown")),
            "Choices": list(dm.get("available_modes", [])),
            "HasMux": bool(mux.get("has_mux", False)),
            "ActiveGpu": str(mux.get("active_gpu", "unknown")),
        }


    def _m_Display_SetMode(self, sender, mode):
        choices = self.store.value(self._iface("Display"), "Choices") or []
        if mode not in choices:
            raise ControlError("InvalidArgument", f"mode must be one of {choices}")
        if self._display_busy:
            raise ControlError("Busy", "a display mode change is already running")
        self._display_busy = True

        def worker():
            try:
                result = self.hw.set_display_mode(mode)
                if not result.get("success"):
                    logger.warning(f"Display.SetMode({mode}): {result.get('error')}")
            finally:
                self._display_busy = False
                GLib.idle_add(lambda: (self.store.update(
                    self._iface("Display"), self._display_values()), False)[1])

        threading.Thread(target=worker, name="display-mode", daemon=True).start()

