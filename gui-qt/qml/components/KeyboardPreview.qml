import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../Utils.js" as U

// Four-zone keyboard. Zones light with Lighting.zones; click selects a zone.
Item {
    id: root
    property int selected: -1          // -1 = all zones
    property var zones: Lighting.zones || [[0,0,0],[0,0,0],[0,0,0],[0,0,0]]
    property real brightness: (Lighting.brightness || 0) / 100
    property bool off: Lighting.effect === "off"
    signal zoneClicked(int index)
    implicitHeight: Kirigami.Units.gridUnit * 8
    implicitWidth: Kirigami.Units.gridUnit * 24

    Rectangle {
        anchors.fill: parent
        radius: Kirigami.Units.largeSpacing
        color: Qt.darker(Kirigami.Theme.backgroundColor, 1.35)
        border.color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.15)
        RowLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing
            Repeater {
                model: 4
                delegate: Rectangle {
                    id: zone
                    required property int index
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: Kirigami.Units.smallSpacing
                    readonly property color zoneColor: root.off ? "#101010" : U.rgbToColor(root.zones[index])
                    color: Qt.rgba(zoneColor.r, zoneColor.g, zoneColor.b, 0.25 + 0.75 * root.brightness)
                    Behavior on color { enabled: root.visible; ColorAnimation { duration: 200 } }
                    border.width: root.selected === index ? 2 : 1
                    border.color: root.selected === index ? Kirigami.Theme.highlightColor
                                  : Qt.rgba(1, 1, 1, 0.12)
                    // key grid
                    Grid {
                        anchors.fill: parent
                        anchors.margins: Kirigami.Units.smallSpacing
                        columns: 4
                        spacing: 3
                        Repeater {
                            model: 16
                            delegate: Rectangle {
                                width: (zone.width - Kirigami.Units.smallSpacing * 2 - 9) / 4
                                height: (zone.height - Kirigami.Units.smallSpacing * 2 - 9) / 4
                                radius: 2
                                color: Qt.rgba(0, 0, 0, 0.35)
                                border.color: Qt.rgba(zone.zoneColor.r, zone.zoneColor.g, zone.zoneColor.b, 0.6 * root.brightness)
                            }
                        }
                    }
                    Text {
                        anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 4
                        text: "Zone " + (zone.index + 1)
                        color: "white"; opacity: 0.75; font: Kirigami.Theme.smallFont
                    }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.zoneClicked(zone.index) }
                }
            }
        }
    }
}
