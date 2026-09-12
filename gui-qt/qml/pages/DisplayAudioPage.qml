import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

// Hybrid-graphics mode and microphone noise suppression.
Kirigami.ScrollablePage {
    id: page
    title: qsTr("Display & Audio")
    padding: Kirigami.Units.largeSpacing * 2

    readonly property bool hasDisplay: (System.features || []).indexOf("display_mode") >= 0
    property string pendingMode: ""

    Connections {
        target: Bus
        function onCallSucceeded(iface, method) { if (iface === "Display") page.pendingMode = "" }
        function onCallFailed(iface, method, kind, message) { if (iface === "Display") page.pendingMode = "" }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Card {
            title: qsTr("Graphics mode")
            visible: page.hasDisplay
            subtitle: [qsTr("envycontrol"),
                       Display.hasMux ? qsTr("MUX present") : qsTr("no MUX"),
                       Display.activeGpu && Display.activeGpu !== "unknown" ? qsTr("panel on %1").arg(Display.activeGpu) : ""]
                      .filter(s => s).join(" · ")
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: true
                type: Kirigami.MessageType.Information
                text: qsTr("Changing the mode rewrites the display configuration and needs a logout (or reboot) to take effect. It can take up to a minute.")
            }
            RowLayout {
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: Catalog.displayModes             // [[mode, label, hint], …]
                    delegate: ChoiceButton {
                        required property var modelData
                        text: modelData[1]; current: Display.mode === modelData[0]
                        enabled: page.pendingMode === "" && (Display.choices || []).indexOf(modelData[0]) >= 0
                        QQC2.ToolTip.text: modelData[2]; QQC2.ToolTip.visible: hovered
                        onClicked: { page.pendingMode = modelData[0]; Bus.call("Display", "SetMode", [modelData[0]]) }
                    }
                }
                QQC2.BusyIndicator { running: page.pendingMode !== ""; visible: running }
                QQC2.Label { visible: page.pendingMode !== ""; text: qsTr("Switching to %1…").arg(page.pendingMode) }
            }
        }

        Card {
            title: qsTr("Microphone noise suppression")
            subtitle: qsTr("PipeWire filter chain (RNNoise); PipeWire restarts in your session when toggled")
            BoundSwitch { text: checked ? qsTr("Enabled") : qsTr("Disabled"); bound: Audio.noiseSuppression === true; apply: v => Bus.call("Audio", "SetNoiseSuppression", [v]) }
        }
    }
}
