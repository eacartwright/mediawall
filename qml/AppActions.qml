import QtQuick
import QtQuick.Controls

// Every app command, defined once: its name, keyboard shortcut, and
// when it's available. Toolbar buttons, menus, and the sidebar use these
// (Button { action: appActions.undo }), so each command is wired in one
// place, and a later UI pass (menu bar, icons) only rearranges them
// (readme section 25).
//
// Commands that change the canvas are off in Present.

Item {
    id: actions

    // The main window (mode state), and the windows opened from here.
    required property var window
    property var settingsDialog
    property var logWindow

    readonly property bool editing: !window.presenting
    readonly property bool hasSelection: sceneModel.selectedId !== ""

    // ---- File ----

    readonly property Action newWall: Action {
        text: "New"
        shortcut: StandardKey.New
        enabled: actions.editing
        onTriggered: projectController.newProject()
    }

    readonly property Action open: Action {
        text: "Open"
        shortcut: StandardKey.Open
        enabled: actions.editing
        onTriggered: projectController.openProject()
    }

    readonly property Action save: Action {
        text: "Save"
        shortcut: StandardKey.Save
        onTriggered: projectController.save()
    }

    readonly property Action saveAs: Action {
        text: "Save As"
        shortcut: "Ctrl+Shift+S"       // StandardKey.SaveAs has no binding on Windows
        onTriggered: projectController.saveAs()
    }

    readonly property Action saveLayout: Action {
        text: "Save Layout…"
        onTriggered: projectController.saveLayout()
    }

    readonly property Action newFromLayout: Action {
        text: "New from Layout…"
        enabled: actions.editing
        onTriggered: projectController.newFromLayout()
    }

    readonly property Action addLayout: Action {
        text: "Add Layout to Wall…"
        enabled: actions.editing
        onTriggered: projectController.addLayoutToWall()
    }

    // ---- Edit ----

    readonly property Action undo: Action {
        text: "Undo"
        shortcut: StandardKey.Undo
        enabled: actions.editing && sceneModel.canUndo
        onTriggered: sceneModel.undo()
    }

    readonly property Action redo: Action {
        text: "Redo"
        shortcut: "Ctrl+Shift+Z"       // Ctrl+Y too: a Shortcut in Main.qml
        enabled: actions.editing && sceneModel.canRedo
        onTriggered: sceneModel.redo()
    }

    readonly property Action duplicate: Action {
        text: "Duplicate"
        shortcut: "Ctrl+D"
        enabled: actions.editing && actions.hasSelection
        onTriggered: sceneModel.duplicateSelected()
    }

    readonly property Action deleteSelected: Action {
        text: "Delete"
        shortcut: StandardKey.Delete
        enabled: actions.editing && actions.hasSelection
        onTriggered: sceneModel.removeSelected()
    }

    // ---- Arrange (the selected object, within its stacking group) ----

    readonly property Action bringToFront: Action {
        text: "Bring to Front"
        shortcut: "Ctrl+Shift+Up"
        enabled: actions.editing && actions.hasSelection && !sceneModel.selectedAtFront
        onTriggered: sceneModel.bringToFront(sceneModel.selectedId)
    }

    readonly property Action bringForward: Action {
        text: "Bring Forward"
        shortcut: "Ctrl+Up"
        enabled: actions.editing && actions.hasSelection && !sceneModel.selectedAtFront
        onTriggered: sceneModel.bringForward(sceneModel.selectedId)
    }

    readonly property Action sendBackward: Action {
        text: "Send Backward"
        shortcut: "Ctrl+Down"
        enabled: actions.editing && actions.hasSelection && !sceneModel.selectedAtBack
        onTriggered: sceneModel.sendBackward(sceneModel.selectedId)
    }

    readonly property Action sendToBack: Action {
        text: "Send to Back"
        shortcut: "Ctrl+Shift+Down"
        enabled: actions.editing && actions.hasSelection && !sceneModel.selectedAtBack
        onTriggered: sceneModel.sendToBack(sceneModel.selectedId)
    }

    // ---- Files (a selected browser or browsing container) ----

    // The selected object, if it steps through a folder's files.
    readonly property var fileStepper: {
        var item = window.objectItem(sceneModel.selectedId)
        return item && item.stepsFiles ? item : null
    }

    readonly property Action previousFile: Action {
        text: "Previous File"
        shortcut: "Left"
        enabled: actions.fileStepper !== null
        onTriggered: actions.fileStepper.stepFiles(-1)
    }

    readonly property Action nextFile: Action {
        text: "Next File"
        shortcut: "Right"
        enabled: actions.fileStepper !== null
        onTriggered: actions.fileStepper.stepFiles(1)
    }

    // ---- Insert ----

    readonly property Action addBrowser: Action {
        text: "Add Browser"
        enabled: actions.editing
        onTriggered: sceneModel.addBrowser(100 + Math.random() * 100,
                                           100 + Math.random() * 100)
    }

    readonly property Action addContainer: Action {
        text: "Add Container"
        enabled: actions.editing
        onTriggered: sceneModel.addContainer(150 + Math.random() * 100,
                                             150 + Math.random() * 100)
    }

    // ---- View ----

    // F11: Full Screen on/off (from Present: back to where you were).
    readonly property Action fullScreen: Action {
        text: "Full Screen"
        shortcut: "F11"
        onTriggered: {
            if (actions.window.presenting)
                actions.window.presenting = false
            else
                actions.window.fullScreenEditing = !actions.window.fullScreenEditing
        }
    }

    readonly property Action present: Action {
        text: "Present"
        shortcut: "F5"
        onTriggered: actions.window.presenting = !actions.window.presenting
    }

    readonly property Action settings: Action {
        text: "Settings"
        onTriggered: actions.settingsDialog.open()
    }

    // Messages the app would print to a terminal.
    readonly property Action log: Action {
        text: "Log"
        onTriggered: {
            actions.logWindow.show()
            actions.logWindow.raise()
            actions.logWindow.requestActivate()
        }
    }
}
