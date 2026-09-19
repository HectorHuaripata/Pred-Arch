"""
Audio DSP controls exposed by the Intel SOF firmware through ALSA.

On the Predator Helios Neo 16S AI (Realtek ALC245 behind Intel SOF) the
codec card carries processing blocks that run inside the DSP — speaker
dynamic-range compression, a 4-microphone beamformer with a steerable
angle, microphone DRC — plus the codec's headphone auto-mute. They are
plain ALSA mixer controls, so they are read and written with `amixer`.
That is a subprocess, which the daemon otherwise avoids; it is acceptable
here because these are cold-path operations (once at startup, once per
user action), never sampled.

Nothing here is Acer-specific: any SOF topology that exposes the same
control names gets the same features, and a card without them simply
reports the DSP as unavailable.
"""

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger("archer-daemon")

# Control names as the SOF topology publishes them.
SPEAKER_DRC = "Post Mixer Analog Playback DRC switch"
MIC_DRC = "Dmic0 Capture DRC switch"
MIC_BEAM = "Dmic0 Capture TDFB beam switch"
MIC_BEAM_ANGLE = "Dmic0 Capture TDFB angle set enum"
AUTO_MUTE = "Auto-Mute Mode"

# The card is recognised by the beamformer control; the others are
# optional and reported individually.
REQUIRED = (MIC_BEAM,)
ALL = (SPEAKER_DRC, MIC_DRC, MIC_BEAM, MIC_BEAM_ANGLE, AUTO_MUTE)

AMIXER_TIMEOUT_S = 5
_VALUES_RE = re.compile(r":\s*values=(.+)$", re.M)
_ITEM_RE = re.compile(r"Item #(\d+) '([^']*)'")


class SofDsp:
    """Mixer access for one card. Construct with detect()."""

    def __init__(self, card_index):
        self.card = card_index
        self.controls = set()
        for name in ALL:
            if self._cget(name) is not None:
                self.controls.add(name)

    @classmethod
    def detect(cls):
        """The first card that has the beamformer control, else None."""
        for card_dir in sorted(Path("/proc/asound").glob("card[0-9]*")):
            index = int(card_dir.name[4:])
            probe = cls._run(["-c", str(index), "cget", f"name={MIC_BEAM}"])
            if probe is not None:
                dsp = cls(index)
                logger.info(f"Audio DSP controls on card {index}: {sorted(dsp.controls)}")
                return dsp
        return None

    def has(self, name):
        return name in self.controls

    # -- typed accessors ---------------------------------------------------

    def get_bool(self, name):
        out = self._cget(name)
        if out is None:
            return None
        m = _VALUES_RE.search(out)
        return m.group(1).strip().split(",")[0] == "on" if m else None

    def set_bool(self, name, value):
        return self._cset(name, "on" if value else "off")

    def get_enum(self, name):
        """(items, current_index) for an ENUMERATED control."""
        out = self._cget(name)
        if out is None:
            return [], -1
        items = [label for _, label in sorted(((int(i), lbl) for i, lbl in _ITEM_RE.findall(out)))]
        m = _VALUES_RE.search(out)
        try:
            current = int(m.group(1).strip().split(",")[0]) if m else -1
        except ValueError:
            current = -1
        return items, current

    def set_enum(self, name, item_label):
        return self._cset(name, str(item_label))

    # -- amixer plumbing --------------------------------------------------

    def _cget(self, name):
        return self._run(["-c", str(self.card), "cget", f"name={name}"])

    def _cset(self, name, value):
        return self._run(["-c", str(self.card), "cset", f"name={name}", value]) is not None

    @staticmethod
    def _run(args):
        try:
            result = subprocess.run(["amixer", *args], capture_output=True, text=True,
                                    timeout=AMIXER_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.warning(f"amixer {' '.join(args)}: {e}")
            return None
        return result.stdout if result.returncode == 0 else None
