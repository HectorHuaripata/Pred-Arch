import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../Utils.js" as U

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
            // The colour the mode-button LED shows for this profile.
            Rectangle {
                visible: System.eneReady === true && Lighting.buttonFollowsProfile === true
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 2
                anchors.horizontalCenter: parent.horizontalCenter
                width: Kirigami.Units.gridUnit
                height: 3
                radius: 1.5
                color: U.rgbToColor((Lighting.buttonColors || ({}))[modelData] || [128, 128, 128])
            }
        }
    }
}
