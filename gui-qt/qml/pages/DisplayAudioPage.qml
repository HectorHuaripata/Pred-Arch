import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

// Hybrid-graphics mode; speaker and microphone processing (SOF DSP and
// PipeWire filters).
Kirigami.ScrollablePage {
    id: page
    title: qsTr("Display & Audio")
    padding: Kirigami.Units.largeSpacing * 2

    readonly property bool hasDisplay: (System.features || []).indexOf("display_mode") >= 0
    readonly property bool dsp: Audio.dspAvailable === true
    readonly property var beamAngles: Audio.micBeamAngles || []
    readonly property int beamIndex: Math.max(0, beamAngles.indexOf(Audio.micBeamAngle))
    property string pendingMode: ""

    function angleLabel(deg) {
        if (deg === 0) return qsTr("0° · straight ahead")
        return deg < 0 ? qsTr("%1° · to your left").arg(-deg) : qsTr("%1° · to your right").arg(deg)
    }

    onVisibleChanged: if (visible) Panel.refresh()
    Component.onCompleted: Panel.refresh()

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

        // -- Built-in panel refresh rate (KScreen, session side) ----------------
        Card {
            title: qsTr("Built-in panel")
            visible: Panel.available
            subtitle: Panel.panelEnabled ? Panel.resolution : qsTr("switched off (external display in use)")
            RowLayout {
                spacing: Kirigami.Units.smallSpacing
                enabled: Panel.panelEnabled
                QQC2.Label { text: qsTr("Refresh rate") }
                Repeater {
                    model: Panel.refreshRates
                    delegate: ChoiceButton {
                        required property var modelData
                        text: qsTr("%1 Hz").arg(modelData); current: Math.round(Panel.currentRefresh) === modelData
                        onClicked: Panel.setRefresh(modelData)
                    }
                }
            }
            Hint { text: qsTr("Lower rates save battery; the highest is for games. Plasma remembers the choice per display.") }
        }

        // -- Speakers: processing inside the SOF DSP, zero CPU -----------------
        Card {
            title: qsTr("Speakers")
            subtitle: page.dsp ? qsTr("processed in the audio DSP") : qsTr("no DSP controls on this codec")
            BoundSwitch { enabled: page.dsp; text: qsTr("Dynamic range compression"); bound: Audio.speakerDrc === true; apply: v => Bus.call("Audio", "SetSpeakerDrc", [v]) }
            Hint { text: qsTr("Evens out loud and quiet passages so the speakers sound fuller at the same volume. Off is the neutral, studio-like setting.") }
            BoundSwitch { enabled: page.dsp; text: qsTr("Mute the speakers when headphones are plugged in"); bound: Audio.autoMute === true; apply: v => Bus.call("Audio", "SetAutoMute", [v]) }
        }

        // -- Microphone: beamformer and DRC in the DSP, filters in PipeWire ---
        Card {
            title: qsTr("Microphone")
            subtitle: page.dsp ? qsTr("4-microphone array · beamforming in the audio DSP") : ""
            BoundSwitch { enabled: page.dsp; text: qsTr("Beamforming (focus on one direction)"); bound: Audio.micBeamforming === true; apply: v => Bus.call("Audio", "SetMicBeamforming", [v]) }
            RowLayout {
                visible: page.dsp && page.beamAngles.length > 1
                enabled: Audio.micBeamforming === true
                QQC2.Label { text: qsTr("Direction") }
                BoundSlider {
                    id: angleSlider
                    Layout.fillWidth: true
                    from: 0; to: Math.max(1, page.beamAngles.length - 1); stepSize: 1
                    snapMode: QQC2.Slider.SnapAlways
                    bound: page.beamIndex
                    apply: v => Bus.call("Audio", "SetMicBeamAngle", [page.beamAngles[Math.round(v)]])
                }
                QQC2.Label { Layout.minimumWidth: Kirigami.Units.gridUnit * 9; text: page.angleLabel(page.beamAngles[Math.round(angleSlider.value)] || 0) }
            }
            Hint { visible: page.dsp; text: qsTr("Point the array at where you sit: straight ahead for the person at the keyboard, to a side if the laptop is off-centre. Sound from other directions is attenuated.") }
            BoundSwitch { enabled: page.dsp; text: qsTr("Level compression (steady voice volume)"); bound: Audio.micDrc === true; apply: v => Bus.call("Audio", "SetMicDrc", [v]) }

            Kirigami.Separator { Layout.fillWidth: true }

            BoundSwitch {
                enabled: Audio.noiseSuppressionAvailable === true
                text: qsTr("Noise suppression (RNNoise, PipeWire)")
                bound: Audio.noiseSuppression === true
                apply: v => Bus.call("Audio", "SetNoiseSuppression", [v])
            }
            Hint {
                text: Audio.noiseSuppressionAvailable === true
                      ? qsTr("Removes keyboard, fan and room noise from the microphone before applications see it. PipeWire restarts in your session when toggled.")
                      : qsTr("Not installed. Run the audio-enhance module of the installer (`./install.sh --modules audio-enhance`) to add the RNNoise filter.")
            }
            Hint {
                visible: App.echoCancelDetected
                text: qsTr("Echo cancellation (WebRTC) is active in your PipeWire session — configured outside Pred-Arch, left untouched.")
            }
        }
    }
}
