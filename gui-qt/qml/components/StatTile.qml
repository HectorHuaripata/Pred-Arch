import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Hero number with a label; the number animates between values.
Item {
    id: root
    property string label: ""
    property real value: 0
    property string unit: ""
    property string note: ""
    property color accent: Kirigami.Theme.textColor
    implicitWidth: column.implicitWidth
    implicitHeight: column.implicitHeight

    property real _shown: value
    Behavior on _shown { enabled: root.visible; NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
    onValueChanged: _shown = value

    ColumnLayout {
        id: column
        spacing: 0
        Eyebrow { label: root.label }
        RowLayout {
            spacing: Kirigami.Units.smallSpacing
            Kirigami.Heading {
                level: 1
                text: Math.round(root._shown)
                color: root.accent
                font.weight: Font.Bold
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 2.2
            }
            QQC2.Label { text: root.unit; opacity: 0.7; Layout.alignment: Qt.AlignBaseline }
        }
        Hint { text: root.note; visible: text !== "" }
    }
}
