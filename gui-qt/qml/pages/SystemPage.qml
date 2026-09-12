import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../Utils.js" as U

// Machine facts, detected capabilities, firmware, driver and maintenance.
Kirigami.ScrollablePage {
    id: page
    title: qsTr("System")
    padding: Kirigami.Units.largeSpacing * 2

    property bool refreshing: false
    Connections {
        target: Firmware
        function onLastRefreshChanged() { page.refreshing = false }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Card {
            title: qsTr("This machine")
            Kirigami.FormLayout {
                Layout.fillWidth: true
                QQC2.Label { Kirigami.FormData.label: qsTr("Model:"); text: [System.vendor, System.productName].filter(s => s).join(" ") }
                QQC2.Label { Kirigami.FormData.label: qsTr("Family:"); text: U.capitalize(System.laptopType || "") }
                QQC2.Label { Kirigami.FormData.label: qsTr("CPU:"); text: System.cpuModel || "" }
                QQC2.Label { Kirigami.FormData.label: qsTr("GPU:"); text: System.gpuModel || "" }
                QQC2.Label { Kirigami.FormData.label: qsTr("Kernel:"); text: System.kernel || "" }
                QQC2.Label { Kirigami.FormData.label: qsTr("BIOS:"); text: Firmware.biosVersion || "" }
                QQC2.Label { Kirigami.FormData.label: qsTr("Driver:")
                    text: [System.driver, System.driverVersion && System.driverVersion !== "N/A" ? System.driverVersion : ""].filter(s => s).join(" ") }
                QQC2.Label { Kirigami.FormData.label: qsTr("Keyboard LED backend:"); text: System.eneReady ? qsTr("ENE K5130 (direct)") : (Lighting.backend || "") }
                QQC2.Label { Kirigami.FormData.label: qsTr("Daemon:")
                    text: qsTr("v%1 · %2").arg(System.version || "?").arg(Bus.connected ? qsTr("connected") : qsTr("offline"))
                    color: Bus.connected ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor }
            }
            // What the daemon found on this hardware. Informational: these
            // decide which pages and controls are shown, nothing to click.
            Eyebrow { label: qsTr("Detected capabilities") }
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: System.features || []
                    delegate: Rectangle {
                        required property string modelData
                        width: tag.implicitWidth + Kirigami.Units.largeSpacing * 2
                        height: tag.implicitHeight + Kirigami.Units.smallSpacing * 2
                        radius: height / 2
                        color: Qt.rgba(Kirigami.Theme.positiveTextColor.r, Kirigami.Theme.positiveTextColor.g, Kirigami.Theme.positiveTextColor.b, 0.14)
                        Row {
                            anchors.centerIn: parent
                            spacing: Kirigami.Units.smallSpacing
                            Rectangle { width: Kirigami.Units.smallSpacing * 1.75; height: width; radius: width / 2; color: Kirigami.Theme.positiveTextColor; anchors.verticalCenter: parent.verticalCenter }
                            QQC2.Label { id: tag; text: Catalog.capabilityLabel(modelData); font: Kirigami.Theme.smallFont }
                        }
                    }
                }
            }
        }

        Card {
            title: qsTr("Firmware updates")
            subtitle: Firmware.fwupdAvailable
                      ? (Firmware.lastRefresh > 0 ? qsTr("checked %1").arg(new Date(Firmware.lastRefresh * 1000).toLocaleTimeString()) : qsTr("not checked yet"))
                      : qsTr("fwupd is not installed")
            RowLayout {
                QQC2.Button { text: qsTr("Check for updates"); icon.name: "view-refresh"; enabled: Firmware.fwupdAvailable === true && !page.refreshing
                    onClicked: { page.refreshing = true; Bus.call("Firmware", "Refresh") } }
                QQC2.BusyIndicator { running: page.refreshing; visible: running }
                QQC2.Label { visible: Firmware.lastRefresh > 0 && (Firmware.updates || []).length === 0; text: qsTr("Everything is up to date."); color: Kirigami.Theme.positiveTextColor }
            }
            Repeater {
                model: Firmware.updates || []               // [[device, current, available], …]
                delegate: QQC2.Label { required property var modelData; text: qsTr("%1: %2 → %3").arg(modelData[0]).arg(modelData[1]).arg(modelData[2]) }
            }
        }

        Card {
            title: qsTr("Driver")
            subtitle: qsTr("linuwu_sense module parameter")
            RowLayout {
                Repeater {
                    model: Catalog.modprobeParameters       // [[value, label], …]; "" = auto-detect
                    delegate: ChoiceButton {
                        required property var modelData
                        text: modelData[1]; current: (Maintenance.modprobeParameter || "") === modelData[0]
                        onClicked: modelData[0] === "" ? Bus.call("Maintenance", "ClearModprobeParameter")
                                                       : Bus.call("Maintenance", "SetModprobeParameter", [modelData[0]])
                    }
                }
            }
            RowLayout {
                QQC2.Button { text: qsTr("Restart daemon"); icon.name: "system-reboot"; onClicked: Bus.call("Maintenance", "RestartDaemon") }
                QQC2.Button { text: qsTr("Reload driver and daemon"); icon.name: "system-reboot"; onClicked: Bus.call("Maintenance", "RestartDriversAndDaemon") }
            }
        }
    }
}
