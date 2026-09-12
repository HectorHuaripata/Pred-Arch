import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../Utils.js" as U

Kirigami.ScrollablePage {
    id: page
    title: "Overview"
    padding: Kirigami.Units.largeSpacing * 2

    readonly property var bat: Telemetry.battery || [false, 0, "unknown", -1]

    // Feed the chart from real samples only.
    Connections {
        target: Telemetry
        function onCpuTempChanged() { chart.push(Telemetry.cpuTemp, Telemetry.gpuTemp) }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        // Header: machine + profile
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 0
                Kirigami.Heading { level: 1; text: System.productName || "Acer laptop" }
                Text { text: (System.cpuModel || "") + (System.gpuModel ? " · " + System.gpuModel : ""); color: Kirigami.Theme.textColor; opacity: 0.6; elide: Text.ElideRight; Layout.fillWidth: true }
            }
            Item { Layout.fillWidth: true }
            ProfileBar {}
        }

        // Gauges
        Card {
            title: "Right now"
            subtitle: Telemetry.intervalMs > 0 ? "updating every " + Telemetry.intervalMs + " ms" : "paused"
            GridLayout {
                columns: page.width >= 720 ? 4 : 2
                columnSpacing: Kirigami.Units.largeSpacing * 2
                rowSpacing: Kirigami.Units.largeSpacing
                Layout.alignment: Qt.AlignHCenter
                Gauge { label: "CPU temperature"; unit: "°C"; maxValue: 110; value: Telemetry.cpuTemp || 0; accent: U.tempColor(Kirigami.Theme, value) }
                Gauge { label: "GPU temperature"; unit: "°C"; maxValue: 110; value: Telemetry.gpuTemp || 0; accent: U.tempColor(Kirigami.Theme, value) }
                Gauge { label: "CPU usage"; unit: "%"; value: Telemetry.cpuUsage || 0 }
                Gauge { label: "GPU usage"; unit: "%"; value: Telemetry.gpuUsage || 0 }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing * 2
            Card {
                title: "Fans"
                subtitle: Thermal.fanMode === "auto" ? "automatic" : (Thermal.fanMode || "")
                RowLayout {
                    spacing: Kirigami.Units.gridUnit * 2
                    StatTile { label: "CPU fan"; unit: "rpm"; value: (Telemetry.fanRpm || [0, 0])[0] }
                    StatTile { label: "GPU fan"; unit: "rpm"; value: (Telemetry.fanRpm || [0, 0])[1] }
                }
            }
            Card {
                title: "Battery"
                subtitle: Telemetry.powerSourceAc ? "on AC power" : "on battery"
                visible: page.bat[0]
                RowLayout {
                    spacing: Kirigami.Units.gridUnit * 2
                    StatTile { label: "Charge"; unit: "%"; value: page.bat[1]
                               note: U.batteryStatusLabel(page.bat[2]) + (page.bat[3] >= 0 ? " · " + U.formatSeconds(page.bat[3]) + (page.bat[2] === "charging" ? " to full" : " left") : "") + (Battery.limiter ? " · limit 80 %" : "") }
                }
            }
        }

        Card {
            title: "Temperature, last 5 minutes"
            RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Rectangle { width: 10; height: 10; radius: 5; color: chart.colorA } Text { text: "CPU"; color: Kirigami.Theme.textColor }
                Rectangle { width: 10; height: 10; radius: 5; color: chart.colorB } Text { text: "GPU"; color: Kirigami.Theme.textColor }
            }
            Sparkline { id: chart; Layout.fillWidth: true; maxValue: 100; capacity: 600 }
        }
    }
}
