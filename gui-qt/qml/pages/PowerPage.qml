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

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Card {
            title: qsTr("Battery health")
            visible: page.has("battery_limiter") || page.has("battery_calibration")
            BoundSwitch { visible: page.has("battery_limiter"); text: qsTr("Limit charge to 80 %"); bound: Battery.limiter === true; apply: v => Bus.call("Battery", "SetLimiter", [v]) }
            Hint { visible: page.has("battery_limiter"); text: qsTr("Keeps the cell between 20 and 80 % while plugged in. Recommended when the laptop lives on the desk.") }
            BoundSwitch { visible: page.has("battery_calibration"); text: qsTr("Calibration cycle"); bound: Battery.calibration === true; apply: v => Bus.call("Battery", "SetCalibration", [v]) }
            Hint { visible: page.has("battery_calibration"); text: qsTr("Full discharge followed by a full charge so the gauge relearns capacity. Leave the charger connected.") }
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
