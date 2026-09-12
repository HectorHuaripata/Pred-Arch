import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

Kirigami.ScrollablePage {
    id: page
    title: "Display & Audio"
    padding: Kirigami.Units.largeSpacing * 2
    readonly property bool hasDisplay: (System.features || []).indexOf("display_mode") >= 0
    property string pendingMode: ""

    Connections {
        target: Bus
        function onCallSucceeded(iface, method) { if (iface === "Display") page.pendingMode = "" }
        function onCallFailed(iface, method, kind, msg) { if (iface === "Display") page.pendingMode = "" }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Card {
            title: "Graphics mode"
            visible: page.hasDisplay
            subtitle: "envycontrol · " + (Display.hasMux ? "MUX present" : "no MUX") + (Display.activeGpu && Display.activeGpu !== "unknown" ? " · panel on " + Display.activeGpu : "")
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: true
                type: Kirigami.MessageType.Information
                text: "Changing the mode rewrites the display configuration and needs a logout (or reboot) to take effect. It can take up to a minute."
            }
            RowLayout {
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: [["hybrid", "Hybrid", "Intel by default, NVIDIA on demand"], ["integrated", "Integrated", "NVIDIA off, longest battery"], ["nvidia", "NVIDIA", "discrete GPU always"]]
                    delegate: ChoiceButton {
                        required property var modelData
                        text: modelData[1]; current: Display.mode === modelData[0]
                        enabled: page.pendingMode === "" && (Display.choices || []).indexOf(modelData[0]) >= 0
                        QQC2.ToolTip.text: modelData[2]; QQC2.ToolTip.visible: hovered
                        onClicked: { page.pendingMode = modelData[0]; Bus.call("Display", "SetMode", [modelData[0]]) }
                    }
                }
                QQC2.BusyIndicator { running: page.pendingMode !== ""; visible: running }
                Text { visible: page.pendingMode !== ""; text: "Switching to " + page.pendingMode + "…"; color: Kirigami.Theme.textColor }
            }
        }

        Card {
            title: "Microphone noise suppression"
            subtitle: "PipeWire filter chain (RNNoise); pipewire restarts in your session when toggled"
            BoundSwitch { text: checked ? "Enabled" : "Disabled"; bound: Audio.noiseSuppression === true; apply: v => Bus.call("Audio", "SetNoiseSuppression", [v]) }
        }
    }
}
