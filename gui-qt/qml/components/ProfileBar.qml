import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../Utils.js" as U

// Segmented profile selector; follows Thermal.profile from any writer.
RowLayout {
    id: root
    spacing: Kirigami.Units.smallSpacing
    property bool compact: false
    Repeater {
        model: Thermal.profileChoices || []
        delegate: ChoiceButton {
            required property string modelData
            text: root.compact ? "" : U.profileLabel(modelData)
            icon.name: U.profileIcon(modelData)
            current: Thermal.profile === modelData
            QQC2.ToolTip.text: U.profileLabel(modelData); QQC2.ToolTip.visible: hovered && root.compact
            onClicked: Bus.call("Thermal", "SetProfile", [modelData])
        }
    }
}
