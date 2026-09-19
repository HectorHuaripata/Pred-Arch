import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

// Battery health, USB charging, panel/boot toggles and wake sources.
Kirigami.ScrollablePage {
    id: page
    title: qsTr("Battery & Power")
    padding: Kirigami.Units.largeSpacing * 2

    readonly property var features: System.features || []
    function has(feature) { return features.indexOf(feature) >= 0 }
    // Only wake devices the catalog can name; the rest are PCIe root ports.
    readonly property var wakeSources: (Power.usbWakeSources || []).filter(s => Catalog.wakeSourceLabel(s[0]) !== "")

    readonly property bool calibrating: Battery.calibration === true
    // Phase from the live battery reading: (present, percent, status, seconds).
    readonly property var battery: Telemetry.battery || [false, 0, "unknown", -1]
    readonly property string calibrationPhase: {
        const percent = Math.round(battery[1])
        switch (battery[2]) {
        case "discharging": return qsTr("Calibrating: draining, %1 % left").arg(percent)
        case "charging":    return qsTr("Calibrating: charging back up, %1 %").arg(percent)
        case "full":        return qsTr("Calibrating: finishing at 100 %")
        default:            return qsTr("Calibration in progress")
        }
    }

    Kirigami.PromptDialog {
        id: calibrationPrompt
        title: qsTr("Start a battery calibration cycle?")
        subtitle: qsTr("The laptop will run on battery until it is empty, then charge to 100 %. Plan for a few hours with the charger connected. You can cancel at any time.")
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: Bus.call("Battery", "SetCalibration", [true])
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Card {
            title: qsTr("Battery health")
            visible: page.has("battery_limiter") || page.has("battery_calibration")
            BoundSwitch { visible: page.has("battery_limiter"); text: qsTr("Limit charge to 80 %"); bound: Battery.limiter === true; apply: v => Bus.call("Battery", "SetLimiter", [v]) }
            Hint { visible: page.has("battery_limiter"); text: qsTr("Keeps the cell between 20 and 80 % while plugged in. Recommended when the laptop lives on the desk.") }
            // Calibration is a cycle the EC runs for hours and ends by
            // itself, so it is started and cancelled, never "switched on".
            RowLayout {
                visible: page.has("battery_calibration")
                spacing: Kirigami.Units.largeSpacing
                QQC2.Button {
                    visible: !page.calibrating
                    text: qsTr("Start calibration cycle")
                    icon.name: "battery-profile"
                    onClicked: calibrationPrompt.open()
                }
                QQC2.BusyIndicator {
                    visible: page.calibrating; running: visible
                    implicitWidth: Kirigami.Units.iconSizes.smallMedium
                    implicitHeight: Kirigami.Units.iconSizes.smallMedium
                }
                QQC2.Label {
                    visible: page.calibrating
                    text: page.calibrationPhase
                }
                QQC2.Button {
                    visible: page.calibrating
                    text: qsTr("Cancel")
                    icon.name: "dialog-cancel"
                    onClicked: Bus.call("Battery", "SetCalibration", [false])
                }
            }
            Hint { visible: page.has("battery_calibration"); text: qsTr("Drains the battery completely, then charges it to 100 % so the gauge relearns its capacity. Takes several hours; keep the charger connected and the laptop awake. Acer suggests it every few months or when the reported charge looks wrong.") }
        }

        Card {
            title: qsTr("USB charging while asleep")
            visible: page.has("usb_charging")
            subtitle: qsTr("stops when the battery falls to the chosen level")
            RowLayout {
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: Catalog.usbChargingLevels        // [[percent, label], …]
                    delegate: ChoiceButton {
                        required property var modelData
                        text: modelData[1]; current: Battery.usbCharging === modelData[0]
                        onClicked: Bus.call("Battery", "SetUsbCharging", [modelData[0]])
                    }
                }
            }
        }

        Card {
            title: qsTr("Panel and boot")
            visible: page.has("lcd_override") || page.has("boot_animation_sound")
            BoundSwitch { visible: page.has("lcd_override"); text: qsTr("LCD override (keep the panel at full refresh rate)"); bound: Power.lcdOverride === true; apply: v => Bus.call("Power", "SetLcdOverride", [v]) }
            BoundSwitch { visible: page.has("boot_animation_sound"); text: qsTr("Boot animation and sound"); bound: Power.bootAnimationSound === true; apply: v => Bus.call("Power", "SetBootAnimationSound", [v]) }
        }

        Card {
            title: qsTr("Wake from sleep")
            visible: page.has("usb_wake_policy")
            subtitle: qsTr("which devices may wake the laptop")
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                Repeater {
                    model: page.wakeSources
                    delegate: QQC2.CheckBox {
                        required property var modelData
                        text: qsTr("%1  (%2)").arg(Catalog.wakeSourceLabel(modelData[0])).arg(modelData[0])
                        checked: modelData[1]
                        onToggled: { checked = modelData[1]; Bus.call("Power", "SetUsbWake", [modelData[0], !modelData[1]]) }
                    }
                }
            }
            Hint { visible: page.wakeSources.length === 0; text: qsTr("No recognised wake sources on this machine.") }
        }
    }
}
