import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.kirigami as Kirigami

// Arc gauge. The arcs are Shape paths (GPU-rendered), so animating the value
// costs a scene-graph update, not a CPU rasterisation per frame.
Item {
    id: root
    property real value: 0
    property real maxValue: 100
    property string label: ""
    property string unit: ""
    property string note: ""          // small line under the label, e.g. "9.3 / 23.4 GB"
    property color accent: Kirigami.Theme.highlightColor
    property int decimals: 0

    implicitWidth: Kirigami.Units.gridUnit * 8
    implicitHeight: implicitWidth + caption.implicitHeight + (note !== "" ? noteText.implicitHeight : 0) + Kirigami.Units.smallSpacing

    readonly property real _target: Math.max(0, Math.min(maxValue, value))
    property real _shown: 0
    // Only animate while on screen: an off-screen page's animations would
    // still drive full-window re-renders at the display refresh rate.
    Behavior on _shown { enabled: root.visible; NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
    on_TargetChanged: _shown = _target
    Component.onCompleted: _shown = _target

    readonly property real _r: width / 2 - Kirigami.Units.smallSpacing * 2
    readonly property real _lw: Math.max(6, _r * 0.16)

    Shape {
        id: shape
        width: root.width
        height: root.width
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        preferredRendererType: Shape.CurveRenderer
        antialiasing: true

        ShapePath {
            strokeColor: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.12)
            strokeWidth: root._lw
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: shape.width / 2; centerY: shape.height / 2; radiusX: root._r; radiusY: root._r; startAngle: 135; sweepAngle: 270 }
        }
        ShapePath {
            strokeColor: root.accent
            strokeWidth: root._lw
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: shape.width / 2; centerY: shape.height / 2; radiusX: root._r; radiusY: root._r
                startAngle: 135
                sweepAngle: root.maxValue > 0 ? 270 * root._shown / root.maxValue : 0
            }
        }
    }

    ColumnLayout {
        anchors.centerIn: shape
        spacing: 0
        Kirigami.Heading {
            Layout.alignment: Qt.AlignHCenter
            level: 1
            text: root.value.toFixed(root.decimals)
            font.weight: Font.DemiBold
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: root.unit
            color: Kirigami.Theme.textColor
            opacity: 0.7
        }
    }
    Text {
        id: caption
        anchors.top: shape.bottom
        anchors.topMargin: Kirigami.Units.smallSpacing
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.label
        color: Kirigami.Theme.textColor
        opacity: 0.8
    }
    Text {
        id: noteText
        anchors.top: caption.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        visible: root.note !== ""
        text: root.note
        color: Kirigami.Theme.textColor
        opacity: 0.55
        font.pointSize: Kirigami.Theme.smallFont.pointSize
    }
}
