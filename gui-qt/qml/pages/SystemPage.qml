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
                Text { Kirigami.FormData.label: "Keyboard LED backend:"; text: System.eneReady ? "ENE K5130 (direct)" : Lighting.backend; color: Kirigami.Theme.textColor }
                Text { Kirigami.FormData.label: "Daemon:"; text: "v" + (System.version || "?") + (Bus.connected ? " · connected" : " · offline"); color: Bus.connected ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor }
            }
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater { model: System.features || []; delegate: Kirigami.Chip { required property string modelData; text: modelData; closable: false; checkable: false } }
            }
        }

        Card {
            title: "Firmware updates"
            subtitle: Firmware.fwupdAvailable ? (Firmware.lastRefresh > 0 ? "checked " + new Date(Firmware.lastRefresh * 1000).toLocaleTimeString() : "not checked yet") : "fwupd is not installed"
            RowLayout {
                QQC2.Button { text: "Check for updates"; icon.name: "view-refresh"; enabled: Firmware.fwupdAvailable && !page.refreshing
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
