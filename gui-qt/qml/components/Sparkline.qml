import QtQuick
import org.kde.kirigami as Kirigami

// Two-series time chart fed by push(). Keeps `capacity` samples.
Item {
    id: root
    property int capacity: 300          // samples kept; one per sampleMs
    property int sampleMs: 1000
    property real minValue: 0
    property real maxValue: 100
    property real gridStep: 25
    property color colorA: Kirigami.Theme.highlightColor
    property color colorB: Kirigami.Theme.negativeTextColor
    property var seriesA: []
    property var seriesB: []
    implicitHeight: Kirigami.Units.gridUnit * 10

    function push(a, b) {
        var A = seriesA.slice(), B = seriesB.slice()
        A.push(a); B.push(b)
        if (A.length > capacity) { A.shift(); B.shift() }
        seriesA = A; seriesB = B
        canvas.requestPaint()
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
            ctx.textAlign = "right"
            ctx.fillText("now", padL + w, height - 4)
            ctx.textAlign = "left"
            // Fixed time axis: the trace grows from the right, one sample per
            // sampleMs, until it spans the whole window, then scrolls.
            ctx.fillText("-" + Math.round(root.capacity * root.sampleMs / 60000) + " min", padL, height - 4)
            function line(series, color) {
                if (series.length < 2) return
                var step = w / (root.capacity - 1)
                var x0 = padL + w - (series.length - 1) * step
                ctx.strokeStyle = color
                ctx.lineWidth = 2
                ctx.lineJoin = "round"
                ctx.beginPath()
                for (var i = 0; i < series.length; i++) {
                    var x = x0 + i * step
                    var y = yOf(series[i])
                    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
                }
                ctx.stroke()
                // area under the line
                ctx.lineTo(x0 + (series.length - 1) * step, padT + h)
                ctx.lineTo(x0, padT + h)
                ctx.closePath()
                ctx.fillStyle = Qt.rgba(color.r, color.g, color.b, 0.10)
                ctx.fill()
                // endpoint
                var lx = x0 + (series.length - 1) * step
                var ly = yOf(series[series.length - 1])
                ctx.fillStyle = color
                ctx.beginPath(); ctx.arc(lx, ly, 3, 0, Math.PI * 2); ctx.fill()
            }
            line(root.seriesA, root.colorA)
            line(root.seriesB, root.colorB)
        }
        Connections { target: Kirigami.Theme; function onColorsChanged() { canvas.requestPaint() } }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }
}
