"""
Lighting: keyboard zones and effects, mode-button LED, lid logo, backlight timeout.
"""

from archer_control.common import ControlError, byte_arg, hex_to_rgb, rgb_to_hex
from archer_control.constants import DIRECTION_TO_WIRE, WIRE_TO_DIRECTION, WMI_EFFECTS

class LightingInterface:
    """Value builder and setters for io.github.archer.Control1.Lighting.

    Every setter applies immediately through the LightingCoalescer
    (self._lighting): the first write of a burst is synchronous so its
    error reaches the caller, later ones replace each other.
    """

    def _backend(self):
        if getattr(self.hw, "ene_ready", False):
            return "ene"
        if "keyboard_per_zone" in self.hw.features or "keyboard_effects" in self.hw.features:
            return "wmi"
        return "none"

    def _effect_names(self):
        if self.ene is not None and hasattr(self.ene, "EFFECTS"):
            return [name for name, _ in self.ene.EFFECTS]
        return list(WMI_EFFECTS)

    def _lighting_values(self):
        st = self.hw.settings
        pz = st.get("per_zone_mode") or {}
        fx = st.get("four_zone_mode") or {}
        names = self._effect_names()
        last = st.get("last_keyboard_mode")
        if last == "off":
            effect = "off"
        elif last == "effect":
            idx = int(fx.get("mode", 0))
            effect = names[idx] if 0 <= idx < len(names) else "static"
        else:
            effect = "static"
        brightness = int((fx if last == "effect" else pz).get("brightness", pz.get("brightness", 100)))
        zones = [hex_to_rgb(pz.get(f"zone{i}", "ffffff")) for i in range(1, 5)]
        defaults = dict(getattr(self.ene, "PROFILE_COLOURS", {}) or {}) if self.ene is not None else {}
        button_colours = dict(defaults)
        button_colours.update(st.get("button_colours") or {})
        fixed = st.get("button_fixed_colour") or "ffffff"
        logo = st.get("logo") or {}
        return {
            "Backend": self._backend(),
            "Zones": zones,
            "Brightness": max(0, min(255, brightness)),
            "Effect": effect,
            "EffectChoices": names,
            "EffectColor": (int(fx.get("red", 0)), int(fx.get("green", 0)), int(fx.get("blue", 255))),
            "EffectSpeed": max(0, min(255, int(fx.get("speed", 5)))),
            "EffectDirection": WIRE_TO_DIRECTION.get(int(fx.get("direction", 2)), "right"),
            "ButtonFollowsProfile": bool(st.get("button_follows_profile", True)),
            "ButtonColors": {k: hex_to_rgb(v) for k, v in button_colours.items()},
            "ButtonDefaultColors": {k: hex_to_rgb(v) for k, v in defaults.items()},
            "ButtonColor": hex_to_rgb(fixed),
            "LogoColor": hex_to_rgb(logo.get("colour", "ffffff")),
            "LogoBrightness": max(0, min(255, int(logo.get("brightness", 100)))),
            "BacklightTimeout": bool(self.hw.get_backlight_timeout()),
        }


    def _lighting_refresh(self):
        self.store.update(self._iface("Lighting"), self._lighting_values())

    def _m_Lighting_SetZones(self, sender, zones, brightness):
        if len(zones) != 4:
            raise ControlError("InvalidArgument", "exactly four zones")
        hexes = [rgb_to_hex(tuple(byte_arg(c, "colour") for c in z)) for z in zones]
        b = byte_arg(brightness, "brightness")

        def write():
            if not self.hw.set_per_zone_mode(*hexes, b):
                raise ControlError("HardwareFailure", "per-zone write failed")
            self.hw.settings.set("per_zone_mode", {
                "zone1": hexes[0], "zone2": hexes[1], "zone3": hexes[2],
                "zone4": hexes[3], "brightness": b})
            self.hw.settings.set("last_keyboard_mode", "per_zone")
            self._lighting_refresh()

        self._lighting.request("keyboard", write)

    def _m_Lighting_SetZoneMask(self, sender, zone_mask, color):
        mask = int(zone_mask) & 0x0F
        if not mask:
            raise ControlError("InvalidArgument", "zone_mask selects no zone")
        rgb = tuple(byte_arg(c, "colour") for c in color)
        pz = dict(self.hw.settings.get("per_zone_mode") or {})
        hexes = [pz.get(f"zone{i}", "ffffff") for i in range(1, 5)]
        for i in range(4):
            if mask & (1 << i):
                hexes[i] = rgb_to_hex(rgb)
        b = int(pz.get("brightness", 100))
        self._m_Lighting_SetZones(sender, [hex_to_rgb(h) for h in hexes], b)

    def _m_Lighting_SetBrightness(self, sender, brightness):
        b = byte_arg(brightness, "brightness")
        st = self.hw.settings
        if st.get("last_keyboard_mode") == "effect":
            fx = dict(st.get("four_zone_mode") or {})
            fx["brightness"] = b
            self._apply_effect(fx)
        else:
            pz = dict(st.get("per_zone_mode") or {})
            zones = [hex_to_rgb(pz.get(f"zone{i}", "ffffff")) for i in range(1, 5)]
            self._m_Lighting_SetZones(sender, zones, b)

    def _apply_effect(self, fx):
        def write():
            ok = self.hw.set_four_zone_mode(
                fx["mode"], fx["speed"], fx["brightness"], fx["direction"],
                fx["red"], fx["green"], fx["blue"])
            if not ok:
                raise ControlError("HardwareFailure", "effect write failed")
            self.hw.settings.set("four_zone_mode", fx)
            self.hw.settings.set("last_keyboard_mode", "effect")
            self._lighting_refresh()

        self._lighting.request("keyboard", write)

    def _m_Lighting_SetEffect(self, sender, effect, brightness, color, speed, direction):
        names = self._effect_names()
        lowered = [n.lower() for n in names]
        if effect.lower() not in lowered:
            raise ControlError("InvalidArgument", f"effect must be one of {names}")
        if direction not in DIRECTION_TO_WIRE:
            raise ControlError("InvalidArgument", "direction must be 'left' or 'right'")
        r, g, b = (byte_arg(c, "colour") for c in color)
        fx = {
            "mode": lowered.index(effect.lower()),
            "speed": max(0, min(9, int(speed))),
            "brightness": byte_arg(brightness, "brightness"),
            "direction": DIRECTION_TO_WIRE[direction],
            "red": r, "green": g, "blue": b,
        }
        self._apply_effect(fx)

    def _m_Lighting_SetOff(self, sender):
        ene = self._ene()

        def write():
            if ene is not None:
                ene.set_off()
            else:
                pz = self.hw.settings.get("per_zone_mode") or {}
                if not self.hw.set_per_zone_mode("000000", "000000", "000000", "000000",
                                                 int(pz.get("brightness", 0))):
                    raise ControlError("HardwareFailure", "keyboard off write failed")
            self.hw.settings.set("last_keyboard_mode", "off")
            self._lighting_refresh()

        self._lighting.request("keyboard", write)

    def _m_Lighting_SetButtonFollowsProfile(self, sender, enabled):
        self.hw.settings.set("button_follows_profile", bool(enabled))
        self._resync_button()          # applies the mapping, or the fixed colour
        self._lighting_refresh()

    def _m_Lighting_SetButtonColor(self, sender, profile, color):
        ene = self._ene()
        if ene is None:
            raise ControlError("Unsupported", "button LED needs the ENE backend")
        rgb = tuple(byte_arg(c, "colour") for c in color)
        colours = dict(self.hw.settings.get("button_colours") or {})
        colours[str(profile)] = rgb_to_hex(rgb)
        self.hw.settings.set("button_colours", colours)
        if profile == self.hw.get_thermal_profile():
            self._lighting.request("button", lambda: ene.set_button(rgb_to_hex(rgb)))
        self._lighting_refresh()

    def _m_Lighting_SetButtonColors(self, sender, colors):
        ene = self._ene()
        if ene is None:
            raise ControlError("Unsupported", "button LED needs the ENE backend")
        known = set(self.hw.get_thermal_profile_choices())
        colours = dict(self.hw.settings.get("button_colours") or {})
        for profile, color in dict(colors).items():
            if profile in known:
                colours[str(profile)] = rgb_to_hex(tuple(byte_arg(c, "colour") for c in color))
        self.hw.settings.set("button_colours", colours)
        self._resync_button()
        self._lighting_refresh()

    def _m_Lighting_ResetButtonColors(self, sender):
        if self._ene() is None:
            raise ControlError("Unsupported", "button LED needs the ENE backend")
        self.hw.settings.set("button_colours", {})
        self._resync_button()
        self._lighting_refresh()

    def _m_Lighting_SetButtonFixedColor(self, sender, color):
        ene = self._ene()
        if ene is None:
            raise ControlError("Unsupported", "button LED needs the ENE backend")
        colour = rgb_to_hex(tuple(byte_arg(c, "colour") for c in color))

        def write():
            ene.set_button(colour)                 # raises on failure: nothing saved
            self.hw.settings.set("button_fixed_colour", colour)
            self.hw.settings.set("button_follows_profile", False)
            self._lighting_refresh()

        self._lighting.request("button", write)

    def _resync_button(self):
        """Re-colour the button after a mapping change (coalesced)."""
        profile = self.hw.get_thermal_profile()
        self._lighting.request("button", lambda: self.hw._sync_button_led(profile))

    def _m_Lighting_SetLogo(self, sender, color, brightness):
        ene = self._ene()
        if ene is None:
            raise ControlError("Unsupported", "lid logo needs the ENE backend")
        rgb = tuple(byte_arg(c, "colour") for c in color)
        b = byte_arg(brightness, "brightness")

        def write():
            ene.set_logo(rgb_to_hex(rgb), b)
            self.hw.settings.set("logo", {"colour": rgb_to_hex(rgb), "brightness": b})
            self._lighting_refresh()

        self._lighting.request("logo", write)

    def _m_Lighting_SetBacklightTimeout(self, sender, enabled):
        if not self.hw.set_backlight_timeout(bool(enabled)):
            raise ControlError("HardwareFailure", "backlight_timeout write failed")
        self.hw.settings.set("backlight_timeout", bool(enabled))
        self._lighting_refresh()

