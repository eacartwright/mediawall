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
    }
}
