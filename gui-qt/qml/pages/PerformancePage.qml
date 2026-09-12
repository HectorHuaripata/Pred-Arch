import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../Utils.js" as U

Kirigami.ScrollablePage {
    id: page
    title: "Performance"
    padding: Kirigami.Units.largeSpacing * 2

    readonly property bool hasFans: (System.features || []).indexOf("fan_control") >= 0
    readonly property var fanSpeed: Thermal.fanSpeed || [0, 0]
    readonly property var curves: Thermal.fanCurves || {}

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Card {
            title: "Performance profile"
            subtitle: "also switched by the mode button and Plasma"
            ProfileBar {}
            Text { text: "Current: " + U.profileLabel(Thermal.profile); color: Kirigami.Theme.textColor; opacity: 0.7 }
        }

        Card {
            title: "Game mode"
            subtitle: "performance profile + CPU energy preference, restored on exit"
            RowLayout {
                BoundSwitch { bound: Power.gameMode === true; apply: v => Bus.call("Power", "SetGameMode", [v]); text: checked ? "On" : "Off" }
                Item { Layout.fillWidth: true }
                Text { text: Power.epp ? "EPP: " + Power.epp : ""; color: Kirigami.Theme.textColor; opacity: 0.6 }
            }
        }

        Card {
            title: "Fans"
            visible: page.hasFans
            subtitle: ({ "auto": "EC controls the fans", "manual": "fixed duty", "curve": "following a curve" })[Thermal.fanMode] || ""
            RowLayout {
                QQC2.ButtonGroup { id: fanGroup }
                QQC2.RadioButton { text: "Automatic"; checked: Thermal.fanMode === "auto"; QQC2.ButtonGroup.group: fanGroup
                    onClicked: Bus.call("Thermal", "SetFanAuto") }
                QQC2.RadioButton { text: "Manual"; checked: Thermal.fanMode === "manual"; QQC2.ButtonGroup.group: fanGroup
                    onClicked: Bus.call("Thermal", "SetFanSpeed", [Math.max(30, page.fanSpeed[0]), Math.max(30, page.fanSpeed[1])]) }
                QQC2.RadioButton { text: "Curve"; checked: Thermal.fanMode === "curve"; QQC2.ButtonGroup.group: fanGroup
                    onClicked: Bus.call("Thermal", "SetFanCurve", ["cpu", curveEditor.points]) }
            }
            GridLayout {
                columns: 3
                visible: Thermal.fanMode === "manual"
                Text { text: "CPU fan"; color: Kirigami.Theme.textColor }
                BoundSlider { id: cpuFan; Layout.fillWidth: true; from: 0; to: 100; stepSize: 5; bound: page.fanSpeed[0]
                    apply: v => Bus.call("Thermal", "SetFanSpeed", [v, gpuFan.value]) }
                Text { text: Math.round(cpuFan.value) + " %"; color: Kirigami.Theme.textColor; Layout.minimumWidth: 40 }
                Text { text: "GPU fan"; color: Kirigami.Theme.textColor }
                BoundSlider { id: gpuFan; Layout.fillWidth: true; from: 0; to: 100; stepSize: 5; bound: page.fanSpeed[1]
                    apply: v => Bus.call("Thermal", "SetFanSpeed", [cpuFan.value, v]) }
                Text { text: Math.round(gpuFan.value) + " %"; color: Kirigami.Theme.textColor; Layout.minimumWidth: 40 }
            }
            ColumnLayout {
                id: curveEditor
                visible: Thermal.fanMode === "curve" || curveToggle.checked
                property var points: (page.curves.cpu && page.curves.cpu[1] && page.curves.cpu[1].length) ? page.curves.cpu[1] : [[40, 30], [60, 50], [75, 75], [85, 100]]
                QQC2.CheckBox { id: curveToggle; text: "Edit CPU curve"; visible: Thermal.fanMode !== "curve" }
                Repeater {
                    model: curveEditor.points.length
                    delegate: RowLayout {
                        required property int index
                        Text { text: "at"; color: Kirigami.Theme.textColor }
                        QQC2.SpinBox { from: 0; to: 110; value: curveEditor.points[index][0]; onValueModified: { var p = curveEditor.points.slice(); p[index] = [value, p[index][1]]; curveEditor.points = p } }
                        Text { text: "°C  →"; color: Kirigami.Theme.textColor }
                        QQC2.SpinBox { from: 0; to: 100; stepSize: 5; value: curveEditor.points[index][1]; onValueModified: { var p = curveEditor.points.slice(); p[index] = [p[index][0], value]; curveEditor.points = p } }
                        Text { text: "%"; color: Kirigami.Theme.textColor }
                        QQC2.ToolButton { icon.name: "list-remove"; enabled: curveEditor.points.length > 2; onClicked: { var p = curveEditor.points.slice(); p.splice(index, 1); curveEditor.points = p } }
                    }
                }
                RowLayout {
                    QQC2.Button { text: "Add point"; icon.name: "list-add"; onClicked: { var p = curveEditor.points.slice(); var last = p[p.length - 1]; p.push([Math.min(110, last[0] + 5), Math.min(100, last[1] + 5)]); curveEditor.points = p } }
                    QQC2.Button { text: "Apply curve"; icon.name: "dialog-ok-apply"; onClicked: Bus.call("Thermal", "SetFanCurve", ["cpu", curveEditor.points.slice().sort((a, b) => a[0] - b[0])]) }
                    QQC2.Button { text: "Stop curve"; visible: Thermal.fanMode === "curve"; onClicked: Bus.call("Thermal", "ClearFanCurve", ["cpu"]) }
                }
            }
        }
    }
}
