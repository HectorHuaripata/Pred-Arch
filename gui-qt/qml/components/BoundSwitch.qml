import QtQuick
import QtQuick.Controls as QQC2

// A Switch that shows a daemon property and reverts if the setter fails.
QQC2.Switch {
    id: root
    property bool bound: false
    property var apply: function(v) {}
    checked: bound
    onBoundChanged: checked = bound
    onToggled: apply(checked)
    Connections {
        target: Bus
        function onCallFailed(iface, method, kind, message) { root.checked = root.bound }
    }
}
