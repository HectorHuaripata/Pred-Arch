import QtQuick
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
    implicitWidth: col.implicitWidth
    implicitHeight: col.implicitHeight
    property real _shown: value
    Behavior on _shown { enabled: root.visible; NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
    onValueChanged: _shown = value
    ColumnLayout {
        id: col
        spacing: 0
        Text { text: root.label; color: Kirigami.Theme.textColor; opacity: 0.7; font.pointSize: Kirigami.Theme.smallFont.pointSize; font.capitalization: Font.AllUppercase; font.letterSpacing: 1 }
        RowLayout {
            spacing: Kirigami.Units.smallSpacing
            Kirigami.Heading { level: 1; text: Math.round(root._shown); color: root.accent; font.weight: Font.Bold; font.pointSize: Kirigami.Theme.defaultFont.pointSize * 2.2 }
            Text { text: root.unit; color: Kirigami.Theme.textColor; opacity: 0.7; Layout.alignment: Qt.AlignBaseline }
        }
        Text { text: root.note; visible: text !== ""; color: Kirigami.Theme.textColor; opacity: 0.6; font: Kirigami.Theme.smallFont }
    }
}
