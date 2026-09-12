import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "Utils.js" as U

Kirigami.ApplicationWindow {
    id: root
    title: "Archer"
    width: 1120
    height: 740
    minimumWidth: 860
    minimumHeight: 560

    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None
    pageStack.defaultColumnWidth: width

    readonly property var sections: [
        { title: "Overview",        icon: "utilities-system-monitor",  source: "pages/OverviewPage.qml" },
        { title: "Performance",     icon: "speedometer",               source: "pages/PerformancePage.qml" },
        { title: "Lighting",        icon: "input-keyboard",            source: "pages/LightingPage.qml" },
        { title: "Battery & Power", icon: "battery",                   source: "pages/PowerPage.qml" },
        { title: "Display & Audio", icon: "video-display",             source: "pages/DisplayAudioPage.qml" },
        { title: "System",          icon: "computer",                  source: "pages/SystemPage.qml" }
    ]
    property int currentSection: 0
    // Pages are created the first time they are shown and kept afterwards.
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
                        Kirigami.Icon { source: App.iconPath !== "" ? App.iconPath : "computer"; Layout.preferredWidth: Kirigami.Units.iconSizes.medium; Layout.preferredHeight: Kirigami.Units.iconSizes.medium }
                        ColumnLayout {
                            spacing: 0
                            Kirigami.Heading { level: 2; text: "Archer" }
                            Text { text: System.laptopType ? System.laptopType.charAt(0).toUpperCase() + System.laptopType.slice(1) : ""; color: Kirigami.Theme.textColor; opacity: 0.6; font: Kirigami.Theme.smallFont }
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
                        Text {
                            Layout.fillWidth: true
                            text: Bus.connected ? "Daemon connected" : "Daemon offline"
                            color: Kirigami.Theme.textColor; opacity: 0.75; font: Kirigami.Theme.smallFont
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: Telemetry.intervalMs > 0
                        text: "live · " + Telemetry.intervalMs + " ms"
                        color: Kirigami.Theme.textColor; opacity: 0.5; font: Kirigami.Theme.smallFont
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
                    text: Bus.error !== "" ? Bus.error : "Waiting for the Archer daemon…"
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
