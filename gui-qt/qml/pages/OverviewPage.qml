import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../Utils.js" as U

// Live readings: gauges, fans, battery and the temperature history.
Kirigami.ScrollablePage {
    id: page
    title: qsTr("Overview")
    padding: Kirigami.Units.largeSpacing * 2

    readonly property var battery: Telemetry.battery || [false, 0, "unknown", -1]
    readonly property bool batteryPresent: battery[0]
    readonly property real batteryPercent: battery[1]
    readonly property string batteryStatus: battery[2]
    readonly property int batterySeconds: battery[3]
    // [used MiB, total MiB]; absent on a daemon older than 2.1
    readonly property var memory: Telemetry.memory || [0, 0]
    readonly property real memoryPercent: memory[1] > 0 ? 100 * memory[0] / memory[1] : 0
    readonly property var fanRpm: Telemetry.fanRpm || [0, 0]
    readonly property bool hasNpu: (System.features || []).indexOf("npu") >= 0
    // Six gauges (with an NPU) need to be a little smaller to share one row.
    readonly property real gaugeUnits: hasNpu ? 6.5 : 8
    readonly property var drives: Storage.drives || []          // [[name, model, bytes, temp], …]
    readonly property var filesystems: Storage.filesystems || [] // [[mount, device, fstype, size, used], …]

    function gibibytes(bytes) { return (bytes / 1073741824).toFixed(bytes >= 107374182400 ? 0 : 1) }
    function tempAccentDrive(celsius) { return U.tempColor(Kirigami.Theme, celsius, Settings.tempWarnC, Settings.tempHotC) }

    function gigabytes(mib) { return (mib / 1024).toFixed(1) }
    function tempAccent(celsius) { return U.tempColor(Kirigami.Theme, celsius, Settings.tempWarnC, Settings.tempHotC) }
    function remaining(seconds) {
        var h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60)
        return h > 0 ? qsTr("%1 h %2 min").arg(h).arg(m) : qsTr("%1 min").arg(m)
    }

    // One chart sample per period while the page is on screen. The daemon
    // only announces *changes*, so sampling on a change signal would freeze
    // the time axis whenever the temperature is steady.
    Timer {
        interval: Settings.chartSampleMs
        running: page.visible && Bus.connected && Telemetry.intervalMs > 0
        repeat: true
        onTriggered: { History.push(Telemetry.cpuTemp || 0, Telemetry.gpuTemp || 0); chart.refresh() }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 0
                Kirigami.Heading { level: 1; text: System.productName || qsTr("Acer laptop") }
                Hint { text: [System.cpuModel, System.gpuModel].filter(s => s).join(" · "); elide: Text.ElideRight; wrapMode: Text.NoWrap }
            }
            Item { Layout.fillWidth: true }
            ProfileBar {}
        }

        Card {
            title: qsTr("Right now")
            subtitle: Telemetry.intervalMs > 0 ? qsTr("updating every %1 ms").arg(Telemetry.intervalMs) : qsTr("paused")
            GridLayout {
                // five gauges of 8 grid units fit from roughly 840 px of page width
                columns: Math.max(2, Math.min(6, Math.floor((page.width - Kirigami.Units.gridUnit * 3)
                                                             / (Kirigami.Units.gridUnit * page.gaugeUnits + Kirigami.Units.largeSpacing))))
                columnSpacing: Kirigami.Units.largeSpacing
                rowSpacing: Kirigami.Units.largeSpacing
                Layout.alignment: Qt.AlignHCenter
                Gauge { implicitWidth: Kirigami.Units.gridUnit * page.gaugeUnits; label: qsTr("CPU temperature"); unit: "°C"; maxValue: 110; value: Telemetry.cpuTemp || 0; accent: page.tempAccent(value) }
                Gauge { implicitWidth: Kirigami.Units.gridUnit * page.gaugeUnits; label: qsTr("GPU temperature"); unit: "°C"; maxValue: 110; value: Telemetry.gpuTemp || 0; accent: page.tempAccent(value) }
                Gauge { implicitWidth: Kirigami.Units.gridUnit * page.gaugeUnits; label: qsTr("CPU usage"); unit: "%"; value: Telemetry.cpuUsage || 0
                        note: Telemetry.cpuFreqMhz > 0 ? qsTr("%1 MHz").arg(Telemetry.cpuFreqMhz) : "" }
                Gauge { implicitWidth: Kirigami.Units.gridUnit * page.gaugeUnits; label: qsTr("GPU usage"); unit: "%"; value: Telemetry.gpuUsage || 0
                        note: Telemetry.gpuPowerW > 0 ? qsTr("%1 W").arg(Telemetry.gpuPowerW.toFixed(1)) : "" }
                Gauge { implicitWidth: Kirigami.Units.gridUnit * page.gaugeUnits; visible: page.hasNpu; label: qsTr("NPU usage"); unit: "%"; value: Telemetry.npuUsage || 0; accent: Kirigami.Theme.activeTextColor }
                Gauge {
                    implicitWidth: Kirigami.Units.gridUnit * page.gaugeUnits
                    visible: page.memory[1] > 0
                    label: qsTr("Memory"); unit: "%"; value: page.memoryPercent
                    note: qsTr("%1 / %2 GB").arg(page.gigabytes(page.memory[0])).arg(page.gigabytes(page.memory[1]))
                    accent: page.memoryPercent >= Settings.memoryHotPercent ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.neutralTextColor
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing * 2
            Card {
                title: qsTr("Fans")
                subtitle: ({ "auto": qsTr("automatic"), "manual": qsTr("manual"), "curve": qsTr("curve") })[Thermal.fanMode] || ""
                RowLayout {
                    spacing: Kirigami.Units.gridUnit * 2
                    StatTile { label: qsTr("CPU fan"); unit: qsTr("rpm"); value: page.fanRpm[0] }
                    StatTile { label: qsTr("GPU fan"); unit: qsTr("rpm"); value: page.fanRpm[1] }
                }
            }
            Card {
                title: qsTr("Battery")
                subtitle: Telemetry.powerSourceAc ? qsTr("on AC power") : qsTr("on battery")
                visible: page.batteryPresent
                StatTile {
                    label: qsTr("Charge"); unit: "%"; value: page.batteryPercent
                    note: [Catalog.batteryStatusLabel(page.batteryStatus),
                           page.batterySeconds >= 0
                               ? (page.batteryStatus === "charging" ? qsTr("%1 to full") : qsTr("%1 left")).arg(page.remaining(page.batterySeconds))
                               : "",
                           Battery.limiter ? qsTr("limit 80 %") : ""].filter(s => s).join(" · ")
                }
            }
        }

        Card {
            title: qsTr("Storage")
            visible: page.drives.length > 0 || page.filesystems.length > 0
            subtitle: qsTr("refreshed every 10 s")
            Repeater {
                model: page.drives
                delegate: RowLayout {
                    required property var modelData
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon { source: "drive-harddisk"; Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium; Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium }
                    QQC2.Label { text: modelData[1]; Layout.fillWidth: true; elide: Text.ElideRight }
                    QQC2.Label { text: qsTr("%1 GB").arg(page.gibibytes(modelData[2])); opacity: 0.7 }
                    QQC2.Label { visible: modelData[3] >= 0; text: qsTr("%1 °C").arg(modelData[3]); color: page.tempAccentDrive(modelData[3]) }
                }
            }
            Repeater {
                model: page.filesystems
                delegate: ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 2
                    readonly property real fraction: modelData[3] > 0 ? modelData[4] / modelData[3] : 0
                    RowLayout {
                        QQC2.Label { text: modelData[0]; font.weight: Font.DemiBold }
                        QQC2.Label { text: modelData[2]; opacity: 0.6; font: Kirigami.Theme.smallFont }
                        Item { Layout.fillWidth: true }
                        QQC2.Label { text: qsTr("%1 / %2 GB").arg(page.gibibytes(modelData[4])).arg(page.gibibytes(modelData[3])); opacity: 0.8 }
                    }
                    QQC2.ProgressBar { Layout.fillWidth: true; from: 0; to: 1; value: fraction }
                }
            }
        }

        Card {
            title: qsTr("Temperature")
            RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Rectangle { width: Kirigami.Units.smallSpacing * 2.5; height: width; radius: width / 2; color: chart.colorA }
                QQC2.Label { text: qsTr("CPU") }
                Rectangle { width: Kirigami.Units.smallSpacing * 2.5; height: width; radius: width / 2; color: chart.colorB }
                QQC2.Label { text: qsTr("GPU") }
                Item { Layout.fillWidth: true }
                QQC2.Label { text: qsTr("Show"); opacity: 0.7 }
                QQC2.ComboBox {
                    readonly property var ranges: Catalog.chartRanges       // [[seconds, label], …]
                    model: ranges.map(r => r[1])
                    currentIndex: Math.max(0, ranges.findIndex(r => r[0] === Settings.chartRange))
                    onActivated: Settings.chartRange = ranges[currentIndex][0]
                }
            }
            Sparkline { id: chart; Layout.fillWidth: true; minValue: 20; maxValue: 100; gridStep: 20; windowSeconds: Settings.chartRange }
        }
    }
}
