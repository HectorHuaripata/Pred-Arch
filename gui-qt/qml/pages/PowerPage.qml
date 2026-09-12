import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../Utils.js" as U

Kirigami.ScrollablePage {
    id: page
    title: "Battery & Power"
    padding: Kirigami.Units.largeSpacing * 2
    readonly property var features: System.features || []
    function has(f) { return features.indexOf(f) >= 0 }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Card {
            title: "Battery health"
            visible: page.has("battery_limiter") || page.has("battery_calibration")
            BoundSwitch { visible: page.has("battery_limiter"); text: "Limit charge to 80 %"; bound: Battery.limiter === true; apply: v => Bus.call("Battery", "SetLimiter", [v]) }
            Text { visible: page.has("battery_limiter"); text: "Keeps the cell between 20 and 80 % while plugged in. Recommended when the laptop lives on the desk."; color: Kirigami.Theme.textColor; opacity: 0.6; font: Kirigami.Theme.smallFont; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            BoundSwitch { visible: page.has("battery_calibration"); text: "Calibration cycle"; bound: Battery.calibration === true; apply: v => Bus.call("Battery", "SetCalibration", [v]) }
            Text { visible: page.has("battery_calibration"); text: "Full discharge followed by a full charge so the gauge relearns capacity. Leave the charger connected."; color: Kirigami.Theme.textColor; opacity: 0.6; font: Kirigami.Theme.smallFont; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        }

        Card {
            title: "USB charging while asleep"
            visible: page.has("usb_charging")
            subtitle: "stops when the battery falls to the chosen level"
            RowLayout {
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: [[0, "Off"], [10, "Until 10 %"], [20, "Until 20 %"], [30, "Until 30 %"]]
                    delegate: ChoiceButton {
                        required property var modelData
                        text: modelData[1]; current: Battery.usbCharging === modelData[0]
                        onClicked: Bus.call("Battery", "SetUsbCharging", [modelData[0]])
                    }
                }
            }
        }

        Card {
            title: "Panel and boot"
            visible: page.has("lcd_override") || page.has("boot_animation_sound")
            BoundSwitch { visible: page.has("lcd_override"); text: "LCD override (keep the panel at full refresh rate)"; bound: Power.lcdOverride === true; apply: v => Bus.call("Power", "SetLcdOverride", [v]) }
            BoundSwitch { visible: page.has("boot_animation_sound"); text: "Boot animation and sound"; bound: Power.bootAnimationSound === true; apply: v => Bus.call("Power", "SetBootAnimationSound", [v]) }
        }

        Card {
            id: wakeCard
            title: "Wake from sleep"
            visible: page.has("usb_wake_policy")
            subtitle: "which devices may wake the laptop"
            // /proc/acpi/wakeup lists every PCIe port; only the named
            // controllers mean anything to a person.
            readonly property var known: ({ "XHCI": "USB (chipset)", "TXHC": "USB (Thunderbolt)", "XDCI": "USB device mode",
                                            "GLAN": "Ethernet", "CNVW": "Wi‑Fi", "HDAS": "Audio", "AWAC": "ACPI wake alarm",
                                            "TDM0": "Thunderbolt 0", "TDM1": "Thunderbolt 1", "LID0": "Lid", "PBTN": "Power button", "SLPB": "Sleep button" })
            readonly property var shown: (Power.usbWakeSources || []).filter(s => wakeCard.known[s[0]] !== undefined)
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                Repeater {
                    model: wakeCard.shown
                    delegate: QQC2.CheckBox {
                        required property var modelData
                        text: wakeCard.known[modelData[0]] + "  (" + modelData[0] + ")"; checked: modelData[1]
                        onToggled: { checked = modelData[1]; Bus.call("Power", "SetUsbWake", [modelData[0], !modelData[1]]) }
                    }
                }
            }
            Text { visible: wakeCard.shown.length === 0; text: "No recognised wake sources on this machine."; color: Kirigami.Theme.textColor; opacity: 0.6 }
        }
    }
}
