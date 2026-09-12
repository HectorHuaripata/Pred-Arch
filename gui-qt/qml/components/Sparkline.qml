import QtQuick
import org.kde.kirigami as Kirigami

// Two-series wall-clock chart backed by History (archerqt/history.py).
// Holds no data itself: on each paint it asks for the last `windowSeconds`
// at the resolution that fits, never more than 1440 points. NaN = gap.
Item {
    id: root
    objectName: "sparkline"
    property int windowSeconds: 600
    property real minValue: 0
    property real maxValue: 100
    property real gridStep: 25
    property color colorA: Kirigami.Theme.highlightColor
    property color colorB: Kirigami.Theme.negativeTextColor
    implicitHeight: Kirigami.Units.gridUnit * 10

    function refresh() { canvas.requestPaint() }
    onWindowSecondsChanged: canvas.requestPaint()

    function spanLabel() {
        var s = windowSeconds
        if (s >= 3600) return "-" + Math.round(s / 3600) + " h"
        return "-" + Math.round(s / 60) + " min"
    }

    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true
        readonly property color grid: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.10)
        readonly property color axis: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.55)

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            var padL = 34, padR = 8, padT = 8, padB = 18
            var w = width - padL - padR, h = height - padT - padB
            ctx.font = Kirigami.Theme.smallFont.pixelSize + "px sans-serif"
            ctx.fillStyle = axis
            ctx.strokeStyle = grid
            ctx.lineWidth = 1
            function yOf(v) {
                var f = (Math.min(Math.max(v, root.minValue), root.maxValue) - root.minValue) / (root.maxValue - root.minValue)
                return padT + h - f * h
            }
            for (var t = root.minValue; t <= root.maxValue; t += root.gridStep) {
                var y = yOf(t)
                ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + w, y); ctx.stroke()
                ctx.fillText(t + "°", 4, y + 4)
            }
            ctx.textAlign = "right"; ctx.fillText("now", padL + w, height - 4)
            ctx.textAlign = "left"; ctx.fillText(root.spanLabel(), padL, height - 4)

            var win = History.window(root.windowSeconds)     // [stepSeconds, A, B]
            var slots = Math.max(2, Math.floor(root.windowSeconds / win[0]))
            var step = w / (slots - 1)
            function line(pts, color) {
                if (pts.length < 2) return
                // The trace grows in from the right until it spans the window.
                var x0 = padL + w - (pts.length - 1) * step
                ctx.strokeStyle = color
                ctx.lineWidth = 2
                ctx.lineJoin = "round"
                ctx.beginPath()
                var pen = false, lastX = 0, lastY = 0
                for (var i = 0; i < pts.length; i++) {
                    if (isNaN(pts[i])) { pen = false; continue }
                    var x = x0 + i * step, y = yOf(pts[i])
                    if (!pen) { ctx.moveTo(x, y); pen = true } else ctx.lineTo(x, y)
                    lastX = x; lastY = y
                }
                ctx.stroke()
                if (pen) {
                    ctx.fillStyle = color
                    ctx.beginPath(); ctx.arc(lastX, lastY, 3, 0, Math.PI * 2); ctx.fill()
                }
            }
            line(win[1], root.colorA)
            line(win[2], root.colorB)
        }
        Connections { target: Kirigami.Theme; function onColorsChanged() { canvas.requestPaint() } }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }
}
