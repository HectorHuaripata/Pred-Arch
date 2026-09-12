import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// Small uppercase caption over a number or a group.
QQC2.Label {
    property string label: ""
    text: label.toUpperCase()
    opacity: 0.7
    font: Kirigami.Theme.smallFont
}
