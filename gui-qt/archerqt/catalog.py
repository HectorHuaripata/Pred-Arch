"""
Translatable vocabulary shared by every page.

The daemon speaks in identifiers (`balanced-performance`, `XHCI`,
`keyboard_per_zone`); people read words. This is the one place that maps
between them, so a label is never spelled twice and every string goes
through Qt's translator. QML reaches it as `Catalog`.
"""

from PySide6.QtCore import Property, QCoreApplication, QObject, Slot


def _tr(text):
    """Deferred translation; resolved when the label is requested."""
    return QCoreApplication.translate("Catalog", text)


# platform_profile value -> (label, theme icon)
PROFILES = {
    "low-power": ("Eco", "battery-low"),
    "quiet": ("Quiet", "audio-volume-muted"),
    "balanced": ("Balanced", "speedometer"),
    "balanced-performance": ("Balanced+", "speedometer"),
    "performance": ("Performance", "flag-red"),
}

# Feature identifiers the daemon reports in System.Features.
CAPABILITIES = {
    "thermal_profiles": "Performance profiles",
    "fan_control": "Fan control",
    "fan_speed": "Fan control",
    "keyboard_per_zone": "Per-zone keyboard colour",
    "keyboard_effects": "Keyboard effects",
    "battery_limiter": "Charge limit",
    "battery_calibration": "Battery calibration",
    "battery_info": "Battery readings",
    "usb_charging": "USB charging while asleep",
    "lcd_override": "LCD override",
    "boot_animation_sound": "Boot animation & sound",
    "backlight_timeout": "Keyboard backlight timeout",
    "display_mode": "GPU mode switching",
    "game_mode": "Game mode",
    "usb_wake_policy": "Wake sources",
    "firmware_info": "Firmware info",
}

# ACPI wake device names worth showing. /proc/acpi/wakeup also lists every
# PCIe root port (RPxx, PXSX, TRPx), which mean nothing to a person.
WAKE_SOURCES = {
    "XHCI": "USB (chipset)",
    "TXHC": "USB (Thunderbolt)",
    "XDCI": "USB device mode",
    "GLAN": "Ethernet",
    "CNVW": "Wi-Fi",
    "HDAS": "Audio",
    "AWAC": "ACPI wake alarm",
    "TDM0": "Thunderbolt 0",
    "TDM1": "Thunderbolt 1",
    "LID0": "Lid",
    "PBTN": "Power button",
    "SLPB": "Sleep button",
}

# Battery.UsbCharging levels the firmware accepts: percent floor, 0 = off.
USB_CHARGING_LEVELS = ((0, "Off"), (10, "Until 10 %"), (20, "Until 20 %"), (30, "Until 30 %"))

# Display.Mode choices with a one-line explanation.
DISPLAY_MODES = (
    ("hybrid", "Hybrid", "Integrated GPU by default, NVIDIA on demand"),
    ("integrated", "Integrated", "NVIDIA off, longest battery life"),
    ("nvidia", "NVIDIA", "Discrete GPU always"),
)

# linuwu_sense module parameters the daemon may set.
MODPROBE_PARAMETERS = (("", "Auto-detect"), ("nitro_v4", "nitro_v4"),
                       ("predator_v4", "predator_v4"), ("enable_all", "enable_all"))

# Temperature chart ranges, in seconds.
CHART_RANGES = ((300, "5 min"), (600, "10 min"), (1800, "30 min"), (3600, "1 hour"), (86400, "1 day"))

# Quick colours for the keyboard.
SWATCHES = ("#ffffff", "#ff3b30", "#ff9500", "#ffd60a", "#34c759",
            "#00c7be", "#0a84ff", "#5e5ce6", "#bf5af2", "#ff2d55")

# Ready-made profile -> button colour mappings. The factory mapping comes
# from the daemon (Lighting.ButtonDefaultColors), so it is not repeated
# here; "reset" uses Lighting.ResetButtonColors.
BUTTON_PRESETS = (
    ("traffic-light", "Traffic light", {
        "low-power": "#2ecc40", "quiet": "#a6e22e", "balanced": "#ffd60a",
        "balanced-performance": "#ff9500", "performance": "#ff3b30"}),
    ("cool-to-warm", "Cool to warm", {
        "low-power": "#0a84ff", "quiet": "#00c7be", "balanced": "#ffffff",
        "balanced-performance": "#ff9500", "performance": "#ff3b30"}),
    ("monochrome", "All white", {
        "low-power": "#ffffff", "quiet": "#ffffff", "balanced": "#ffffff",
        "balanced-performance": "#ffffff", "performance": "#ffffff"}),
)

BATTERY_STATUS = {
    "charging": "Charging",
    "discharging": "On battery",
    "full": "Full",
    "idle": "Plugged in, not charging",
    "unknown": "—",
}


class Catalog(QObject):
    """Lookup functions and lists for QML. Lists come back as
    [[value, label, …], …] so a Repeater can iterate them directly."""

    @Slot(str, result=str)
    def profileLabel(self, profile):
        entry = PROFILES.get(profile)
        return _tr(entry[0]) if entry else profile

    @Slot(str, result=str)
    def profileIcon(self, profile):
        entry = PROFILES.get(profile)
        return entry[1] if entry else "speedometer"

    @Slot(str, result=str)
    def capabilityLabel(self, feature):
        return _tr(CAPABILITIES.get(feature, feature))

    @Slot(str, result=str)
    def wakeSourceLabel(self, device):
        """"" for devices not worth showing."""
        label = WAKE_SOURCES.get(device)
        return _tr(label) if label else ""

    @Slot(str, result=str)
    def batteryStatusLabel(self, status):
        return _tr(BATTERY_STATUS.get(status, status))

    @Property("QVariantList", constant=True)
    def usbChargingLevels(self):
        return [[level, _tr(label)] for level, label in USB_CHARGING_LEVELS]

    @Property("QVariantList", constant=True)
    def displayModes(self):
        return [[mode, _tr(label), _tr(hint)] for mode, label, hint in DISPLAY_MODES]

    @Property("QVariantList", constant=True)
    def modprobeParameters(self):
        return [[value, _tr(label)] for value, label in MODPROBE_PARAMETERS]

    @Property("QVariantList", constant=True)
    def chartRanges(self):
        return [[seconds, _tr(label)] for seconds, label in CHART_RANGES]

    @Property("QVariantList", constant=True)
    def swatches(self):
        return list(SWATCHES)

    @Property("QVariantList", constant=True)
    def buttonPresets(self):
        """[[id, label, {profile: "#rrggbb"}], …]"""
        return [[preset_id, _tr(label), dict(colours)] for preset_id, label, colours in BUTTON_PRESETS]
