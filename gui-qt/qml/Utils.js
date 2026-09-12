.pragma library

var PROFILE_LABELS = {
    "low-power": "Eco", "quiet": "Quiet", "balanced": "Balanced",
    "balanced-performance": "Balanced+", "performance": "Performance"
}
var PROFILE_ICONS = {
    "low-power": "battery-low", "quiet": "audio-volume-muted", "balanced": "speedometer",
    "balanced-performance": "speedometer", "performance": "flag-red"
}

function profileLabel(p) { return PROFILE_LABELS[p] || p }
function profileIcon(p) { return PROFILE_ICONS[p] || "speedometer" }

// [r,g,b] (0-255) <-> QML color
function rgbToColor(a) {
    if (!a || a.length < 3) return "#000000"
    return Qt.rgba(a[0] / 255, a[1] / 255, a[2] / 255, 1)
}
function colorToRgb(c) {
    return [Math.round(c.r * 255), Math.round(c.g * 255), Math.round(c.b * 255)]
}
function hex(c) {
    function h(v) { var s = Math.round(v * 255).toString(16); return s.length < 2 ? "0" + s : s }
    return "#" + h(c.r) + h(c.g) + h(c.b)
}

function tempColor(theme, t) {
    if (t >= 85) return theme.negativeTextColor
    if (t >= 70) return theme.neutralTextColor
    return theme.positiveTextColor
}

function formatSeconds(s) {
    if (s === undefined || s === null || s < 0) return "—"
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
    return h > 0 ? h + " h " + m + " min" : m + " min"
}

function batteryStatusLabel(status) {
    return { "charging": "Charging", "discharging": "On battery", "full": "Full",
             "idle": "Plugged in, not charging", "unknown": "—" }[status] || status
}
