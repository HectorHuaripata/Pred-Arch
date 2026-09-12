import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "Utils.js" as U

// Sidebar navigation with lazily created pages. Pages are created the
// first time they are shown and kept afterwards.

Kirigami.ApplicationWindow {
    id: root
    title: "Archer"
    width: Kirigami.Units.gridUnit * 62
    height: Kirigami.Units.gridUnit * 41
    minimumWidth: Kirigami.Units.gridUnit * 48
    minimumHeight: Kirigami.Units.gridUnit * 31

    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None
    pageStack.defaultColumnWidth: width

    readonly property var sections: [
        { title: qsTr("Overview"),        icon: "utilities-system-monitor",  source: "pages/OverviewPage.qml" },
        { title: qsTr("Performance"),     icon: "speedometer",               source: "pages/PerformancePage.qml" },
        { title: qsTr("Lighting"),        icon: "input-keyboard",            source: "pages/LightingPage.qml" },
        { title: qsTr("Battery & Power"), icon: "battery",                   source: "pages/PowerPage.qml" },
        { title: qsTr("Display & Audio"), icon: "video-display",             source: "pages/DisplayAudioPage.qml" },
        { title: qsTr("System"),          icon: "computer",                  source: "pages/SystemPage.qml" }
    ]
    property int currentSection: 0
    property var visited: [true, false, false, false, false, false]
    onCurrentSectionChanged: {
        if (!visited[currentSection]) { var v = visited.slice(); v[currentSection] = true; visited = v }
        App.overviewVisible = currentSection === 0
    }

    // Close → tray when there is one.
    onClosing: close => { if (App.hasTray) { close.accepted = false; root.hide() } }

    Connections {
        target: Bus
        function onCallFailed(iface, method, kind, message) {
            if (kind === "NotAuthorized") return      // the polkit agent already told the user
            root.showPassiveNotification(iface + "." + method + ": " + message, "long")
        }
    }

    pageStack.initialPage: Kirigami.Page {
        padding: 0
        RowLayout {
            anchors.fill: parent
            spacing: 0

            // ---- Sidebar -------------------------------------------------
            Rectangle {
                Layout.fillHeight: true
                Layout.preferredWidth: Kirigami.Units.gridUnit * 13
                Kirigami.Theme.colorSet: Kirigami.Theme.Window
                Kirigami.Theme.inherit: false
                color: Kirigami.Theme.backgroundColor

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.largeSpacing

                    RowLayout {
                        spacing: Kirigami.Units.largeSpacing
                        // The Archer SVG is white; tint it with the theme's text colour so it reads on light schemes too.
                        Kirigami.Icon { source: App.iconPath !== "" ? App.iconPath : "computer"; isMask: App.iconPath !== ""; color: Kirigami.Theme.textColor; Layout.preferredWidth: Kirigami.Units.iconSizes.medium; Layout.preferredHeight: Kirigami.Units.iconSizes.medium }
                        ColumnLayout {
                            spacing: 0
                            Kirigami.Heading { level: 2; text: "Archer" }
                            QQC2.Label { text: U.capitalize(System.laptopType || ""); opacity: 0.6; font: Kirigami.Theme.smallFont }
                        }
                    }

                    ListView {
                        id: nav
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: root.sections
                        currentIndex: root.currentSection
                        spacing: 2
                        interactive: false
                        delegate: QQC2.ItemDelegate {
                            required property var modelData
                            required property int index
                            width: nav.width
                            text: modelData.title
                            icon.name: modelData.icon
                            highlighted: root.currentSection === index
                            onClicked: root.currentSection = index
                        }
                    }

                    // Connection status
                    RowLayout {
                        spacing: Kirigami.Units.smallSpacing
                        Rectangle { width: 9; height: 9; radius: 4.5
                            color: Bus.connected ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
                            Behavior on color { ColorAnimation { duration: 300 } } }
                        QQC2.Label {
                            Layout.fillWidth: true
                            text: Bus.connected ? qsTr("Daemon connected") : qsTr("Daemon offline")
                            opacity: 0.75; font: Kirigami.Theme.smallFont
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: Telemetry.intervalMs > 0
                        text: qsTr("live · %1 ms").arg(Telemetry.intervalMs)
                        opacity: 0.5; font: Kirigami.Theme.smallFont
                    }
                }
            }
            Kirigami.Separator { Layout.fillHeight: true }

            // ---- Content -------------------------------------------------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    Layout.margins: visible ? Kirigami.Units.largeSpacing : 0
                    visible: !Bus.connected
                    type: Kirigami.MessageType.Error
                    text: Bus.error !== "" ? Bus.error : qsTr("Waiting for the Archer daemon…")
                }
                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: root.currentSection
                    Repeater {
                        model: root.sections
                        delegate: Loader {
                            required property var modelData
                            required property int index
                            active: root.visited[index]
                            source: modelData.source
                        }
                    }
                }
            }
        }
    }
}
