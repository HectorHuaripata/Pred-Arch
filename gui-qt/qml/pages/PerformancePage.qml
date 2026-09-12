import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"

// Profile, game mode and fan control.
Kirigami.ScrollablePage {
    id: page
    title: qsTr("Performance")
    padding: Kirigami.Units.largeSpacing * 2

    readonly property bool hasFans: (System.features || []).indexOf("fan_control") >= 0
    readonly property var fanSpeed: Thermal.fanSpeed || [0, 0]
    readonly property var curves: Thermal.fanCurves || ({})
    // Starting point for a new curve: (°C, %) pairs.
    readonly property var defaultCurve: [[40, 30], [60, 50], [75, 75], [85, 100]]
    readonly property int manualStartPercent: 30

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Card {
            title: qsTr("Performance profile")
            subtitle: qsTr("also switched by the mode button and Plasma")
            ProfileBar {}
            Hint { text: qsTr("Current: %1").arg(Catalog.profileLabel(Thermal.profile || "")) }
        }

        Card {
            title: qsTr("Game mode")
            subtitle: qsTr("performance profile + CPU energy preference, restored on exit")
            RowLayout {
                BoundSwitch { bound: Power.gameMode === true; apply: v => Bus.call("Power", "SetGameMode", [v]); text: checked ? qsTr("On") : qsTr("Off") }
                Item { Layout.fillWidth: true }
                Hint { text: Power.epp ? qsTr("EPP: %1").arg(Power.epp) : ""; Layout.fillWidth: false }
            }
        }

        Card {
            title: qsTr("Fans")
            visible: page.hasFans
            subtitle: ({ "auto": qsTr("EC controls the fans"), "manual": qsTr("fixed duty"), "curve": qsTr("following a curve") })[Thermal.fanMode] || ""
            RowLayout {
                QQC2.ButtonGroup { id: fanGroup }
                QQC2.RadioButton { text: qsTr("Automatic"); checked: Thermal.fanMode === "auto"; QQC2.ButtonGroup.group: fanGroup
                    onClicked: Bus.call("Thermal", "SetFanAuto") }
                QQC2.RadioButton { text: qsTr("Manual"); checked: Thermal.fanMode === "manual"; QQC2.ButtonGroup.group: fanGroup
                    onClicked: Bus.call("Thermal", "SetFanSpeed", [Math.max(page.manualStartPercent, page.fanSpeed[0]), Math.max(page.manualStartPercent, page.fanSpeed[1])]) }
                QQC2.RadioButton { text: qsTr("Curve"); checked: Thermal.fanMode === "curve"; QQC2.ButtonGroup.group: fanGroup
                    onClicked: Bus.call("Thermal", "SetFanCurve", ["cpu", curveEditor.points]) }
            }
            GridLayout {
                columns: 3
                visible: Thermal.fanMode === "manual"
                QQC2.Label { text: qsTr("CPU fan") }
                BoundSlider { id: cpuFan; Layout.fillWidth: true; from: 0; to: 100; stepSize: 5; bound: page.fanSpeed[0]
                    apply: v => Bus.call("Thermal", "SetFanSpeed", [v, gpuFan.value]) }
                QQC2.Label { text: Math.round(cpuFan.value) + " %"; Layout.minimumWidth: Kirigami.Units.gridUnit * 3 }
                QQC2.Label { text: qsTr("GPU fan") }
                BoundSlider { id: gpuFan; Layout.fillWidth: true; from: 0; to: 100; stepSize: 5; bound: page.fanSpeed[1]
                    apply: v => Bus.call("Thermal", "SetFanSpeed", [cpuFan.value, v]) }
                QQC2.Label { text: Math.round(gpuFan.value) + " %"; Layout.minimumWidth: Kirigami.Units.gridUnit * 3 }
            }
            ColumnLayout {
                id: curveEditor
                visible: Thermal.fanMode === "curve" || curveToggle.checked
                property var points: (page.curves.cpu && page.curves.cpu[1] && page.curves.cpu[1].length) ? page.curves.cpu[1] : page.defaultCurve
                function replacePoint(index, point) { var p = points.slice(); p[index] = point; points = p }
                QQC2.CheckBox { id: curveToggle; text: qsTr("Edit CPU curve"); visible: Thermal.fanMode !== "curve" }
                Repeater {
                    model: curveEditor.points.length
                    delegate: RowLayout {
                        required property int index
                        QQC2.Label { text: qsTr("at") }
                        QQC2.SpinBox { from: 0; to: 110; value: curveEditor.points[index][0]
                            onValueModified: curveEditor.replacePoint(index, [value, curveEditor.points[index][1]]) }
                        QQC2.Label { text: qsTr("°C  →") }
                        QQC2.SpinBox { from: 0; to: 100; stepSize: 5; value: curveEditor.points[index][1]
                            onValueModified: curveEditor.replacePoint(index, [curveEditor.points[index][0], value]) }
                        QQC2.Label { text: "%" }
                        QQC2.ToolButton { icon.name: "list-remove"; enabled: curveEditor.points.length > 2
                            onClicked: { var p = curveEditor.points.slice(); p.splice(index, 1); curveEditor.points = p } }
                    }
                }
                RowLayout {
                    QQC2.Button { text: qsTr("Add point"); icon.name: "list-add"
                        onClicked: { var p = curveEditor.points.slice(); var last = p[p.length - 1]; p.push([Math.min(110, last[0] + 5), Math.min(100, last[1] + 5)]); curveEditor.points = p } }
                    QQC2.Button { text: qsTr("Apply curve"); icon.name: "dialog-ok-apply"
                        onClicked: Bus.call("Thermal", "SetFanCurve", ["cpu", curveEditor.points.slice().sort((a, b) => a[0] - b[0])]) }
                    QQC2.Button { text: qsTr("Stop curve"); visible: Thermal.fanMode === "curve"; onClicked: Bus.call("Thermal", "ClearFanCurve", ["cpu"]) }
                }
            }
        }
    }
}
