"""
Audio: the PipeWire noise-suppression filter file, and the codec card's
SOF DSP controls (speaker DRC, microphone beamformer and DRC, auto-mute).
"""

import os

from archer_control import alsa_dsp
from archer_control.common import ControlError, logger
from archer_control.constants import NOISE_CONF

SETTINGS_KEY = "audio_dsp"
FEATURE = "audio_dsp"

# settings key -> (ALSA control, kind)
DSP_SETTINGS = {
    "speaker_drc": (alsa_dsp.SPEAKER_DRC, "bool"),
    "auto_mute": (alsa_dsp.AUTO_MUTE, "enum"),      # "Enabled" / "Disabled"
    "mic_drc": (alsa_dsp.MIC_DRC, "bool"),
    "mic_beamforming": (alsa_dsp.MIC_BEAM, "bool"),
    "mic_beam_angle": (alsa_dsp.MIC_BEAM_ANGLE, "enum"),   # degrees as a string
}


class AudioInterface:
    """Value builder and setters for io.github.archer.Control1.Audio."""

    # -- detection and restore (called from the service constructor) ------

    def _init_audio_dsp(self):
        """Find the DSP card, advertise the feature, reapply saved values.
        alsa-restore normally keeps them across reboots; the reapply covers
        an unclean shutdown."""
        self._dsp = alsa_dsp.SofDsp.detect()
        if self._dsp is None:
            return
        if FEATURE not in self.hw.features:
            self.hw.features.append(FEATURE)
        saved = self.hw.settings.get(SETTINGS_KEY) or {}
        for key, value in saved.items():
            control, kind = DSP_SETTINGS.get(key, (None, None))
            if control is None or not self._dsp.has(control):
                continue
            ok = self._dsp.set_bool(control, value) if kind == "bool" else self._dsp.set_enum(control, value)
            if not ok:
                logger.warning(f"Could not restore audio DSP setting {key}={value}")

    def _dsp_or_unsupported(self, control):
        dsp = getattr(self, "_dsp", None)
        if dsp is None or not dsp.has(control):
            raise ControlError("Unsupported", "this audio DSP control is not present on this machine")
        return dsp

    def _remember_dsp(self, key, value):
        saved = dict(self.hw.settings.get(SETTINGS_KEY) or {})
        saved[key] = value
        self.hw.settings.set(SETTINGS_KEY, saved)

    # -- values -------------------------------------------------------------

    def _audio_values(self):
        values = {
            # The daemon only renames the filter file; its presence is the state.
            "NoiseSuppression": os.path.exists(NOISE_CONF),
            "NoiseSuppressionAvailable": os.path.exists(NOISE_CONF) or os.path.exists(NOISE_CONF + ".disabled"),
            "DspAvailable": False,
            "SpeakerDrc": False, "AutoMute": False, "MicDrc": False,
            "MicBeamforming": False, "MicBeamAngle": 0, "MicBeamAngles": [],
        }
        dsp = getattr(self, "_dsp", None)
        if dsp is None:
            return values
        values["DspAvailable"] = True
        if dsp.has(alsa_dsp.SPEAKER_DRC):
            values["SpeakerDrc"] = bool(dsp.get_bool(alsa_dsp.SPEAKER_DRC))
        if dsp.has(alsa_dsp.MIC_DRC):
            values["MicDrc"] = bool(dsp.get_bool(alsa_dsp.MIC_DRC))
        if dsp.has(alsa_dsp.MIC_BEAM):
            values["MicBeamforming"] = bool(dsp.get_bool(alsa_dsp.MIC_BEAM))
        if dsp.has(alsa_dsp.MIC_BEAM_ANGLE):
            items, current = dsp.get_enum(alsa_dsp.MIC_BEAM_ANGLE)
            angles = [int(i) for i in items if i.lstrip("-").isdigit()]
            values["MicBeamAngles"] = angles
            values["MicBeamAngle"] = angles[current] if 0 <= current < len(angles) else 0
        if dsp.has(alsa_dsp.AUTO_MUTE):
            items, current = dsp.get_enum(alsa_dsp.AUTO_MUTE)
            values["AutoMute"] = 0 <= current < len(items) and items[current] == "Enabled"
        return values

    def _audio_refresh(self):
        self.store.update(self._iface("Audio"), self._audio_values())

    # -- PipeWire filter ----------------------------------------------------

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
        self._audio_refresh()

    # -- SOF DSP ------------------------------------------------------------

    def _set_dsp_bool(self, key, control, enabled):
        dsp = self._dsp_or_unsupported(control)
        if not dsp.set_bool(control, bool(enabled)):
            raise ControlError("HardwareFailure", f"amixer refused {control}")
        self._remember_dsp(key, bool(enabled))
        self._audio_refresh()

    def _m_Audio_SetSpeakerDrc(self, sender, enabled):
        self._set_dsp_bool("speaker_drc", alsa_dsp.SPEAKER_DRC, enabled)

    def _m_Audio_SetMicDrc(self, sender, enabled):
        self._set_dsp_bool("mic_drc", alsa_dsp.MIC_DRC, enabled)

    def _m_Audio_SetMicBeamforming(self, sender, enabled):
        self._set_dsp_bool("mic_beamforming", alsa_dsp.MIC_BEAM, enabled)

    def _m_Audio_SetAutoMute(self, sender, enabled):
        dsp = self._dsp_or_unsupported(alsa_dsp.AUTO_MUTE)
        label = "Enabled" if enabled else "Disabled"
        if not dsp.set_enum(alsa_dsp.AUTO_MUTE, label):
            raise ControlError("HardwareFailure", "amixer refused Auto-Mute Mode")
        self._remember_dsp("auto_mute", label)
        self._audio_refresh()

    def _m_Audio_SetMicBeamAngle(self, sender, degrees):
        dsp = self._dsp_or_unsupported(alsa_dsp.MIC_BEAM_ANGLE)
        items, _ = dsp.get_enum(alsa_dsp.MIC_BEAM_ANGLE)
        label = str(int(degrees))
        if label not in items:
            raise ControlError("InvalidArgument", f"angle must be one of {items}")
        if not dsp.set_enum(alsa_dsp.MIC_BEAM_ANGLE, label):
            raise ControlError("HardwareFailure", "amixer refused the beam angle")
        self._remember_dsp("mic_beam_angle", label)
        self._audio_refresh()
