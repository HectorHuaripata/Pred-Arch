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
    // [used MiB, total MiB]; absent on a daemon older than 2.1
    readonly property var mem: Telemetry.memory || [0, 0]
    readonly property real memPercent: mem[1] > 0 ? 100 * mem[0] / mem[1] : 0

    // One chart sample per second while the page is on screen. The daemon
    // only announces *changes*, so sampling on cpuTempChanged would freeze
    // the time axis whenever the temperature is steady.
    Timer {
        interval: 1000
        running: page.visible && Bus.connected && Telemetry.intervalMs > 0
        repeat: true
        onTriggered: { History.push(Telemetry.cpuTemp || 0, Telemetry.gpuTemp || 0); chart.refresh() }
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
                // 5 gauges of 8 grid units fit from ~840 px of page width
                columns: Math.max(2, Math.min(5, Math.floor((page.width - 48) / (Kirigami.Units.gridUnit * 8 + Kirigami.Units.largeSpacing))))
                columnSpacing: Kirigami.Units.largeSpacing
                rowSpacing: Kirigami.Units.largeSpacing
                Layout.alignment: Qt.AlignHCenter
                Gauge { label: "CPU temperature"; unit: "°C"; maxValue: 110; value: Telemetry.cpuTemp || 0; accent: U.tempColor(Kirigami.Theme, value) }
                Gauge { label: "GPU temperature"; unit: "°C"; maxValue: 110; value: Telemetry.gpuTemp || 0; accent: U.tempColor(Kirigami.Theme, value) }
                Gauge { label: "CPU usage"; unit: "%"; value: Telemetry.cpuUsage || 0 }
                Gauge { label: "GPU usage"; unit: "%"; value: Telemetry.gpuUsage || 0 }
                Gauge {
                    visible: page.mem[1] > 0
                    label: "Memory"; unit: "%"; value: page.memPercent
                    note: (page.mem[0] / 1024).toFixed(1) + " / " + (page.mem[1] / 1024).toFixed(1) + " GB"
                    accent: page.memPercent >= 90 ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.neutralTextColor
                }
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
            title: "Temperature"
            RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Rectangle { width: 10; height: 10; radius: 5; color: chart.colorA } Text { text: "CPU"; color: Kirigami.Theme.textColor }
                Rectangle { width: 10; height: 10; radius: 5; color: chart.colorB } Text { text: "GPU"; color: Kirigami.Theme.textColor }
                Item { Layout.fillWidth: true }
                Text { text: "Show"; color: Kirigami.Theme.textColor; opacity: 0.7 }
                QQC2.ComboBox {
                    id: rangeBox
                    // seconds of history on screen; samples are one per second
                    readonly property var spans: [300, 600, 1800, 3600, 86400]
                    model: ["5 min", "10 min", "30 min", "1 hour", "1 day"]
                    currentIndex: Math.max(0, spans.indexOf(App.chartRange))
                    onActivated: App.chartRange = spans[currentIndex]
                }
            }
            Sparkline { id: chart; Layout.fillWidth: true; minValue: 20; maxValue: 100; gridStep: 20; windowSeconds: App.chartRange }
        }
    }
}
