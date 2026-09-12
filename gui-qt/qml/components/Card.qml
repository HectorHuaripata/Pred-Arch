import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// A titled surface. Content goes in `contentItem`'s column.
Kirigami.AbstractCard {
    id: root
    property string title: ""
    property string subtitle: ""
    default property alias content: column.data
    Layout.fillWidth: true
    contentItem: ColumnLayout {
        spacing: Kirigami.Units.largeSpacing
        RowLayout {
            visible: root.title !== ""
            Kirigami.Heading { level: 3; text: root.title; Layout.fillWidth: true }
            Text { text: root.subtitle; visible: text !== ""; color: Kirigami.Theme.textColor; opacity: 0.6; font: Kirigami.Theme.smallFont }
        }
        ColumnLayout { id: column; spacing: Kirigami.Units.largeSpacing; Layout.fillWidth: true }
    }
}
