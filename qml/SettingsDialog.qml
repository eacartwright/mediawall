import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// App-wide settings (bridge/app_settings.py). Changes apply at once and
// are saved immediately; Close just closes. Opened from the toolbar.

Dialog {
    id: dialog

    title: "Settings"
    modal: true
    standardButtons: Dialog.Close

    anchors.centerIn: Overlay.overlay
    width: 460

    ColumnLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 6

        // ---- Mouse-wheel zoom step ----

        Label {
            text: "Mouse-wheel zoom step"
            font.bold: true
        }

        RowLayout {
            spacing: 8

            SpinBox {
                id: zoomStepBox

                from: appSettings.zoomStepMin
                to: appSettings.zoomStepMax
                editable: true

                value: appSettings.zoomStep
                onValueModified: appSettings.zoomStep = value

                textFromValue: function(value) { return value + " %" }
                valueFromText: function(text) { return parseInt(text) }
            }

            Label {
                text: "per wheel notch"
                color: "#bbbbbb"
            }

            Item { Layout.fillWidth: true }

            Button {
                text: "Default (" + appSettings.zoomStepDefault + " %)"
                enabled: appSettings.zoomStep !== appSettings.zoomStepDefault
                onClicked: appSettings.resetZoomStep()
            }
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "How much each notch of the mouse wheel zooms: free images and "
                  + "containers, browsing containers, Adjust mode, and browser previews."
            color: "#999999"
            font.pixelSize: 12
        }

        // ---- Playback speed range ----

        Label {
            Layout.topMargin: 12
            text: "Playback speed range"
            font.bold: true
        }

        RowLayout {
            spacing: 8

            Label { text: "Slowest" }

            // Hundredths, shown as a speed: 25 -> "0.25×".
            SpinBox {
                from: 25
                to: 100
                stepSize: 25
                value: Math.round(appSettings.speedMin * 100)
                onValueModified: appSettings.speedMin = value / 100
                textFromValue: function(value) { return (value / 100).toFixed(2) + "×" }
                valueFromText: function(text) { return Math.round(parseFloat(text) * 100) }
            }

            Label { text: "Fastest"; Layout.leftMargin: 8 }

            SpinBox {
                from: 100
                to: 400
                stepSize: 25
                value: Math.round(appSettings.speedMax * 100)
                onValueModified: appSettings.speedMax = value / 100
                textFromValue: function(value) { return (value / 100).toFixed(2) + "×" }
                valueFromText: function(text) { return Math.round(parseFloat(text) * 100) }
            }

            Item { Layout.fillWidth: true }

            Button {
                text: "Default"
                enabled: appSettings.speedMin !== appSettings.speedMinDefault
                         || appSettings.speedMax !== appSettings.speedMaxDefault
                onClicked: appSettings.resetSpeedRange()
            }
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "The range of the speed slider in the Audio tab (default "
                  + appSettings.speedMinDefault + "× to " + appSettings.speedMaxDefault
                  + "×). With Keep pitch off, pitch follows speed."
            color: "#999999"
            font.pixelSize: 12
        }
    }
}
