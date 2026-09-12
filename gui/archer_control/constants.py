"""
Names, paths, tunables and the polkit / feature tables of contract v2.

Everything a packager or a port to another model might need to change is
here; the rest of the package refers to these names.
"""

from pathlib import Path

BUS_NAME = "io.github.archer.Control1"
OBJECT_PATH = "/io/github/archer/Control1"
ERROR_PREFIX = BUS_NAME + ".Error."
PROPS_IFACE = "org.freedesktop.DBus.Properties"

XML_NAME = "io.github.archer.Control1.xml"
# The introspection XML is looked up next to the daemon files (installed
# layout) and in ../dbus (repository layout).
_DAEMON_DIR = Path(__file__).resolve().parent.parent
XML_CANDIDATES = (
    _DAEMON_DIR / XML_NAME,
    _DAEMON_DIR.parent / "dbus" / XML_NAME,
)

# Sampling bounds for Telemetry.Subscribe, in ms.
INTERVAL_MIN_MS = 250
INTERVAL_MAX_MS = 5000
# Battery does not move faster than this, whatever the subscriber asked for.
BATTERY_PERIOD_S = 10
# platform_profile changes are delivered by the kernel through sysfs_notify
# (POLLPRI on the file): the core notifies on every store, and linuwu_sense
# calls platform_profile_notify() from the hardware-button handler. Reading
# the attribute costs ~13 ms of CPU on this platform (the ACPI interpreter
# runs the WMI method), so it is read only when notified, plus a slow
# safety poll that also refreshes ENE readiness and fan-curve state.
PLATFORM_PROFILE_PATH = "/sys/firmware/acpi/platform_profile"
SLOW_POLL_S = 30
# Lighting setters coalesce bursts (a slider drag) into one write per device
# every this many ms. The ENE tolerates 20 Hz comfortably.
LIGHTING_FLUSH_MS = 50

DMI_BIOS_VERSION = "/sys/class/dmi/id/bios_version"
DEFAULT_PATH = "/usr/bin:/usr/local/bin"
NOISE_CONF = "/etc/pipewire/filter-chain.conf.d/archer-noise-suppress.conf"
MODPROBE_CONF = "/etc/modprobe.d/linuwu-sense.conf"
MODPROBE_PARAMS = ("nitro_v4", "predator_v4", "enable_all")
FAN_CURVE_TARGETS = ("cpu", "gpu")

# Effect names for the sysfs/WMI four_zone_mode fallback, indexed by the
# driver's mode number. The ENE backend supplies its own verified list.
WMI_EFFECTS = ("Static", "Breathing", "Neon", "Wave", "Shifting", "Zoom")

# Archer's direction convention on the wire: 1 = right to left, 2 = left to
# right. The contract uses words.
DIRECTION_TO_WIRE = {"left": 1, "right": 2}
WIRE_TO_DIRECTION = {1: "left", 2: "right"}

# "Interface.Method" -> polkit action. Same ids as v1 so the installed
# policy file keeps working. Methods not listed need no authorization.
POLKIT_ACTIONS = {
    "Thermal.SetProfile": "io.otectus.archer1.set-profile",
    "Thermal.SetFanSpeed": "io.otectus.archer1.set-fan",
    "Thermal.SetFanAuto": "io.otectus.archer1.set-fan",
    "Thermal.SetFanCurve": "io.otectus.archer1.set-fan",
    "Thermal.ClearFanCurve": "io.otectus.archer1.set-fan",
    "Battery.SetLimiter": "io.otectus.archer1.set-hardware",
    "Battery.SetCalibration": "io.otectus.archer1.set-hardware",
    "Battery.SetUsbCharging": "io.otectus.archer1.set-hardware",
    "Lighting.SetZones": "io.otectus.archer1.set-hardware",
    "Lighting.SetZoneMask": "io.otectus.archer1.set-hardware",
    "Lighting.SetBrightness": "io.otectus.archer1.set-hardware",
    "Lighting.SetEffect": "io.otectus.archer1.set-hardware",
    "Lighting.SetOff": "io.otectus.archer1.set-hardware",
    "Lighting.SetButtonFollowsProfile": "io.otectus.archer1.set-hardware",
    "Lighting.SetButtonColor": "io.otectus.archer1.set-hardware",
    "Lighting.SetButtonColors": "io.otectus.archer1.set-hardware",
    "Lighting.ResetButtonColors": "io.otectus.archer1.set-hardware",
    "Lighting.SetButtonFixedColor": "io.otectus.archer1.set-hardware",
    "Lighting.SetLogo": "io.otectus.archer1.set-hardware",
    "Lighting.SetBacklightTimeout": "io.otectus.archer1.set-hardware",
    "Display.SetMode": "io.otectus.archer1.set-display",
    "Power.SetGameMode": "io.otectus.archer1.set-gamemode",
    "Power.SetLcdOverride": "io.otectus.archer1.set-hardware",
    "Power.SetBootAnimationSound": "io.otectus.archer1.set-hardware",
    "Power.SetUsbWake": "io.otectus.archer1.set-hardware",
    "Audio.SetNoiseSuppression": "io.otectus.archer1.set-hardware",
    "Maintenance.SetModprobeParameter": "io.otectus.archer1.system-control",
    "Maintenance.ClearModprobeParameter": "io.otectus.archer1.system-control",
    "Maintenance.RestartDaemon": "io.otectus.archer1.system-control",
    "Maintenance.RestartDriversAndDaemon": "io.otectus.archer1.system-control",
}

# "Interface.Method" -> any-of feature names. Checked before polkit so a
# machine without the feature never shows an auth prompt for it.
FEATURE_GATES = {
    "Thermal.SetProfile": ("thermal_profiles",),
    "Thermal.SetFanSpeed": ("fan_control", "fan_speed"),
    "Thermal.SetFanAuto": ("fan_control", "fan_speed"),
    "Thermal.SetFanCurve": ("fan_control", "fan_speed"),
    "Thermal.ClearFanCurve": ("fan_control", "fan_speed"),
    "Battery.SetLimiter": ("battery_limiter",),
    "Battery.SetCalibration": ("battery_calibration",),
    "Battery.SetUsbCharging": ("usb_charging",),
    "Lighting.SetZones": ("keyboard_per_zone",),
    "Lighting.SetZoneMask": ("keyboard_per_zone",),
    "Lighting.SetBrightness": ("keyboard_per_zone", "keyboard_effects"),
    "Lighting.SetEffect": ("keyboard_effects",),
    "Lighting.SetOff": ("keyboard_per_zone", "keyboard_effects"),
    "Lighting.SetButtonFollowsProfile": ("ene_ready",),
    "Lighting.SetButtonColor": ("ene_ready",),
    "Lighting.SetButtonColors": ("ene_ready",),
    "Lighting.ResetButtonColors": ("ene_ready",),
    "Lighting.SetButtonFixedColor": ("ene_ready",),
    "Lighting.SetLogo": ("ene_ready",),
    "Lighting.SetBacklightTimeout": ("backlight_timeout",),
    "Display.SetMode": ("display_mode",),
    "Power.SetGameMode": ("game_mode",),
    "Power.SetLcdOverride": ("lcd_override",),
    "Power.SetBootAnimationSound": ("boot_animation_sound",),
    "Power.SetUsbWake": ("usb_wake_policy",),
}

