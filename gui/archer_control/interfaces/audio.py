"""
Audio: PipeWire noise-suppression filter file.
"""

import os

from archer_control.common import ControlError
from archer_control.constants import NOISE_CONF


class AudioInterface:
    """Value builder and SetNoiseSuppression for io.github.archer.Control1.Audio."""

    def _audio_values(self):
        # The daemon only renames the filter file; its presence is the state.
        return {"NoiseSuppression": os.path.exists(NOISE_CONF)}

    def _m_Audio_SetNoiseSuppression(self, sender, enabled):
        disabled = NOISE_CONF + ".disabled"
        if not os.path.exists(NOISE_CONF) and not os.path.exists(disabled):
            # Nothing to rename: the audio-enhance installer module was never
            # run on this machine. Say so instead of silently reverting.
            raise ControlError(
                "Unsupported",
                "noise suppression filter is not installed; run "
                "`./install.sh --modules audio-enhance` to add the RNNoise "
                "PipeWire filter")
        try:
            if enabled:
                if os.path.exists(disabled) and not os.path.exists(NOISE_CONF):
                    os.rename(disabled, NOISE_CONF)
            elif os.path.exists(NOISE_CONF):
                os.rename(NOISE_CONF, disabled)
        except OSError as e:
            raise ControlError("HardwareFailure", str(e))
        self.hw.settings.set("audio_enhancement", {"noise_suppression": bool(enabled)})
        # The client that sees this flip restarts pipewire in its own session.
        self.store.update(self._iface("Audio"), {"NoiseSuppression": os.path.exists(NOISE_CONF)})
