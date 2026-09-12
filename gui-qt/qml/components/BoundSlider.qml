import QtQuick
import QtQuick.Controls as QQC2

// A Slider bound to a daemon property. Applies live while dragging, at most
// every `throttleMs`, plus once on release; reverts on failure.
QQC2.Slider {
    id: root
    property real bound: 0
    property int throttleMs: 60
    property var apply: function(v) {}
    property bool _dirty: false
    value: bound
    onBoundChanged: if (!pressed) value = bound
    onMoved: { _dirty = true; if (!throttle.running) { throttle.start(); flush() } }
    onPressedChanged: if (!pressed) flush()
    function flush() { if (_dirty) { _dirty = false; apply(value) } }
    Timer { id: throttle; interval: root.throttleMs; onTriggered: root.flush() }
    Connections {
        target: Bus
        function onCallFailed(iface, method, kind, message) { if (!root.pressed) root.value = root.bound }
    }
}
