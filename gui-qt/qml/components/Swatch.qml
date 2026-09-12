import QtQuick
import org.kde.kirigami as Kirigami

// A clickable colour sample.
Rectangle {
    id: root
    signal clicked()
    property bool round: false
    width: Kirigami.Units.gridUnit * 2
    height: round ? width : Kirigami.Units.gridUnit * 1.4
    radius: round ? width / 2 : Kirigami.Units.smallSpacing
    border.width: 1
    border.color: Qt.rgba(0, 0, 0, 0.3)
    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
