import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

Kirigami.ScrollablePage {
    id: page
    title: "System"
    padding: Kirigami.Units.largeSpacing * 2
    property bool refreshing: false
    Connections {
        target: Firmware
        function onLastRefreshChanged() { page.refreshing = false }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Card {
            title: "This machine"
            Kirigami.FormLayout {
                Layout.fillWidth: true
                Text { Kirigami.FormData.label: "Model:"; text: (System.vendor || "") + " " + (System.productName || ""); color: Kirigami.Theme.textColor }
                Text { Kirigami.FormData.label: "Family:"; text: System.laptopType || ""; color: Kirigami.Theme.textColor }
                Text { Kirigami.FormData.label: "CPU:"; text: System.cpuModel || ""; color: Kirigami.Theme.textColor }
                Text { Kirigami.FormData.label: "GPU:"; text: System.gpuModel || ""; color: Kirigami.Theme.textColor }
                Text { Kirigami.FormData.label: "Kernel:"; text: System.kernel || ""; color: Kirigami.Theme.textColor }
                Text { Kirigami.FormData.label: "BIOS:"; text: Firmware.biosVersion || ""; color: Kirigami.Theme.textColor }
                Text { Kirigami.FormData.label: "Driver:"; text: (System.driver || "") + (System.driverVersion && System.driverVersion !== "N/A" ? " " + System.driverVersion : ""); color: Kirigami.Theme.textColor }
                Text { Kirigami.FormData.label: "Keyboard LED backend:"; text: System.eneReady ? "ENE K5130 (direct)" : (Lighting.backend || ""); color: Kirigami.Theme.textColor }
                Text { Kirigami.FormData.label: "Daemon:"; text: "v" + (System.version || "?") + (Bus.connected ? " · connected" : " · offline"); color: Bus.connected ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor }
            }
            // What the daemon found on this hardware. Informational: these
            // decide which pages and controls are shown, nothing to click.
            Text { text: "Detected capabilities"; color: Kirigami.Theme.textColor; opacity: 0.7; font.pointSize: Kirigami.Theme.smallFont.pointSize; font.capitalization: Font.AllUppercase; font.letterSpacing: 1 }
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                readonly property var names: ({
                    "thermal_profiles": "Performance profiles", "fan_control": "Fan control", "fan_speed": "Fan control",
                    "keyboard_per_zone": "Per-zone keyboard colour", "keyboard_effects": "Keyboard effects",
                    "battery_limiter": "Charge limit", "battery_calibration": "Battery calibration", "battery_info": "Battery readings",
                    "usb_charging": "USB charging while asleep", "lcd_override": "LCD override", "boot_animation_sound": "Boot animation & sound",
                    "backlight_timeout": "Keyboard backlight timeout", "display_mode": "GPU mode switching", "game_mode": "Game mode",
                    "usb_wake_policy": "Wake sources", "firmware_info": "Firmware info"
                })
                Repeater {
                    model: System.features || []
                    delegate: Rectangle {
                        required property string modelData
                        readonly property string label: parent.names[modelData] || modelData
                        width: tagText.implicitWidth + Kirigami.Units.largeSpacing * 2
                        height: tagText.implicitHeight + Kirigami.Units.smallSpacing * 2
                        radius: height / 2
                        color: Qt.rgba(Kirigami.Theme.positiveTextColor.r, Kirigami.Theme.positiveTextColor.g, Kirigami.Theme.positiveTextColor.b, 0.14)
                        Row {
                            anchors.centerIn: parent
                            spacing: Kirigami.Units.smallSpacing
                            Rectangle { width: 7; height: 7; radius: 3.5; color: Kirigami.Theme.positiveTextColor; anchors.verticalCenter: parent.verticalCenter }
                            Text { id: tagText; text: label; color: Kirigami.Theme.textColor; font.pointSize: Kirigami.Theme.smallFont.pointSize }
                        }
                    }
                }
            }
        }

        Card {
            title: "Firmware updates"
            subtitle: Firmware.fwupdAvailable ? (Firmware.lastRefresh > 0 ? "checked " + new Date(Firmware.lastRefresh * 1000).toLocaleTimeString() : "not checked yet") : "fwupd is not installed"
            RowLayout {
                QQC2.Button { text: "Check for updates"; icon.name: "view-refresh"; enabled: Firmware.fwupdAvailable === true && !page.refreshing
                    onClicked: { page.refreshing = true; Bus.call("Firmware", "Refresh") } }
                QQC2.BusyIndicator { running: page.refreshing; visible: running }
                Text { visible: Firmware.lastRefresh > 0 && (Firmware.updates || []).length === 0; text: "Everything is up to date."; color: Kirigami.Theme.positiveTextColor }
            }
            Repeater {
                model: Firmware.updates || []
                delegate: Text { required property var modelData; text: modelData[0] + ": " + modelData[1] + " → " + modelData[2]; color: Kirigami.Theme.textColor }
            }
        }

        Card {
            title: "Driver"
            subtitle: "linuwu_sense module parameter"
            RowLayout {
                Repeater {
                    model: [["", "Auto‑detect"], ["nitro_v4", "nitro_v4"], ["predator_v4", "predator_v4"], ["enable_all", "enable_all"]]
                    delegate: ChoiceButton {
                        required property var modelData
                        text: modelData[1]; current: (Maintenance.modprobeParameter || "") === modelData[0]
                        onClicked: modelData[0] === "" ? Bus.call("Maintenance", "ClearModprobeParameter") : Bus.call("Maintenance", "SetModprobeParameter", [modelData[0]])
                    }
                }
            }
            RowLayout {
                QQC2.Button { text: "Restart daemon"; icon.name: "system-reboot"; onClicked: Bus.call("Maintenance", "RestartDaemon") }
                QQC2.Button { text: "Reload driver and daemon"; icon.name: "system-reboot"; onClicked: Bus.call("Maintenance", "RestartDriversAndDaemon") }
            }
        }
    }
}
