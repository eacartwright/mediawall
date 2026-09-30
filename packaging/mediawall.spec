# PyInstaller recipe for MediaWall. Run by packaging/build.py, which
# first renders the icons into build/icon/.
#
# Output: dist/MediaWall/, a self-contained app folder (Python, Qt,
# FFmpeg, the QML files). On Windows it holds two programs:
#   MediaWall.exe      the one to run: starts the app without a console
#   MediaWall-app.exe  the app itself (a console program, for the Log)
# On Linux it holds one program, mediawall.

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICON_DIR = ROOT / "build" / "icon"
WINDOWS = sys.platform == "win32"

# Python modules the app never uses. (Qt's own unused parts are
# removed from the collected files below.)
EXCLUDES = ["tkinter", "unittest", "pydoc_data", "test"]

# Parts of Qt MediaWall doesn't use. PySide6 ships all of Qt and
# PyInstaller collects every QML module it finds, so collected files
# whose path contains any of these are dropped. (Qt names them
# Qt6<Name>.dll / libQt6<Name>.so, qml/Qt<Name>, qml/QtQuick/<Name>.)
# MediaWall's QML imports: QtQuick, QtQuick.Controls (Fusion style),
# QtQuick.Layouts, QtQuick.Shapes, QtMultimedia, Qt.labs.qmlmodels.
UNUSED_QT = [
    "WebEngine", "WebView", "WebChannel", "WebSockets", "3D", "Charts",
    "DataVisualization", "Graphs", "Pdf", "qpdf", "Location", "Positioning",
    "Sensors", "SerialPort", "SerialBus", "Bluetooth", "Nfc", "RemoteObjects",
    "Scxml", "StateMachine", "Sql", "VirtualKeyboard", "TextToSpeech",
    "SpatialAudio", "HttpServer", "Protobuf", "Grpc", "Lottie", "Timeline",
    "WavefrontMesh", "Qt5Compat", "Particles", "QuickTest", "Qt6Test",
    "VectorImage", "Designer", "Linguist", "Assistant", "qmlls", "qmllint",
    "qmlformat", "qmltooling", "translations",
    # Controls styles other than Fusion
    "FluentWinUI3", "Imagine", "Material", "Universal", "NativeStyle",
    # Qt's software OpenGL; Qt Quick draws with Direct3D on Windows
    "opengl32sw",
]


def keep(entry):
    dest = entry[0].replace("\\", "/")
    return not any(part in dest for part in UNUSED_QT)


def analysis(script, **options):
    a = Analysis([str(script)], pathex=[str(ROOT)], excludes=EXCLUDES, **options)
    a.binaries = [e for e in a.binaries if keep(e)]
    a.datas = [e for e in a.datas if keep(e)]
    return a


app = analysis(
    ROOT / "main.py",
    datas=[(str(ROOT / "qml"), "qml"), (str(ROOT / "assets"), "assets")],
    # Used only from QML, so PyInstaller can't see them in the Python
    # code: QtMultimedia brings Qt's FFmpeg plugin and libraries.
    hiddenimports=["PySide6.QtMultimedia", "PySide6.QtSvg"],
)
app_exe = EXE(
    PYZ(app.pure),
    app.scripts,
    [],
    exclude_binaries=True,
    name="MediaWall-app" if WINDOWS else "mediawall",
    icon=str(ICON_DIR / "mediawall.ico") if WINDOWS else None,
    console=True,
)
parts = [app_exe, app.binaries, app.datas]

if WINDOWS:
    launcher = analysis(ROOT / "packaging" / "windows_launcher.py")
    parts += [
        EXE(
            PYZ(launcher.pure),
            launcher.scripts,
            [],
            exclude_binaries=True,
            name="MediaWall",
            icon=str(ICON_DIR / "mediawall.ico"),
            console=False,
        ),
        launcher.binaries,
        launcher.datas,
    ]

COLLECT(*parts, name="MediaWall")
