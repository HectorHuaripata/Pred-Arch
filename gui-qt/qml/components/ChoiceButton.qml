import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// One option of a mutually exclusive set. `current` says whether the daemon
// reports this option as active; the accent follows the daemon, not the click.
QQC2.Button {
    id: root
    property bool current: false
    checkable: true
    checked: current
    onCurrentChanged: checked = current
    onClicked: checked = current
    // qqc2-desktop-style draws "checked" very quietly in dark themes, so
    // mark the active option with the theme's accent explicitly.
    Rectangle {
        anchors.fill: parent
        radius: 3
        visible: root.current
        color: Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.22)
        border.width: 2
        border.color: Kirigami.Theme.highlightColor
    }
}
