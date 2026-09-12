.pragma library
// Pure helpers with no state and no user-visible text; words live in
// archerqt/catalog.py so they can be translated.

// [r, g, b] (0-255) <-> QML color
function rgbToColor(rgb) {
    if (!rgb || rgb.length < 3) return "#000000"
    return Qt.rgba(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, 1)
}

function colorToRgb(color) {
    return [Math.round(color.r * 255), Math.round(color.g * 255), Math.round(color.b * 255)]
}

// Theme colour for a temperature: positive below warn, neutral below hot,
// negative from hot.
function tempColor(theme, celsius, warnC, hotC) {
    if (celsius >= hotC) return theme.negativeTextColor
    if (celsius >= warnC) return theme.neutralTextColor
    return theme.positiveTextColor
}

function capitalize(text) {
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : ""
}
