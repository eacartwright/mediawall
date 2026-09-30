# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

MediaWall is a desktop app (Python + PySide6/QML, QtMultimedia) for arranging images, GIFs, video, and viewports freely on a canvas. `readme.md` is the full design document (~2400 lines). Consult it by section number: the code cites sections like "readme section 52" often. Key sections: 2.3 (source/instance/viewport), 37 (dev environment), 38 (structure and layering), 39 (roadmap and phase status), 47 (undo), 50 (current state and known limitations), 51 (the prioritised backlog: what to work on next), 52 (the architectural rule), and 55 (decision log and open decisions). When a feature changes, update the matching readme sections (the roadmap status, 50 Current State, and 55 Decision Log).

New errors, requested changes, and feature ideas are collected in the **Inbox** at the top of readme section 51 (the backlog), then sorted into its Next / Soon / Later lists.

## Commands

Use the project's own venv (`venv/`, gitignored). Do not use any other project's environment.

```powershell
.\venv\Scripts\python.exe main.py                     # run
.\venv\Scripts\python.exe main.py path\to\x.mediawall # run and open a project
.\venv\Scripts\python.exe -m unittest                 # all tests
.\venv\Scripts\python.exe -m unittest tests.test_containers                       # one module
.\venv\Scripts\python.exe -m unittest tests.test_containers.FittedSizeTests.test_cover_and_contain   # one test
```

On Linux: `venv/bin/python` instead. Setup: `python -m venv venv` followed by `pip install -r requirements.txt`. PySide6 is pinned to an exact version and must stay at 6.10 or newer, because pitch compensation needs Qt 6.10.

`bridge/log_capture.py` redirects file descriptors 1 and 2 into a pipe at startup, so all output (FFmpeg, Qt, Python) goes to the in-app Log window and `logs/mediawall.log`, and is echoed to the terminal only if one exists. When checking app output, read `logs/mediawall.log`. `launcher.pyw` and `tools/create_launchers.py` make the double-click launchers (readme section 37).

The unit tests cover `core/` only. They need no Qt or display and finish in milliseconds. Run them after any `core/` change.

App checks (`tests/app/`, readme section 37) start the real app and drive it (about 110 checks, ~1.5 minutes; need a display and `tests/media/`): `.\venv\Scripts\python.exe tests\app\run.py [name ...]` (Linux: `venv/bin/python tests/app/run.py`). Run them after QML or bridge changes, and update or add a `check_*.py` when behaviour changes. They use `tests/app/harness.py` (`Check`: timed steps, input helpers, `js()` in Main.qml's context, `item_js()` / `center_of()` to find items by `objectName`). There is no linter or build step. `tests/media/` (gitignored) holds sample media for manual testing.

## Architecture

### Layering: `qml → bridge → core`

- **`core/`** is plain Python and must never import Qt or `bridge/`. It holds all logic and data: `scene.py` (`MediaSource`, `SceneObject`, `Scene`, geometry and z-order), `project.py` (JSON save/load), `history.py` (undo/redo), and `media_browser.py` (folder scanning and extension-based type detection). This separation is what makes Qt-free tests, direct serialization, and snapshot undo possible.
- **`bridge/`** is the Qt glue. `SceneModel` (a `QAbstractListModel`) exposes the scene to QML and turns QML slot calls into `core` operations. `ProjectController` handles New/Open/Save dialogs, the dirty flag, and the window title.
- **`qml/`** renders model rows and handles live interaction. It never owns persistent state.
- App commands (toolbar, menus, shortcuts) are Qt Quick `Action`s defined once in `qml/AppActions.qml`; controls use `action: appActions.<name>`. Add new commands there rather than wiring buttons and `Shortcut`s separately.
- `main.py` wires `sceneModel`, `projectController`, `browserBackend`, and `appSettings` (app-wide settings via QSettings, `bridge/app_settings.py`) into QML as context properties. Set `MEDIAWALL_SETTINGS` to an `.ini` path when running the app in tests, so the user's real settings are never changed. It sets `QML_DISABLE_DISK_CACHE=1`, because stale compiled QML causes errors like "Type X unavailable".

### Source → Instance → Viewport (readme section 52; do not collapse these)

- `MediaSource` exists once per file, in `scene.sources`, keyed by id. It holds only the path, type, and size.
- A `SceneObject` of type `"media"` is an instance that refers to a source by `source_id`. Many instances can share one source, each with its own geometry and playback state.
- A `"container"` is a viewport. It holds at most one media instance, linked by the child's `parent_id`. It never holds a filename directly.
- A `"browser"` is a workspace object with folder and index state.
- `SceneObject` is one flat dataclass whose fields apply per type. Saved fields are listed per type in `TYPE_FIELDS` in `core/project.py`. A new persistent field must be added there as well.

### Coordinates

`x, y` is the top-left of the unrotated box, and rotation is in degrees around the box's center. Top-level objects use scene coordinates. A container's content uses the container's local, unrotated space, where (0,0) is the container's top-left. That is why pan, zoom, and rotation inside a container are independent of the container. `z` orders only top-level objects.

### Model rows and roles

Model rows are **top-level objects only**. Container content is not a row. It is exposed through the container row's `content*` / `contentSource*` roles and edited through the container's id (for example `commitContent(containerId, ...)`). `Main.qml` uses a `Repeater` with a `DelegateChooser` on `objectType` to choose `MediaObject`, `BrowserObject`, or `ContainerObject`. Role groups (`GEOMETRY_ROLES`, `PLAYBACK_ROLES`, and others) at the top of `bridge/scene_model.py` control which roles are emitted when something changes.

### Interaction → model → undo

- During a drag, resize, or rotate, QML moves the item directly. On release it sends the final values once (`commitGeometry`) and re-binds to the model, so later changes from Python (load, undo) reach the canvas.
- Every change to saved state in `SceneModel` must end with `_changed()`. It records the previous snapshot in `History` and emits `modified`. Browser fields are saved but excluded from undo (`_changed(workspace_only=True)`), and selection is neither saved nor undone.
- Undo stores whole-scene deep-copy snapshots (`core/history.py`), so new actions become undoable without extra code. The history is also saved next to the project as `<project>.history` (`core/history_file.py`), matched to the saved project by a content fingerprint. For rapid repeated changes such as wheel zoom, call `sceneModel.setMergeKey("zoom:" + id)` before the change so they merge into one step.
- `_apply_state` diffs the target snapshot against the live scene and inserts or removes only the rows that changed. Untouched delegates survive, so browsers don't rescan and videos and GIFs keep playing. Keep that behavior when changing undo or reset code.

### Persistence (`core/project.py`)

Projects are `.mediawall` JSON files. Media is stored as paths, never as bytes. Each source keeps its original absolute path plus a path relative to the project file. Loading is tolerant: bad values, unknown types, and missing files produce warnings and a recoverable scene (missing files show a "Missing file" box), and only an unreadable file fails. Saves are atomic (write to a temp file, then replace). Object ids are random (`new_id`), so merging layouts cannot collide.

## Conventions

- Match filename case exactly (`Main.qml`, not `main.qml`). Development happens on both Windows and Linux (Linux is primary), and Linux file names are case-sensitive.
- Keep platform-specific code isolated. Every Python package folder needs an `__init__.py` (unittest discovery depends on it).
- Guiding rule (readme section 56): keep the architectural boundaries, and build the smallest working version of the current feature rather than adding speculative complexity.

## Development environments
- Developed on both Windows and Linux Mint. Linux Mint is the primary target; every change must keep working there.
- Never write Windows-only or Linux-only commands or paths without noting the other platform's equivalent.
- The venv is at `venv/` on each machine (not committed).
  - Windows: `venv\Scripts\python.exe`
  - Linux: `venv/bin/python`
- Run the app from the project root: `python main.py` (venv activated).
- Linux filesystems are case-sensitive: file names and QML imports must match exactly in case.
- Qt Multimedia uses the FFmpeg backend on both platforms.

## Working context
- Architecture rules and decisions: see `readme.md`.
- Current errors, changes and planned features: see readme section 51 (Inbox, then Next / Soon / Later).
- Propose a plan before making large or multi-file changes.