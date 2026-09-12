import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Secondary text: explanations under a control, subtitles, notes.
QQC2.Label {
    opacity: 0.65
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
    font: Kirigami.Theme.smallFont
}
