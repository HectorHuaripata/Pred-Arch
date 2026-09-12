import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../Utils.js" as U

Kirigami.ScrollablePage {
    id: page
    title: "Lighting"
    padding: Kirigami.Units.largeSpacing * 2

    readonly property var zones: Lighting.zones || [[255,255,255],[255,255,255],[255,255,255],[255,255,255]]
    readonly property bool ene: Lighting.backend === "ene"
    readonly property bool isEffect: Lighting.effect !== "static" && Lighting.effect !== "off"
    property int selectedZone: -1

    function setZone(index, color) {
        var rgb = U.colorToRgb(color)
        if (index < 0) Bus.call("Lighting", "SetZones", [[rgb, rgb, rgb, rgb], Lighting.brightness])
        else Bus.call("Lighting", "SetZoneMask", [1 << index, rgb])
    }

    ColorDialog {
        id: zoneDialog
        title: page.selectedZone < 0 ? "Colour for all zones" : "Colour for zone " + (page.selectedZone + 1)
        onSelectedColorChanged: if (visible) page.setZone(page.selectedZone, selectedColor)   // live while picking
        onAccepted: page.setZone(page.selectedZone, selectedColor)
    }
    ColorDialog {
        id: effectDialog
        title: "Effect colour"
        onAccepted: page.applyEffect(Lighting.effect, U.colorToRgb(selectedColor))
    }
    ColorDialog {
        id: logoDialog
        title: "Lid logo colour"
        onAccepted: Bus.call("Lighting", "SetLogo", [U.colorToRgb(selectedColor), Lighting.logoBrightness])
    }
    ColorDialog {
        id: buttonDialog
        property string profile: ""
        title: "Button colour for " + U.profileLabel(profile)
        onAccepted: Bus.call("Lighting", "SetButtonColor", [profile, U.colorToRgb(selectedColor)])
    }

    function applyEffect(name, rgb) {
        Bus.call("Lighting", "SetEffect", [name, Lighting.brightness, rgb || Lighting.effectColor,
                                           Lighting.effectSpeed, Lighting.effectDirection || "right"])
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: Lighting.backend === "wmi"
            type: Kirigami.MessageType.Warning
            text: "Driving the keyboard through ACPI‑WMI. On some Predator models this path reports success but changes nothing; the ENE backend is needed there."
        }

        Card {
            title: "Keyboard"
            subtitle: Lighting.backend === "ene" ? "ENE K5130 · " + (Lighting.effect === "off" ? "off" : Lighting.effect) : Lighting.backend
            KeyboardPreview {
                Layout.fillWidth: true
                selected: page.selectedZone
                onZoneClicked: index => { page.selectedZone = (page.selectedZone === index ? -1 : index) }
            }
            RowLayout {
                spacing: Kirigami.Units.largeSpacing
                ChoiceButton { text: "Static colour"; icon.name: "color-picker"; current: Lighting.effect === "static"
                    onClicked: Bus.call("Lighting", "SetZones", [page.zones, Lighting.brightness]) }
                ChoiceButton { text: "Effect"; icon.name: "view-refresh"; current: page.isEffect
                    onClicked: { var c = Lighting.effectChoices || []; page.applyEffect(c.indexOf("Wave") >= 0 ? "Wave" : (c[1] || c[0] || "Wave")) } }
                ChoiceButton { text: "Off"; icon.name: "system-shutdown"; current: Lighting.effect === "off"
                    onClicked: Bus.call("Lighting", "SetOff") }
                Item { Layout.fillWidth: true }
                Text { text: "Brightness"; color: Kirigami.Theme.textColor }
                BoundSlider { Layout.preferredWidth: Kirigami.Units.gridUnit * 10; from: 0; to: 100; bound: Lighting.brightness || 0
                    apply: v => Bus.call("Lighting", "SetBrightness", [v]) }
            }
        }

        Card {
            title: page.selectedZone < 0 ? "Colour · all zones" : "Colour · zone " + (page.selectedZone + 1)
            subtitle: "click a zone in the preview to colour it alone"
            visible: !page.isEffect
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: ["#ffffff", "#ff3b30", "#ff9500", "#ffd60a", "#34c759", "#00c7be", "#0a84ff", "#5e5ce6", "#bf5af2", "#ff2d55"]
                    delegate: Rectangle {
                        required property string modelData
                        width: 34; height: 34; radius: 17; color: modelData
                        border.width: 2; border.color: Qt.rgba(0, 0, 0, 0.25)
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: page.setZone(page.selectedZone, parent.color) }
                    }
                }
                QQC2.Button { text: "Custom…"; icon.name: "color-management"
                    onClicked: { zoneDialog.selectedColor = U.rgbToColor(page.zones[Math.max(0, page.selectedZone)]); zoneDialog.open() } }
            }
        }

        Card {
            title: "Effect"
            visible: page.isEffect || Lighting.effect === "static"
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: (Lighting.effectChoices || []).filter(n => n !== "Static")
                    delegate: ChoiceButton {
                        required property string modelData
                        text: modelData; current: Lighting.effect === modelData
                        onClicked: page.applyEffect(modelData)
                    }
                }
            }
            GridLayout {
                columns: 4
                visible: page.isEffect
                Text { text: "Colour"; color: Kirigami.Theme.textColor }
                Rectangle { width: 34; height: 24; radius: 4; color: U.rgbToColor(Lighting.effectColor); border.color: Qt.rgba(0,0,0,0.3)
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { effectDialog.selectedColor = parent.color; effectDialog.open() } } }
                Text { text: "Direction"; color: Kirigami.Theme.textColor }
                RowLayout {
                    ChoiceButton { icon.name: "go-previous"; current: Lighting.effectDirection === "left"
                        onClicked: Bus.call("Lighting", "SetEffect", [Lighting.effect, Lighting.brightness, Lighting.effectColor, Lighting.effectSpeed, "left"]) }
                    ChoiceButton { icon.name: "go-next"; current: Lighting.effectDirection === "right"
                        onClicked: Bus.call("Lighting", "SetEffect", [Lighting.effect, Lighting.brightness, Lighting.effectColor, Lighting.effectSpeed, "right"]) }
                }
                Text { text: "Speed"; color: Kirigami.Theme.textColor }
                BoundSlider { Layout.columnSpan: 3; Layout.fillWidth: true; from: 0; to: 9; stepSize: 1; snapMode: QQC2.Slider.SnapAlways; bound: Lighting.effectSpeed || 0
                    apply: v => Bus.call("Lighting", "SetEffect", [Lighting.effect, Lighting.brightness, Lighting.effectColor, v, Lighting.effectDirection || "right"]) }
            }
            Text { visible: page.ene; text: "Speed and direction bytes are not decoded on the ENE K5130 yet; they are sent but may be ignored."; color: Kirigami.Theme.textColor; opacity: 0.6; font: Kirigami.Theme.smallFont; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        }

        Card {
            title: "Mode button LED"
            visible: page.ene
            subtitle: "coloured by the active profile, whoever changed it"
            BoundSwitch { text: "Follow the performance profile"; bound: Lighting.buttonFollowsProfile === true; apply: v => Bus.call("Lighting", "SetButtonFollowsProfile", [v]) }
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                Repeater {
                    model: Thermal.profileChoices || []
                    delegate: RowLayout {
                        required property string modelData
                        Rectangle { width: 22; height: 22; radius: 11; color: U.rgbToColor((Lighting.buttonColors || {})[modelData] || [128,128,128]); border.color: Qt.rgba(0,0,0,0.3)
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { buttonDialog.profile = modelData; buttonDialog.selectedColor = parent.color; buttonDialog.open() } } }
                        Text { text: U.profileLabel(modelData); color: Kirigami.Theme.textColor }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing * 2
            Card {
                title: "Lid logo"
                visible: page.ene
                RowLayout {
                    Rectangle { width: 34; height: 24; radius: 4; color: U.rgbToColor(Lighting.logoColor); border.color: Qt.rgba(0,0,0,0.3)
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { logoDialog.selectedColor = parent.color; logoDialog.open() } } }
                    Text { text: "Brightness"; color: Kirigami.Theme.textColor }
                    BoundSlider { Layout.fillWidth: true; from: 0; to: 100; bound: Lighting.logoBrightness || 0
                        apply: v => Bus.call("Lighting", "SetLogo", [Lighting.logoColor, v]) }
                }
            }
            Card {
                title: "Backlight timeout"
                visible: (System.features || []).indexOf("backlight_timeout") >= 0
                BoundSwitch { text: "Turn the keyboard off after 30 s idle"; bound: Lighting.backlightTimeout === true; apply: v => Bus.call("Lighting", "SetBacklightTimeout", [v]) }
            }
        }
    }
}
