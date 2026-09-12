import QtQuick
import org.kde.kirigami as Kirigami

// Two-series time chart fed by push(). Keeps `capacity` samples.
Item {
    id: root
    property int capacity: 300
    property real maxValue: 100
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
            for (var t = 0; t <= root.maxValue; t += 25) {
                var y = padT + h - (t / root.maxValue) * h
                ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + w, y); ctx.stroke()
                ctx.fillText(t + "°", 4, y + 4)
            }
            ctx.textAlign = "right"
            ctx.fillText("now", padL + w, height - 4)
            ctx.textAlign = "left"
            ctx.fillText("-" + Math.round(root.capacity / 60 * 0.5) + " min", padL, height - 4)
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
                    var y = padT + h - (Math.min(series[i], root.maxValue) / root.maxValue) * h
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
                var ly = padT + h - (Math.min(series[series.length - 1], root.maxValue) / root.maxValue) * h
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
