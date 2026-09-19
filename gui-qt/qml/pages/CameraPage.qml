import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

// Webcam controls (V4L2 user controls), rendered from whatever the camera
// reports: integers as sliders, booleans as switches, menus as buttons.
Kirigami.ScrollablePage {
    id: page
    title: qsTr("Camera")
    padding: Kirigami.Units.largeSpacing * 2

    onVisibleChanged: if (visible) Camera.refresh()
    Component.onCompleted: Camera.refresh()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !Camera.available
            type: Kirigami.MessageType.Information
            text: qsTr("No camera controls: v4l-utils is not installed or no video device was found.")
        }

        Card {
            title: qsTr("Image")
            visible: Camera.available && Camera.controls.length > 0
            subtitle: Camera.device
            Repeater {
                model: Camera.controls
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    enabled: !modelData.inactive
                    QQC2.Label { text: modelData.label; Layout.minimumWidth: Kirigami.Units.gridUnit * 12 }
                    // int → slider
                    QQC2.Slider {
                        visible: modelData.type === "int"
                        Layout.fillWidth: true
                        from: modelData.min; to: modelData.max; stepSize: modelData.step
                        value: modelData.value
                        onPressedChanged: if (!pressed) Camera.setControl(modelData.name, Math.round(value))
                    }
                    QQC2.Label { visible: modelData.type === "int"; text: modelData.value; Layout.minimumWidth: Kirigami.Units.gridUnit * 3; horizontalAlignment: Text.AlignRight }
                    // bool → switch
                    QQC2.Switch {
                        visible: modelData.type === "bool"
                        checked: modelData.value !== 0
                        onToggled: Camera.setControl(modelData.name, checked ? 1 : 0)
                    }
                    // menu → one button per option
                    RowLayout {
                        visible: modelData.type === "menu"
                        spacing: Kirigami.Units.smallSpacing
                        Repeater {
                            model: modelData.menu
                            delegate: ChoiceButton {
                                required property string modelData
                                required property int index
                                text: modelData; current: parent.parent.modelData.value === index
                                onClicked: Camera.setControl(parent.parent.modelData.name, index)
                            }
                        }
                    }
                }
            }
            RowLayout {
                QQC2.Button { text: qsTr("Restore defaults"); icon.name: "edit-undo"; onClicked: Camera.resetDefaults() }
                Hint { text: qsTr("Changes apply immediately and persist while the camera stays connected; most cameras forget them on unplug or reboot.") }
            }
        }
    }
}
