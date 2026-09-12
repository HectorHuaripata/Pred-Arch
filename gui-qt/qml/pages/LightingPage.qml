import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../Utils.js" as U

// Keyboard zones and effects, mode-button LED, lid logo, backlight timeout.
// Every control applies as it moves; the daemon coalesces bursts.
Kirigami.ScrollablePage {
    id: page
    title: qsTr("Lighting")
    padding: Kirigami.Units.largeSpacing * 2

    readonly property var zones: Lighting.zones || [[255, 255, 255], [255, 255, 255], [255, 255, 255], [255, 255, 255]]
    readonly property bool eneBackend: Lighting.backend === "ene"
    readonly property bool effectActive: Lighting.effect !== "static" && Lighting.effect !== "off"
    readonly property string preferredEffect: "Wave"
    property int selectedZone: -1                 // -1 = all zones

    function setZone(index, color) {
        var rgb = U.colorToRgb(color)
        if (index < 0) Bus.call("Lighting", "SetZones", [[rgb, rgb, rgb, rgb], Lighting.brightness])
        else Bus.call("Lighting", "SetZoneMask", [1 << index, rgb])
    }
    function applyEffect(name, rgb, speed, direction) {
        Bus.call("Lighting", "SetEffect", [name, Lighting.brightness, rgb || Lighting.effectColor,
                                           speed !== undefined ? speed : Lighting.effectSpeed,
                                           direction || Lighting.effectDirection || "right"])
    }
    function startEffect() {
        var choices = Lighting.effectChoices || []
        applyEffect(choices.indexOf(preferredEffect) >= 0 ? preferredEffect : (choices[1] || choices[0] || preferredEffect))
    }

    ColorDialog {
        id: zoneDialog
        title: page.selectedZone < 0 ? qsTr("Colour for all zones") : qsTr("Colour for zone %1").arg(page.selectedZone + 1)
        onSelectedColorChanged: if (visible) page.setZone(page.selectedZone, selectedColor)   // live while picking
        onAccepted: page.setZone(page.selectedZone, selectedColor)
    }
    ColorDialog { id: effectDialog; title: qsTr("Effect colour"); onAccepted: page.applyEffect(Lighting.effect, U.colorToRgb(selectedColor)) }
    ColorDialog { id: logoDialog; title: qsTr("Lid logo colour"); onAccepted: Bus.call("Lighting", "SetLogo", [U.colorToRgb(selectedColor), Lighting.logoBrightness]) }
    ColorDialog {
        id: buttonDialog
        property string profile: ""
        title: qsTr("Button colour for %1").arg(Catalog.profileLabel(profile))
        onAccepted: Bus.call("Lighting", "SetButtonColor", [profile, U.colorToRgb(selectedColor)])
    }
    ColorDialog {
        id: buttonFixedDialog
        title: qsTr("Mode button colour")
        onSelectedColorChanged: if (visible) Bus.call("Lighting", "SetButtonFixedColor", [U.colorToRgb(selectedColor)])   // live
        onAccepted: Bus.call("Lighting", "SetButtonFixedColor", [U.colorToRgb(selectedColor)])
    }

    function applyPreset(colours) {           // {profile: [r, g, b]}
        Bus.call("Lighting", "SetButtonColors", [colours])
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: Lighting.backend === "wmi"
            type: Kirigami.MessageType.Warning
            text: qsTr("Driving the keyboard through ACPI-WMI. On some Predator models this path reports success but changes nothing; the ENE backend is needed there.")
        }

        Card {
            title: qsTr("Keyboard")
            subtitle: page.eneBackend ? qsTr("ENE K5130 · %1").arg(Lighting.effect === "off" ? qsTr("off") : Lighting.effect) : (Lighting.backend || "")
            KeyboardPreview {
                Layout.fillWidth: true
                selected: page.selectedZone
                onZoneClicked: index => { page.selectedZone = (page.selectedZone === index ? -1 : index) }
            }
            RowLayout {
                spacing: Kirigami.Units.largeSpacing
                ChoiceButton { text: qsTr("Static colour"); icon.name: "color-picker"; current: Lighting.effect === "static"
                    onClicked: Bus.call("Lighting", "SetZones", [page.zones, Lighting.brightness]) }
                ChoiceButton { text: qsTr("Effect"); icon.name: "view-refresh"; current: page.effectActive; onClicked: page.startEffect() }
                ChoiceButton { text: qsTr("Off"); icon.name: "system-shutdown"; current: Lighting.effect === "off"; onClicked: Bus.call("Lighting", "SetOff") }
                Item { Layout.fillWidth: true }
                QQC2.Label { text: qsTr("Brightness") }
                BoundSlider { Layout.preferredWidth: Kirigami.Units.gridUnit * 10; from: 0; to: 100; bound: Lighting.brightness || 0
                    apply: v => Bus.call("Lighting", "SetBrightness", [v]) }
            }
        }

        Card {
            title: page.selectedZone < 0 ? qsTr("Colour · all zones") : qsTr("Colour · zone %1").arg(page.selectedZone + 1)
            subtitle: qsTr("click a zone in the preview to colour it alone")
            visible: !page.effectActive
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: Catalog.swatches
                    delegate: Swatch { required property string modelData; round: true; color: modelData; onClicked: page.setZone(page.selectedZone, color) }
                }
                QQC2.Button { text: qsTr("Custom…"); icon.name: "color-management"
                    onClicked: { zoneDialog.selectedColor = U.rgbToColor(page.zones[Math.max(0, page.selectedZone)]); zoneDialog.open() } }
            }
        }

        Card {
            title: qsTr("Effect")
            visible: page.effectActive || Lighting.effect === "static"
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: (Lighting.effectChoices || []).filter(n => n !== "Static")
                    delegate: ChoiceButton { required property string modelData; text: modelData; current: Lighting.effect === modelData; onClicked: page.applyEffect(modelData) }
                }
            }
            GridLayout {
                columns: 4
                visible: page.effectActive
                QQC2.Label { text: qsTr("Colour") }
                Swatch { color: U.rgbToColor(Lighting.effectColor); onClicked: { effectDialog.selectedColor = color; effectDialog.open() } }
                QQC2.Label { text: qsTr("Direction") }
                RowLayout {
                    ChoiceButton { icon.name: "go-previous"; current: Lighting.effectDirection === "left"; onClicked: page.applyEffect(Lighting.effect, undefined, undefined, "left") }
                    ChoiceButton { icon.name: "go-next"; current: Lighting.effectDirection === "right"; onClicked: page.applyEffect(Lighting.effect, undefined, undefined, "right") }
                }
                QQC2.Label { text: qsTr("Speed") }
                BoundSlider { Layout.columnSpan: 3; Layout.fillWidth: true; from: 0; to: 9; stepSize: 1; snapMode: QQC2.Slider.SnapAlways; bound: Lighting.effectSpeed || 0
                    apply: v => page.applyEffect(Lighting.effect, undefined, v) }
            }
            Hint { visible: page.eneBackend; text: qsTr("Speed and direction bytes are not decoded on the ENE K5130 yet; they are sent but may be ignored.") }
        }

        Card {
            id: buttonCard
            title: qsTr("Mode button LED")
            visible: page.eneBackend
            subtitle: qsTr("the mode key itself does nothing on Linux, but its LED is yours")
            readonly property bool follows: Lighting.buttonFollowsProfile === true
            RowLayout {
                spacing: Kirigami.Units.smallSpacing
                ChoiceButton { text: qsTr("One colour per profile"); icon.name: "view-list-details"; current: buttonCard.follows
                    onClicked: Bus.call("Lighting", "SetButtonFollowsProfile", [true]) }
                ChoiceButton { text: qsTr("Always the same colour"); icon.name: "color-picker"; current: !buttonCard.follows
                    onClicked: Bus.call("Lighting", "SetButtonFollowsProfile", [false]) }
            }

            // -- per profile ------------------------------------------------
            Hint { visible: buttonCard.follows; text: qsTr("Click a colour to change it. The bar under each profile button shows the same mapping.") }
            Flow {
                visible: buttonCard.follows
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                Repeater {
                    model: Thermal.profileChoices || []
                    delegate: RowLayout {
                        required property string modelData
                        Swatch { round: true; width: Kirigami.Units.gridUnit * 1.3; color: U.rgbToColor((Lighting.buttonColors || ({}))[modelData] || [128, 128, 128])
                            onClicked: { buttonDialog.profile = modelData; buttonDialog.selectedColor = color; buttonDialog.open() } }
                        QQC2.Label { text: Catalog.profileLabel(modelData) }
                    }
                }
            }
            RowLayout {
                visible: buttonCard.follows
                spacing: Kirigami.Units.smallSpacing
                QQC2.Label { text: qsTr("Presets"); opacity: 0.7 }
                Repeater {
                    model: Catalog.buttonPresets            // [[id, label, {profile: "#rrggbb"}], …]
                    delegate: QQC2.Button {
                        required property var modelData
                        text: modelData[1]
                        onClicked: page.applyPreset(modelData[2])
                        // preview strip of the preset's colours
                        Row {
                            anchors.bottom: parent.bottom; anchors.bottomMargin: 2; anchors.horizontalCenter: parent.horizontalCenter
                            spacing: 1
                            Repeater {
                                model: Thermal.profileChoices || []
                                delegate: Rectangle { required property string modelData; width: 7; height: 3; radius: 1
                                    readonly property var rgb: (parent.parent.parent.modelData[2])[modelData]
                                    color: rgb ? U.rgbToColor(rgb) : "transparent" }
                            }
                        }
                    }
                }
                QQC2.Button { text: qsTr("Factory colours"); icon.name: "edit-undo"; onClicked: Bus.call("Lighting", "ResetButtonColors") }
            }

            // -- one colour -------------------------------------------------
            Flow {
                visible: !buttonCard.follows
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: Catalog.swatches
                    delegate: Swatch { required property string modelData; round: true; color: modelData
                        onClicked: Bus.call("Lighting", "SetButtonFixedColor", [U.colorToRgb(color)]) }
                }
                QQC2.Button { text: qsTr("Custom…"); icon.name: "color-management"
                    onClicked: { buttonFixedDialog.selectedColor = U.rgbToColor(Lighting.buttonColor); buttonFixedDialog.open() } }
            }
            RowLayout {
                visible: !buttonCard.follows
                Swatch { round: true; width: Kirigami.Units.gridUnit * 1.3; color: U.rgbToColor(Lighting.buttonColor) }
                Hint { text: qsTr("Current button colour. It is kept across profile changes and after resume.") }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing * 2
            Card {
                title: qsTr("Lid logo")
                visible: page.eneBackend
                RowLayout {
                    Swatch { color: U.rgbToColor(Lighting.logoColor); onClicked: { logoDialog.selectedColor = color; logoDialog.open() } }
                    QQC2.Label { text: qsTr("Brightness") }
                    BoundSlider { Layout.fillWidth: true; from: 0; to: 100; bound: Lighting.logoBrightness || 0
                        apply: v => Bus.call("Lighting", "SetLogo", [Lighting.logoColor, v]) }
                }
            }
            Card {
                title: qsTr("Backlight timeout")
                visible: (System.features || []).indexOf("backlight_timeout") >= 0
                BoundSwitch { text: qsTr("Turn the keyboard off after 30 s idle"); bound: Lighting.backlightTimeout === true; apply: v => Bus.call("Lighting", "SetBacklightTimeout", [v]) }
            }
        }
    }
}
