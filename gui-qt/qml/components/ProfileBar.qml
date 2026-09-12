import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Segmented profile selector; follows Thermal.profile whoever wrote it.
RowLayout {
    id: root
    spacing: Kirigami.Units.smallSpacing
    property bool compact: false
    Repeater {
        model: Thermal.profileChoices || []
        delegate: ChoiceButton {
            required property string modelData
            text: root.compact ? "" : Catalog.profileLabel(modelData)
            icon.name: Catalog.profileIcon(modelData)
            current: Thermal.profile === modelData
            QQC2.ToolTip.text: Catalog.profileLabel(modelData)
            QQC2.ToolTip.visible: hovered && root.compact
            onClicked: Bus.call("Thermal", "SetProfile", [modelData])
        }
    }
}
