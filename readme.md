# MediaWall — Complete Project Design Document

**Last updated:** 2026-09-22 20:54 EDT  
**Project status:** Working prototype: scene model, browsing, images, GIFs, video, containers, save/load, undo/redo  
**Target platform:** Cross-platform desktop; Linux (Mint/Ubuntu) primary, Windows also used for development  
**Primary implementation language:** Python  
**UI framework:** PySide6 + QML  
**Media playback:** QtMultimedia (FFmpeg backend)  
**Project/layout persistence:** JSON initially, with SQLite reserved for a later media index/library  
**Rendering philosophy:** GPU-accelerated Qt/QML scene graph; avoid CPU-side pixel processing for normal canvas operations

---

# 1. Project Overview

## 1.1 Concept

MediaWall is a local desktop application for creating interactive multimedia walls, digital scrapbooks, visual installations, presentations, and live media compositions.

The central concept is a large visual canvas on which the user can arrange media and viewports rather than a conventional document editor.

The application should feel closer to:

- a digital scrapbook,
- a multimedia mood board,
- a visual installation,
- a live media wall,
- a presentation canvas,
- or a personal interactive media display

than to a traditional file manager, slideshow editor, or video editor.

The user should be able to place media freely on a canvas, put media inside viewports/containers, browse media while still seeing the canvas, create slideshows, and eventually build dynamic presentations.

The canvas is the primary workspace.

---

# 2. Core Design Principles

## 2.1 The canvas is central

The canvas is not merely a preview of a document.

It is the application's primary interaction surface.

Objects should exist directly on the canvas and be manipulated there.

Examples:

- images
- videos
- containers
- browsers
- slideshows
- eventually text and other objects

---

## 2.2 Media files are references, not project contents

The application should normally NOT copy media files into a project.

Instead, projects retain references to the original filesystem paths.

Example:

```text
/home/alien/Pictures/Japan/IMG_001.jpg
```

The project stores the path and the object's state.

This means:

- projects remain relatively small,
- the same media can be used by multiple projects,
- cloning an object does not duplicate a file,
- collections do not duplicate media,
- layouts remain independent of the media themselves.

---

## 2.3 Separate source, instance, and viewport

This distinction is fundamental.

### Media Source

The underlying file.

Example:

```text
/home/alien/Pictures/Japan/IMG_001.jpg
```

A source has properties such as:

- filesystem path
- detected media type
- metadata
- dimensions
- duration
- available streams
- thumbnail/cache information later

---

### Media Instance

A particular use of a source on the canvas.

The same source can have many instances.

For example:

```text
photo.jpg
    ├── instance A
    │      └── container 1
    ├── instance B
    │      └── container 2
    └── instance C
           └── free-floating canvas object
```

Each instance can have independent:

- position
- size
- scale
- rotation
- crop
- zoom
- pan
- playback state
- volume
- visibility
- z-order
- containment

The file itself is not copied.

---

### Viewport / Container

A viewport determines where and how an instance is displayed.

A container is not simply "a box containing a file."

It is a viewing region with its own coordinate system.

The media inside it can be transformed independently of the container.

---

## 2.4 Workspace objects versus presentation objects

The application has two conceptual categories.

### Workspace/editor objects

These exist to help the user build the composition.

Examples:

- Browse Object
- media browser
- inspector
- layer panel
- media library
- temporary selection UI

These should normally disappear in presentation mode.

---

### Presentation objects

These are the actual content intended to appear during presentation.

Examples:

- images
- videos
- containers
- slideshows
- visual media objects
- audio tracks

The distinction allows the user to browse and edit without those controls becoming part of the final presentation.

---

# 3. Supported Media

## 3.1 Images

Initial target formats:

- JPG
- JPEG
- PNG
- GIF
- WebP

Future formats can be added without redesigning the media abstraction.

---

## 3.2 Video

Initial target formats:

- MP4
- AVI
- MKV
- MOV
- WMV
- 3GP

Playback is delegated to QtMultimedia (Qt's own player, using its FFmpeg backend) rather than implemented in Python. See the decision log.

---

## 3.3 Audio

Initial target formats:

- MP3
- M4A

Additionally, video files should be usable as audio sources.

For example:

```text
movie.mkv
```

could supply an audio track while its visual component is hidden.

The application should not need to extract the audio to another file just to play it.

The audio subsystem should select an appropriate audio stream from the source.

---

# 4. Main Object Types

The initial conceptual object types are:

```text
FREE MEDIA
CONTAINER
BROWSER
SLIDESHOW
```

These should eventually be represented as first-class scene objects.

---

# 5. Free Media Object

A Free Media Object is media placed directly on the canvas.

Examples:

- photograph
- video
- animated image
- eventually other media

The user can:

- move it
- scale it
- rotate it
- zoom it
- crop it
- change its display mode
- change its z-order
- duplicate/clone it

---

## 5.1 Aspect ratio

Aspect ratio should be preserved by default.

Possible display modes:

### Contain

Entire media fits inside the object's bounds.

No cropping.

### Cover

Media completely fills the object's bounds.

Some content may be cropped.

### Free

Independent width/height transformations are permitted.

### Stretch

The source is deliberately stretched to fill the object's dimensions.

The default should be aspect-ratio preserving.

**Decision (2026-09-26):** free media always keeps its aspect ratio; the other display modes are not planned. Contain and Cover exist where they matter, as a container's Fit Content / Fill Container, and cropping is done with Crop / Zoom Inside (section 5.2).

---

## 5.2 Zoom and crop (implemented)

- **Scaling:** the mouse wheel over a *selected* free image scales it around the pointer, keeping its aspect ratio (5% per wheel notch, proportional for trackpads; the same step is used for all wheel zoom). This is an accelerator for the resize handle. Unselected objects ignore the wheel, so scrolling over the canvas never resizes things by accident.
- **Cropping / zooming inside:** right-click → **Crop / Zoom Inside…** replaces the image with a container of exactly the same box, rotation, and stacking position, holding the image, and opens it in Adjust mode. Nothing visibly changes until you zoom or pan. Cropping is container behavior, so there is only one implementation of pan/zoom/crop.
- Containers made this way start with **Scale Content with Container off**, so dragging the frame's corner crops the image instead of scaling it. **Release Content** turns it back into a plain free image.

---

# 6. Container Object

A Container is a viewport.

Initially containers are rectangular.

Eventually they should support arbitrary clipping shapes.

Possible future shapes:

- rectangle
- rounded rectangle
- circle
- ellipse
- polygon
- SVG/path
- arbitrary vector path

---

## 6.1 Container coordinate system

A container has its own local coordinate system.

For example:

```text
Canvas
└── Container
    └── Media
```

The container controls the viewport.

The media controls its own transform within that viewport.

This permits effects such as:

- zooming into a photograph
- panning around a photograph
- rotating the photograph
- cropping the photograph
- keeping the container fixed while changing the media framing

---

## 6.2 Container clipping

Media inside a container should be clipped to the container's shape.

For a rectangle:

```text
┌─────────────────────────┐
│                         │
│       IMAGE             │
│                         │
└─────────────────────────┘
```

For a circle eventually:

```text
       ╭────────╮
     ╭─          ─╮
    │    IMAGE     │
     ╰─          ─╯
       ╰────────╯
```

The clipping mechanism should be designed so that arbitrary future shapes can be added without redesigning the object model.

---

## 6.3 Container resizing behavior

A container should support an option to lock media scaling to the container.

Two conceptual modes:

### Independent

Resizing the container changes the viewport only.

The media retains its own scale and transform.

### Locked

Resizing the container proportionally scales the media arrangement along with it.

This should be a property of the media/container relationship.

**Implemented:** as the container's "Scale Content with Container" setting (on by default), in its right-click menu. When on, the content keeps its center at the same relative position and scales by the larger of the two resize factors, so content that filled the container still fills it. When off, the content stays exactly where it is on the canvas and only the viewport changes, from whichever corner is dragged; this is how cropping works. Moving or rotating a container always carries its content along.

---

## 6.4 Implementation notes

- A container holds at most one media instance. The instance is an ordinary media object whose `parent_id` is the container, with its geometry in the container's local, unrotated coordinates (0, 0 = the container's top-left).
- Moving media into or out of a container re-parents that same instance, so its state (e.g. paused) carries over.
- Media gets into a container by dragging a free image onto it (the container highlights; holding Shift places the image on top instead), or by selecting the container and using a browser's **Add to Container** button. Only an empty container accepts media: a full one doesn't highlight as a drop target (the media lands on the canvas instead), and Add to Container is disabled for it. To change what a container holds, release or remove its content first.
- New content is framed to fill the container (cover). **Fit Content** and **Fill Container** re-frame it and reset its rotation.
- **Adjust mode** (double-click, or right-click → Adjust Content) turns dragging into panning, the mouse wheel into zoom around the pointer, and the rotation knob into content rotation. The part of the content outside the frame shows as a faint ghost, and a small toolbar offers Fit, Fill, and Done. The toolbar stays upright whatever the rotation, sits below the container (or above it when there's no room), and stays inside the visible canvas. Enter or Space also finishes adjusting, as do clicking elsewhere and Escape.
- The mouse wheel over a *selected* container (outside Adjust mode) scales the whole container around the pointer, content included, so the view inside the frame doesn't change. This happens whether or not "Scale Content with Container" is on; that setting only affects the resize handles.
- **Release Content** turns the content back into a free object at the position, size, and rotation it currently appears on the canvas. **Remove Content** deletes it. Deleting a container deletes its content.
- Only top-level objects take part in z-order; content has none of its own.
- Clipping is rectangular (`clip_shape: "rect"`, stored per container). Other shapes will replace the rectangular clip with a mask without changing the object model.

---

# 7. Overlapping Objects

Objects are allowed to overlap.

The scene therefore needs explicit z-order/layer management.

Required operations:

- Bring to Front
- Bring Forward
- Send Backward
- Send to Back

**Implemented:** all four operations, available from each object's right-click menu and from keyboard shortcuts (section 49). Selecting an object does NOT bring it to the front; otherwise "Send to Back" would be undone the moment the object was clicked again. New objects are created on top.

Eventually a dedicated Layers panel should provide:

- object list
- visibility toggle
- lock toggle
- z-order
- reordering
- object type
- object name

---

# 8. Cloning

"Clone" must mean creating another **media instance**, not copying the underlying media file.

Example:

```text
Source:
    /home/alien/Pictures/photo.jpg

Instances:

    Instance A
        Container 1
        scale = 1.0
        rotation = 0

    Instance B
        Container 2
        scale = 2.0
        rotation = 25
```

Both point to the same source.

This is important because a single photograph could appear:

- in multiple containers,
- at multiple scales,
- with different rotations,
- with different crops,
- simultaneously.

---

# 9. Browse Object

The Browse Object is one of the most important concepts in the application.

The user should NOT be forced to create a container before browsing for media.

Instead, browsing should itself be a movable/scalable object on the canvas.

---

## 9.1 Basic concept

A Browse Object behaves like a media browser that lives inside the canvas.

Example:

```text
┌──────────────────────────────────────────────────────────────┐
│                       CANVAS                                 │
│                                                              │
│      ┌─────────────────────────────┐                         │
│      │ Browse Object              │                         │
│      │                             │                         │
│      │       [PHOTO]               │                         │
│      │                             │                         │
│      │   ◀ Previous     Next ▶     │                         │
│      └─────────────────────────────┘                         │
│                                                              │
│                      [other media]                            │
└──────────────────────────────────────────────────────────────┘
```

The browser itself can:

- move
- resize
- potentially zoom
- scroll
- browse folders
- browse collections
- preview media
- step through media
- add the current item to the canvas

---

## 9.2 Browser does not automatically add media

Browsing should be non-destructive.

Viewing an image should NOT automatically place that image permanently on the canvas.

The user can browse until they find what they want.

Then they explicitly choose an action.

Possible actions:

```text
Add as Free Media
Add to Selected Container
Make Container
Add as Slideshow
```

---

## 9.3 Browser actions

The browser should eventually support context-sensitive actions.

Example:

If nothing is selected:

```text
Add to Canvas
    ├── Free Media
    ├── Container
    └── Slideshow
```

If a container is selected:

```text
Add to Selected Container
```

If a browser is itself inside a container:

```text
Use Current Item
```

The goal is to make the workflow natural rather than forcing the user through a rigid sequence.

---

# 10. Browse First and Container First

Both workflows should be supported.

## 10.1 Browse first

```text
Add Browser
     ↓
Choose folder
     ↓
Browse media
     ↓
Find image/video
     ↓
Add to Canvas
```

This is useful when the user doesn't know exactly what they want yet.

---

## 10.2 Container first

```text
Add Container
     ↓
Assign folder
     ↓
Browse inside container
     ↓
Select media
     ↓
Media appears in viewport
```

This is useful when the user already knows the visual structure they want.

Neither workflow should invalidate the other.

---

# 11. Browser State

A browser should retain enough state to allow the user to return to where they were.

Possible state:

```text
source folder
include subfolders
collection
file list
sort order
filter
current index
current file
scroll position
```

**Implemented:** folder, current index, and the include-subfolders setting are stored in the scene model. The file list itself is not stored; it is rescanned from the folder, so the browser always reflects what is actually on disk.

When subfolders are included, files directly in the chosen folder come first, then each subfolder in depth-first order, with natural sorting inside each folder (`IMG_2` before `IMG_10`). Hidden folders (names starting with `.`) are skipped, symlinked folders are not followed, and unreadable folders are skipped rather than failing the scan. The browser shows each file's path relative to the chosen folder, e.g. `Japan/Kyoto/temple.png`.

This allows a browser to effectively remember:

> "I was looking at the 37th image in this folder."

---

# 12. Collections

Collections are saved media queries / browsing definitions.

They do NOT copy media.

A collection could combine:

- directories
- individual files
- media type filters
- sorting
- potentially tags later

Example:

```text
Collection: Japan Trip

Folders:
    /Pictures/Japan/Tokyo
    /Pictures/Japan/Kyoto
    /Pictures/Japan/Osaka

Specific files:
    /Pictures/Japan/map.png
    /Pictures/Japan/itinerary.pdf   [future support]

Filter:
    images + video

Sort:
    date taken
```

A Browse Object can use a collection as its source.

---

# 13. Slideshow Object

A Slideshow Object is a canvas object that cycles through media.

It can be assigned a directory or collection.

The slideshow may display:

- images
- videos
- potentially mixed media

The media appears one at a time.

Future features include:

- transition effects
- duration
- ordering
- shuffle
- looping
- video playback rules
- per-item duration
- transition timing

---

# 14. Audio System

Audio is conceptually separate from visible canvas media.

There should be an Audio Rack / Audio Panel / Audio Flyout.

Audio does not necessarily need a visual representation on the canvas.

---

## 14.1 Audio tracks

Each audio track can contain:

- source
- selected stream
- volume
- mute
- solo/isolate
- loop
- playback speed
- pitch behavior
- play/pause
- position

Loop should be enabled by default.

---

## 14.2 Video as audio

A video can be used as an audio source.

Example:

```text
video.mkv
    ├── Video stream → hidden
    └── Audio stream → Audio Track
```

The user should be able to preview a video before adding it as an audio track.

Possible workflow:

```text
Browse video
      ↓
Preview video normally
      ↓
"Use as Audio"
      ↓
Hide visual
      ↓
Loop audio
```

No temporary extracted audio file should be necessary.

---

## 14.3 Volume controls

The audio rack should eventually support mouse-wheel volume adjustment.

Potential modifier behavior:

```text
Mouse wheel
    → volume

Modifier + mouse wheel
    → playback speed

Another modifier
    → pitch
```

Exact key bindings can be chosen later.

---

## 14.4 Speed and pitch

The user specifically wants behavior similar to Celluloid.

Changing playback speed should be able to affect pitch, with a future option for pitch preservation.

Conceptually:

```text
Playback Speed
    ├── affects pitch
    └── preserve pitch
```

This should be exposed as a setting rather than hard-coded.

Implementation: QtMultimedia's `playbackRate` sets speed, and `pitchCompensation` switches between the two behaviors above (off = pitch follows speed, as in Celluloid; on = pitch preserved). Check `pitchCompensationAvailability` at runtime and hide or disable the setting if the backend reports it unavailable.

## 14.5 Implemented so far (2026-09-26)

Every video instance (free, or a container's content) has its own, saved and undoable:

- **volume**, **mute**, **play/pause**, **loop** (as before)
- **speed**, 0.25x to 4x (`speed`), and **Keep pitch** (`preserve_pitch`, off by default so pitch follows speed). `pitchCompensation` was confirmed available on Windows with PySide6 6.11.2.
- an **A-B loop** (`loop_a` / `loop_b`, milliseconds, -1 = not set). Looping between them happens only when both are set; the points are kept in order, and points less than 0.1 s apart are rejected. Set them at the current position from the right-click menu (Set Loop Start (A) Here / Set Loop End (B) Here / Clear A–B Loop) or the Audio tab. The seek bar shows A and B markers and the looped span. Reaching B seeks back to A (deferred to the next event-loop turn: the FFmpeg backend ignores a seek made inside `positionChanged`).

The sidebar's **Audio** tab (next to Layers) lists every video instance, top first, each with Play/Pause, Mute, a volume slider (the mouse wheel over it changes the volume), a speed slider on a log scale (1x in the middle; double-click the value to reset), Keep pitch, Loop, and A/B buttons. Clicking a card selects the video (or the container holding it). The list is a real list model (`bridge/audio_model.py`) that updates rows in place, so sliders aren't recreated while being dragged.

Panels find a video's player (for its position) through a registry on the scene item (`registerView` / `viewFor` in `Main.qml`), keyed by media instance id.

**Audio tracks** (MP3, M4A, and other audio files) are added from a Browser: double-click the preview, or use **Add to Audio** (the Add to Canvas button's label for audio files). A track is an object of type `audio` with a source and the same playback settings as a video, saved and undoable like any other object, but with no place on the canvas: no geometry, no stacking, not in the Layers list (`NON_VISUAL_TYPES` in `core/scene.py`). On the QML side it is a row of `sceneModel` whose delegate (`AudioTrackObject.qml`) draws nothing and only hosts a player. Tracks start **audible and looping** (canvas videos start muted). They are listed first in the Audio tab, with a ✕ to remove them and, if the file is missing, **Locate…**. Adding a track opens the Audio tab and pauses the browser's preview of that file, so it isn't heard twice. Audio previews in a browser are audible by default, with their own mute state separate from video previews.

Not yet: video-as-audio (next). The mouse wheel changes volume only over a card's volume slider; elsewhere it scrolls the list. Solo and audio stream selection were dropped.

---

# 15. Presentation Mode

Presentation mode should transform the application from an editor into the finished media wall.

A keyboard shortcut such as F11 can enter presentation mode.

Presentation mode should:

- hide application chrome
- hide editing controls
- hide browser objects
- hide inspector/layers panels
- hide workspace UI
- display only presentation content

Conceptually:

```text
EDITOR

┌────────────────────────────────────────────┐
│ toolbar                                    │
├────────────────────────────────────────────┤
│                                            │
│ browser        media       container       │
│                                            │
│ panels                                      │
└────────────────────────────────────────────┘


PRESENTATION

┌────────────────────────────────────────────┐
│                                            │
│              MEDIA WALL                   │
│                                            │
│                                            │
└────────────────────────────────────────────┘
```

The user should not need to export a video merely to present the composition.

The project itself becomes the presentation.

### Implemented (2026-09-26)

There are two full-screen modes, both window state only (not saved):

- **Full Screen** (toolbar button or F11): the editor fills the screen, covering the taskbar, with the toolbar hidden. Everything else works as usual.
- **Present** (toolbar button or F5): full screen, and the canvas becomes view-only. Media and containers can't be selected, moved, or right-clicked, and no outlines, handles, or video bars show. Editing shortcuts are off. **Browsers stay visible and working** (browse, zoom, Add to Canvas) but show no selection chrome; hiding them was deliberately not done, so a live browsing wall is possible.

Leaving: Esc (in Full Screen, Esc first deselects), F11 / F5 again, double-clicking the canvas (in Present, anywhere except a browser), or the ✕ in the top-right corner, which appears when the mouse moves and fades after about two seconds. Leaving Present returns to where you were (window or Full Screen).

The toolbar overlays the canvas instead of pushing it down, so objects keep exactly the same screen positions when entering or leaving full screen: what you arrange is what you present.

---

# 16. Project Persistence

Projects should be saveable and reloadable.

The project file stores:

- canvas properties
- scene objects
- media paths
- transformations
- object relationships
- z-order
- browser state
- slideshow configuration
- audio tracks
- presentation settings

It should NOT normally store the media bytes.

---

## 16.1 Missing media

If a referenced source disappears, the project should remain valid.

For example:

```text
The previously used file cannot be found:

/home/alien/Pictures/Japan/IMG_001.jpg
```

The UI should eventually offer:

- Locate
- Replace
- Remove
- Ignore for now

**Implemented:** Locate (right-click → Locate Missing File…). After one file is located, any other missing files from the same old folder are relinked automatically if files with the same names exist in the new folder. Remove is the normal Delete. Ignore is the default: nothing forces a decision.

The original path should remain stored even if the user relocates the file.

---

# 17. Layout Files

Layouts are separate from projects.

A layout describes spatial structure without necessarily containing specific media.

Example:

```text
Four Quadrants
```

could define:

```text
┌──────────┬──────────┐
│          │          │
│    A     │    B     │
│          │          │
├──────────┼──────────┤
│          │          │
│    C     │    D     │
│          │          │
└──────────┴──────────┘
```

The user can:

1. Create layout.
2. Save layout.
3. Start a new project.
4. Import layout.
5. Populate its areas with media.

Layouts therefore remain reusable.

---

# 18. Project Versus Layout

These must remain distinct.

## Project

Contains:

- actual media references
- objects
- transforms
- playback state
- audio
- browser state
- scene configuration

## Layout

Contains:

- spatial arrangement
- containers
- object positions
- sizes
- perhaps clipping shapes
- optional names/roles

A layout should not need to contain the actual media files.

---

# 19. Suggested Project Data Model

A future project could resemble:

```json
{
    "version": 1,

    "name": "Japan Trip",

    "canvas": {
        "width": 1920,
        "height": 1080
    },

    "objects": [
        {
            "id": "object-001",
            "type": "container",

            "transform": {
                "x": 100,
                "y": 200,
                "scale": 1.0,
                "rotation": 0
            },

            "size": {
                "width": 800,
                "height": 500
            },

            "media": {
                "source": "/home/alien/Pictures/Japan/IMG_001.jpg"
            }
        }
    ],

    "audio_tracks": []
}
```

This is illustrative rather than a final schema.

The schema should eventually include stable IDs and explicit relationships between sources and instances.

---

# 20. More Robust Future Data Model

A more scalable model is:

```text
Project
│
├── MediaSources
│     ├── Source A
│     ├── Source B
│     └── Source C
│
├── Objects
│     ├── MediaInstance
│     ├── Container
│     ├── Browser
│     └── Slideshow
│
├── Collections
│
├── AudioTracks
│
└── Canvas
```

For example:

```json
{
    "media_sources": {
        "source-001": {
            "path": "/home/alien/Pictures/photo.jpg",
            "type": "image"
        }
    },

    "objects": [
        {
            "id": "instance-001",
            "type": "media",
            "source_id": "source-001"
        },

        {
            "id": "instance-002",
            "type": "media",
            "source_id": "source-001"
        }
    ]
}
```

This explicitly supports cloning without copying the source.

---

# 21. Transforms

Transforms should be represented in a way that can later support animation.

Basic transform:

```text
x
y
scale
rotation
```

Potential future transform properties:

```text
scale_x
scale_y
rotation
opacity
anchor_x
anchor_y
```

The model should not make future animation difficult.

---

# 22. Future Animation

Although animation is not required for the first prototype, the data model should leave room for it.

For example:

```text
Object
    └── Animation
          ├── position keyframes
          ├── scale keyframes
          ├── rotation keyframes
          └── opacity keyframes
```

This would eventually permit:

- objects moving across the canvas
- zoom effects
- rotation
- fades
- animated layouts
- timed presentations

The initial model should therefore avoid assumptions that every transform is permanently static.

---

# 23. Layer Architecture

Every visual object should have a layer/z-order value.

Basic operations:

```text
bring_to_front()
bring_forward()
send_backward()
send_to_back()
```

Future Layers panel:

```text
Layers

☑ 🔒 Browser
☑ 🔓 Container 2
☑ 🔓 Photo 1
☑ 🔓 Video
☐ 🔓 Container 1
```

Potential future properties:

- visible
- locked
- name
- type
- z-order

### Implemented (2026-09-26)

- Stacking has two groups: ordinary objects below, and browsers (workspace tools, `OVERLAY_TYPES` in `core/scene.py`) always above. Each group is ordered by `z`, and every z-order operation moves an object only within its own group, so "Bring to Front" on an image puts it at the top of the images, still below any browser. `Scene.is_at_front()` / `is_at_back()` answer per group; the right-click menu and the Layers panel use them.
- The **Layers panel** is a flyout on the right edge (the "Layers" tab opens and closes it; it's hidden in Present). It lists every top-level object, top first, with a type badge and a name (`Scene.display_name`: the file name, `Container · <file>` or `Container (empty)`, `Browser · <folder>`). The selected object is highlighted and kept in view; clicking a row selects that object on the canvas. **Top / Up / Down / Bottom** buttons move the selected object. Visibility, locking, and drag-to-reorder are not done yet.

---

# 24. Selection

Objects need a selection state.

A selected object can eventually display:

- bounding box
- resize handles
- rotation handle
- object name
- transform controls

The selection UI should be an editor overlay rather than part of presentation mode.

---

# 25. Workspace UI

The eventual editor can contain:

### Canvas

Central visual area.

### Toolbar

Actions such as:

- Add Media
- Add Browser
- Add Container
- Add Slideshow
- Save
- Load
- Presentation Mode

### Inspector

Properties of the selected object.

Possible properties:

```text
Position
X
Y

Size
Width
Height

Scale

Rotation

Opacity

Display Mode
Contain / Cover / Free / Stretch

Lock Aspect Ratio

Layer
```

### Layers panel

Controls z-order, visibility, and locking.

### Audio rack

Persistent or dockable audio controls.

### Context menus

Right-clicking an object opens a menu of the actions that apply to it (currently z-order, Delete, and Pause/Play for animated images). Items that don't apply to an object are hidden, not just disabled. This is the primary way to reach object actions.

The exact UI arrangement can evolve, subject to one rule:

> **Every action must be reachable through visible UI.** Keyboard shortcuts are accelerators, never the only path to a feature.

---

# 26. Browser UI

A browser might eventually contain:

```text
┌─────────────────────────────────────────────┐
│ Folder: Japan/Tokyo                    ... │
├─────────────────────────────────────────────┤
│                                             │
│              MEDIA PREVIEW                  │
│                                             │
├─────────────────────────────────────────────┤
│  ◀ Previous     37 / 142       Next ▶       │
├─────────────────────────────────────────────┤
│ Add as...                                   │
│ [Free] [Container] [Slideshow]             │
└─────────────────────────────────────────────┘
```

Potential controls:

- folder selector
- collection selector
- filter
- sort
- previous
- next
- add to canvas
- add to selected container
- make container
- make slideshow
- use as audio
- keep browser

### Current layout (2026-09-26)

The browser is kept compact, with the media as large as possible:

```text
┌─────────────────────────────────────────────┐
│ Tokyo  street/IMG_0142.jpg  ☑ Subfolders [Choose Folder] [✕] │  ← header: drag here to move
├─────────────────────────────────────────────┤
│                                             │
│        MEDIA PREVIEW (see-through)          │
│                                             │
│  [Pause] ───●────────── 0:12 / 1:40 [Mute]  │  ← videos/audio only
│  [◀] [▶] [Add to Canvas] [Add to Container]  37 / 142 │  ← overlaid
└─────────────────────────────────────────────┘
```

- The header shows the folder name and the current file's path relative to it. Only the header moves the browser; the ✕ closes (deletes) it, which can be undone.
- The preview background is about 90% transparent, so the canvas shows around the media.
- Browsers always draw above other canvas objects (they are workspace tools). Among themselves they keep their normal stacking order, and z-order operations move them only among browsers (section 23).
- Over the preview: the wheel moves to the previous/next file; holding the left button while scrolling zooms around the pointer, and left-drag then pans. The zoom is temporary and resets when the file changes. Double-clicking adds the current file to the canvas.

---

# 27. Browser as Temporary Workspace Object

A browser can initially be temporary.

For example:

```text
Open Browser
    ↓
Find image
    ↓
Add image to canvas
    ↓
Close browser
```

The browser itself need not become part of the presentation.

But it should also be possible to keep it.

This allows a live interactive workspace where a browser remains visible during editing.

---

# 28. Browser as a Container-like Object

There is a useful conceptual relationship:

```text
Container
    = viewport for presentation media

Browser
    = viewport for browsing media
```

This suggests both can eventually share parts of their implementation.

They are not identical, however.

A Browser has:

- source list
- current index
- navigation
- collection/folder
- preview controls

A Container has:

- clipping
- media instance
- media transform
- presentation behavior

---

# 29. Media Source Abstraction

The media subsystem should use a common abstraction.

Conceptually:

```text
MediaSource
│
├── ImageSource
├── VideoSource
└── AudioSource
```

However, video files can also provide audio.

Therefore an even better conceptual model is:

```text
MediaSource
│
├── image stream
├── video stream
└── audio stream
```

A file can expose one or more streams.

For example:

```text
movie.mkv
    ├── video stream 0
    ├── audio stream 0
    └── subtitle stream 0   [future]
```

The application can then assign individual streams to roles.

---

# 30. Rendering Architecture

The application should use Qt/QML's scene graph for normal visual rendering.

Avoid implementing canvas rendering by repeatedly manipulating image pixels in Python.

The intended pipeline is approximately:

```text
Python
    │
    │ application state
    ▼
QML / Qt Scene Graph
    │
    │ GPU rendering
    ▼
NVIDIA GPU
```

Video/audio decoding is delegated to QtMultimedia.

This is important for maintaining smooth performance.

The window renders with 4x multisample anti-aliasing (`QSurfaceFormat` samples, set in `main.py`), so the edges of rotated media and containers are smooth. Per-item `antialiasing` wasn't enough: it can't smooth the clip of a rotated container. If MSAA ever costs too much on a weaker GPU, lowering the sample count is the one place to change it.

---

# 31. Why Python Is Appropriate

Python is intended to handle:

- application logic
- project management
- file handling
- media indexing
- collections
- configuration
- data models
- interaction with QML
- orchestration of media playback

Heavy work should be delegated to native/GPU-backed libraries.

Therefore the architecture should not require Python to perform every frame-level operation.

---

# 32. Performance Philosophy

The user has an NVIDIA RTX 3070.

The application should make use of GPU rendering wherever practical.

The likely performance-sensitive operations are:

- video decoding
- texture upload
- scene rendering
- scaling
- transformations
- clipping
- compositing

Those should be handled by Qt/QML/QtMultimedia and underlying native libraries rather than Python loops.

If a genuine performance bottleneck appears later, a specific native module can be introduced without rewriting the entire application.

---

# 33. Technology Stack

Initial intended stack:

```text
Python
    │
    ├── PySide6
    │     └── Qt / QML
    │
    ├── QtMultimedia (FFmpeg backend)
    │     └── video/audio playback
    │
    ├── JSON
    │     └── project/layout files
    │
    └── filesystem / application logic
```

Potential future components:

```text
SQLite
    └── media library/index

FFmpeg
    └── metadata/probing/conversion where appropriate

GPU acceleration
    └── Qt scene graph / video pipeline
```

---

# 34. Why Not Build It as a Web Application?

The application is intended to be a native desktop application.

Web technology can still be used internally if useful, but the target experience is:

- local filesystem access
- desktop media playback
- native fullscreen
- GPU rendering
- local project files
- no server dependency

The user should be able to run it locally on Linux Mint/Ubuntu.

---

# 35. Why Not C++ Initially?

C++ with Qt would be a viable long-term implementation.

However, for the initial version Python + PySide6 is preferred.

The expected heavy operations are already delegated to:

- Qt/QML
- QtMultimedia
- GPU rendering
- native media libraries

Therefore Python should not be the limiting factor for the initial application.

If a specific subsystem later proves CPU-bound, that subsystem can be optimized or moved to native code.

---

# 36. Target Platforms

Primary environment:

```text
Linux Mint
```

The application should also run on Ubuntu-derived Linux systems and on Windows, which is also used for development.

Rules that keep the code cross-platform:

- Build filesystem paths with `pathlib`, never by joining strings with `/` or `\`.
- Build file URLs with `Path.as_uri()` (Python) or `QUrl.fromLocalFile()` (Qt), never with `"file://" + path`. String concatenation breaks on Windows drive letters and on filenames containing `#`, `?`, or `%`.
- Match filename capitalization exactly. Windows ignores case; Linux does not, so `main.qml` versus `Main.qml` works on one and fails on the other.
- Avoid platform-specific APIs unless they are isolated behind a small, clearly named module.

Qt Quick Controls use the Fusion style on every platform (set in `main.py`), with a fixed dark palette in `Main.qml`, so buttons and checkboxes look the same on Windows and Linux whatever the OS theme. The native Windows style was dropped because it looked different and, in PySide6 6.11.2, drew the last button of a row with white text on a light face.

---

# 37. Development Environment

Use a dedicated virtual environment on each machine. A venv is not portable: never copy the `venv` folder between machines, and keep it out of version control (`venv/` in `.gitignore`).

Dependencies are listed in `requirements.txt`. PySide6 is pinned to one exact version (currently `PySide6==6.11.2`) so every machine runs the same Qt. It must stay at 6.10 or newer, because pitch-compensation control (section 14.4) was introduced in Qt 6.10. Only `PySide6` needs to be listed; it pulls in `PySide6_Essentials`, `PySide6_Addons`, and `shiboken6` automatically.

### Linux Mint / Ubuntu

```bash
cd ~/mediawall
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

If Qt fails to start with an error about the "xcb" platform plugin:

```bash
sudo apt install libxcb-cursor0
```

### Windows (PowerShell)

```powershell
cd C:\Dev\mediawall
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

If PowerShell refuses to run `Activate.ps1`, use Command Prompt with `venv\Scripts\activate.bat`, or skip activation and run `venv\Scripts\python.exe main.py`.

If pip finds no PySide6 wheel, the installed Python is newer than PySide6 supports. Install a supported version and create the venv with it, e.g. `py -3.12 -m venv venv`.

### Launchers (double-click to start)

After creating the venv, run once on each machine:

```text
Windows:  venv\Scripts\python.exe tools\create_launchers.py [--desktop] [--start-menu]
Linux:    venv/bin/python tools/create_launchers.py [--desktop]
```

- **Windows** gets `MediaWall.lnk` (no terminal window) and `MediaWall (debug).lnk` (terminal stays open after exit) in the project folder, and optionally on the Desktop / in the Start Menu. The shortcuts are machine-specific and not committed. `MediaWall.lnk` runs `launcher.pyw`, which starts `main.py` with a *hidden* console rather than none, because on Windows FFmpeg's output can only be captured when the process has a console.
- **Linux** gets "MediaWall" and "MediaWall (debug)" in the application menu (`~/.local/share/applications`), and optionally on the Desktop. The debug entry runs `tools/run_debug.sh` in a terminal.

### Log window

Everything the app would print to a terminal (FFmpeg, Qt warnings and QML errors, Python output and uncaught exceptions) is captured by `bridge/log_capture.py` and shown in the **Log** window (toolbar button), with Copy All and Clear. It is also written to `logs/mediawall.log` (the previous run is kept as `mediawall.previous.log`), so a start that fails before the window appears still leaves a trace. When the app is started from a terminal, the output appears there too.

The capture works by redirecting file descriptors 1 and 2 into a pipe, since FFmpeg writes to stderr directly.

### QML disk cache

`main.py` turns off Qt's compiled-QML disk cache (`QML_DISABLE_DISK_CACHE=1`). With QML files changing often, a stale cache can make the app fail to start with errors like "Type MediaObject unavailable" or "Cannot assign to non-existent property". The cache saves almost no time for a project this size. It can be re-enabled for a release build.

### Tests

From the project folder:

```bash
python -m unittest
```

The tests cover `core/` only and need no display or Qt, so they run in milliseconds. Run them after any change to `core/`.

Do not depend on any other project's virtual environment (for example ComfyUI's). MediaWall has its own environment and dependency set.

---

# 38. Project Structure

Current structure:

```text
mediawall/
├── main.py                 entry point: creates the app, engine, and models
├── launcher.pyw            starts main.py without a terminal window
├── requirements.txt
├── readme.md
│
├── core/                   plain Python, no Qt imports
│   ├── __init__.py
│   ├── scene.py            MediaSource, SceneObject, Scene
│   ├── project.py          project save/load (JSON)
│   ├── history.py          undo/redo history (scene snapshots)
│   └── media_browser.py    folder scanning, media type detection
│
├── bridge/                 Qt glue between core and QML
│   ├── __init__.py
│   ├── log_capture.py      terminal output -> Log window and logs/
│   ├── audio_model.py      video/audio instances for the Audio tab
│   ├── scene_model.py      exposes Scene to QML as a list model
│   └── project_controller.py  New/Open/Save dialogs, title, unsaved prompts
│
├── qml/
│   ├── Main.qml            window, toolbar, scene, shortcuts
│   ├── MediaObject.qml     free media instance
│   ├── BrowserObject.qml   Browse Object
│   ├── ContainerObject.qml container (viewport with clipped content)
│   ├── AudioTrackObject.qml audio track (a player with no canvas item)
│   ├── MediaView.qml       displays one media source (image, GIF/WebP, video, audio)
│   ├── VideoControls.qml   play/seek/mute bar for video and audio
│   ├── MediaErrorBox.qml   "Missing file" / "Can't display file" box
│   ├── RotationHandle.qml  shared rotation knob
│   ├── ResizeHandles.qml   shared four-corner resize handles
│   ├── ObjectContextMenu.qml  shared right-click menu
│   ├── LogWindow.qml       the Log window
│   ├── Sidebar.qml         right-edge flyout: Layers and Audio tabs
│   └── Zoom.js             shared mouse-wheel zoom step
│
├── tools/
│   ├── create_launchers.py shortcuts / menu entries for this machine
│   └── run_debug.sh        Linux debug launcher (keeps the terminal open)
│
└── tests/
    ├── __init__.py
    ├── test_scene.py
    ├── test_media_browser.py
    ├── test_project.py
    ├── test_containers.py
    ├── test_history.py
    └── test_video.py
```

### Layering rule

```text
qml  →  bridge  →  core
```

- `core/` holds the actual logic and data: what a scene is, what a source is, how z-order works, how folders are scanned. It never imports Qt or anything from `bridge/`.
- `bridge/` wraps `core` objects so QML can display and change them, and translates QML calls into `core` operations.
- `qml/` renders what the bridge exposes. It does not own persistent object state.

This rule is what makes unit testing without Qt, direct serialization for save/load, and model-level undo/redo possible.

### Packages

Every folder of importable Python modules contains an `__init__.py`, normally empty. It marks the folder as a package; `python -m unittest` needs it in `tests/` to discover tests. Folders of QML, images, or data do not need one.

### Planned additions

```text
core/
├── layout.py
├── collections.py
└── audio.py

qml/
└── Slideshow.qml
```

Example `projects/` and `layouts/` folders may be used during development; the application does not force users to store files there.

---

# 39. Development Roadmap

Status key: **Done**, **Partial**, **Not started**.

## Phase 1 — Scene foundation — **Done**

Goal:

A working QML canvas with first-class scene objects.

Implement:

- main window
- canvas
- object creation
- selection
- movement
- resize
- z-order
- Browser Object placeholder
- Container Object placeholder

All of the above exist. Object state lives in a Python scene model (`core/scene.py`) rather than in QML, and z-order is available through the right-click menu.

---

## Phase 2 — Real media — **Done**

Implement:

- image loading
- image object
- filesystem paths
- contain/cover modes
- scaling
- rotation
- cloning
- missing-file handling

Done: image loading, image objects, filesystem paths, aspect-preserving scaling, rotation, EXIF orientation (phone photos appear upright, and objects are sized to the rotated dimensions), animated GIF/WebP playback with per-instance pause/play, one shared `MediaSource` per file, cloning (Duplicate / Ctrl+D makes a new instance of the same source), and missing-file handling (Missing file box, Locate Missing File). Contain/cover display modes for free media were dropped (section 5.1).

---

## Phase 3 — Containers — **Done** (rectangular clipping)

Implement:

- container clipping
- media inside container
- local media coordinate system
- pan
- zoom
- rotation
- container resize
- optional locked scaling

All of the above exist; see section 6.4. Container relationships are saved in projects.

---

## Phase 4 — Save/load — **Done**

Implement:

- project JSON
- stable object IDs
- media source references
- transformations
- z-order
- container relationships
- missing-file detection

Done: JSON project files (`.mediawall`) with a format name and version number; stable IDs; media sources saved once with original, current, and project-relative paths; transforms, z-order, playback state, and browser state; atomic saves; tolerant loading; missing files shown as an error state on the canvas; unsaved-changes prompts on New, Open, and close. Container relationships will be added with Phase 3.

---

## Phase 5 — Layouts — **Not started** (kept on the roadmap; section 51)

Implement:

- save layout
- load layout
- import layout into project
- populate layout with media

---

## Phase 6 — Browse Object — **Partial**

Implement:

- folder selection
- file discovery
- supported media filtering
- current item
- previous/next
- image preview
- video preview
- Add to Canvas
- Add to Selected Container
- Make Container
- Add as Slideshow

Done: folder selection, file discovery with optional subfolders, supported-media filtering, current item, previous/next (buttons and mouse wheel), image, GIF, video, and audio preview, preview zoom, Add to Canvas (or double-click), Add to Container (for the selected empty container), Add to Audio for audio files, and browser state stored in the scene model. Remaining (back burner, with slideshows): Make Container, Add as Slideshow.

---

## Phase 7 — Collections — **Not started** (back burner)

Implement:

- saved collections
- multiple folders
- specific files
- filtering
- sorting
- collection persistence

---

## Phase 8 — Video — **Done**

Integrate QtMultimedia (`MediaPlayer` + `VideoOutput` in QML).

Implement:

- video playback
- seeking
- pause/play
- looping
- video inside free media objects
- video inside containers
- video preview in Browser Object

Done: all of the above, through the shared `MediaView` component, so video works in free objects, containers (including crops), and browser previews. Each video instance has its own playing, muted, volume, and loop state, saved with the project and undoable. Selected videos show an on-object seek bar with the time; the right-click menu has Pause/Play Video (Replay Video once a non-looping video has ended), Mute/Unmute, and Loop. Browser previews of video and audio play muted and looping, with a control bar that also has play/pause/replay and mute buttons, since the preview has no right-click menu. Audio files are listed and previewed in browsers; placing them waits for the Audio Rack.

---

## Phase 9 — Audio Rack — **Partial**

Done: audio tracks (MP3/M4A etc., added from a browser), audio preview, and per-video / per-track volume, mute, loop, speed, pitch behavior, and A-B loop, in the sidebar's Audio tab (section 14.5).

Remaining: video-as-audio (next). Solo and choosing between several audio streams in one file were dropped (section 55).

Implement:

- audio tracks
- MP3/M4A
- video-as-audio
- volume
- mute
- solo
- loop
- speed
- pitch behavior
- audio preview

---

## Phase 10 — Presentation Mode — **Partial**

Done: Full Screen and Present modes, hidden editor UI, view-only canvas, keyboard shortcuts and a mouse-only exit (section 15). Browsers stay visible in Present by choice.

Remaining: hiding the mouse cursor while idle (planned, if easy). Scaling the wall to other screen sizes is not planned: positions are in screen units from the top-left, so a wall made on a 1080p screen opens at the same size on a 4K screen, top-left, with more canvas around it; a wall spanning two monitors is better done as a separate MediaWall window/instance per screen.

---

## Phase 11 — Layers / Inspector — **Partial** (z-order operations and Layers panel)

Done: z-order operations (grouped: browsers above everything), Layers panel with selection sync and Top/Up/Down/Bottom (section 23).

Next: drag-to-reorder in the Layers panel. Later: the Inspector. Back burner: visibility and locking.

Implement:

- Layers panel
- visibility
- locking
- z-order
- Inspector
- transform editing

---

## Phase 12 — Advanced presentation features — **Not started** (back burner)

Potential additions:

- transitions
- animation
- keyframes
- fades
- timed slides
- animated camera/viewport
- arbitrary clipping paths
- SVG shapes
- text objects
- effects
- color adjustments

These are deliberately later features.

---

# 40. Important UX Goals

The application should avoid forcing the user through rigid workflows.

The general philosophy is:

> Browse, experiment, arrange, and decide what becomes permanent.

Examples:

### Good workflow

```text
Open browser
→ browse
→ preview
→ drag/resize browser
→ find image
→ add image
→ continue browsing
```

### Also good

```text
Create container
→ assign folder
→ browse inside it
→ select media
→ adjust zoom/crop
```

Both should feel natural.

---

# 41. No Mandatory Media Import Step

The application should not require a traditional:

```text
Import → Copy into Library → Add to Project
```

workflow.

Instead:

```text
Filesystem
    ↓
Browse
    ↓
Reference source
    ↓
Use source in project
```

This keeps the system lightweight and makes very large personal media collections practical.

---

# 42. File Relocation Strategy

Because projects reference external files, files can disappear or move.

The project should preserve:

```text
original_path
```

Potential future enhancements:

- relative paths
- project-relative paths
- configurable search roots
- automatic relocation detection
- "Locate Missing Media"
- batch relinking

But the original path should not be discarded.

---

# 43. Media Caching

A future thumbnail/cache system can improve performance.

Important distinction:

```text
Original media
    ≠
Generated cache
```

The cache may contain:

- thumbnails
- video preview frames
- metadata
- waveform previews

Deleting a cache must never delete the user's original media.

---

# 44. Future Media Library

SQLite may eventually maintain an indexed library.

Potential indexed data:

```text
path
media type
width
height
duration
creation date
modification date
thumbnail
folder
metadata
```

This is a future optimization and should not be required for the first prototype.

The application should work directly from filesystem paths before introducing a database.

---

# 45. Error Handling

Errors should be visible and understandable.

Examples:

### Missing file

```text
The previously used file cannot be found:

/home/alien/Pictures/Japan/IMG_001.jpg

[Locate] [Remove] [Ignore]
```

### Unsupported media

```text
This file could not be played.

File:
example.xyz

[Remove]
```

### Playback failure

The application should not crash the entire project because one media object failed.

The object should remain in the scene with an error state.

---

# 46. Project Robustness

A corrupt/missing individual media source should not invalidate the entire project.

Projects should be loadable even when:

- files are missing
- thumbnails are missing
- videos fail to decode
- audio streams are unavailable

The application should degrade gracefully.

---

# 47. Undo/Redo

**Implemented.** Toolbar Undo/Redo buttons, Ctrl+Z, and Ctrl+Shift+Z or Ctrl+Y.

- The history stores whole-scene snapshots (`core/history.py`), up to 200 steps. A scene holds only paths and numbers, so snapshots are cheap, and every action is undoable automatically, including ones added later, as long as it goes through the scene model.
- Every change to saved state ends in one place in the bridge (`SceneModel._changed`), which records the step and marks the project modified.
- Rapid repeated changes can share a merge key and become one step. A whole scroll of wheel zoom, on a free image or inside a container, is a single undo.
- Browser state (folder, position, subfolders setting) is workspace state: saved with the project, but not recorded as undo steps and not rewound by undo. Browsing through 50 photos doesn't fill the history.
- Applying an undo announces only the rows that actually appear or disappear, so untouched objects keep their on-screen state: browsers don't rescan and GIFs keep playing.
- Selection is not part of undo.
- History is cleared on New and Open, and is not saved.

---

# 48. Clipboard / Duplication

Eventually:

```text
Ctrl+C
Ctrl+V
Ctrl+D
```

could duplicate scene objects.

Duplication should create a new instance/reference rather than copying media files.

**Implemented:** Duplicate (right-click menu, or Ctrl+D) creates a new instance of the same source, offset slightly and placed on top. Duplicating a container duplicates its content too. Copy/paste is not implemented yet.

---

# 49. Keyboard Interaction

Shortcuts are accelerators. Every shortcut action must also be reachable through visible UI (section 25).

Implemented:

```text
Ctrl+Z            undo
Ctrl+Shift+Z      redo (Ctrl+Y also works)
Ctrl+D            duplicate selected object
Ctrl+N            new project
Ctrl+O            open project
Ctrl+S            save
Ctrl+Shift+S      save as
Delete            remove selected object
Escape            leave Present; otherwise deselect (also leaves a
                  container's Adjust mode); with nothing selected,
                  leave Full Screen
F11               Full Screen on/off
F5                Present on/off
Enter / Space     finish adjusting (in a container's Adjust mode)
Ctrl+Shift+Up     bring to front
Ctrl+Up           bring forward
Ctrl+Down         send backward
Ctrl+Shift+Down   send to back
Mouse wheel       previous/next item (over a browser preview);
Left button+wheel zoom a browser preview (then left-drag pans);
                  scale a selected free image or container around the pointer;
                  zoom content (over a container in Adjust mode)
Double-click      enter Adjust mode (on a container with content);
                  add the current file to the canvas (on a browser preview);
                  reset rotation to 0° (on the orange rotation knob)
```

Planned:

```text
Arrow keys   move selected object
Shift+Arrow  move faster
```

Exact bindings can still change.

---

# 50. Current State

The prototype currently provides:

- a canvas with a toolbar (New, Open, Save, Save As, Undo, Redo, Add Browser, Add Container, Full Screen, Present, Log)
- Full Screen (editing) and Present (view-only canvas, browsers still usable) modes (section 15)
- a right-click menu on empty canvas (Add Browser Here, Add Container Here)
- project save/load to `.mediawall` files, with unsaved-changes prompts and the project name in the window title
- missing media shown as a "Missing file" box that keeps its size and position; undecodable files shown as "Can't display file"
- Locate Missing File (right-click), which also relinks other missing files from the same old folder if they're found in the new one
- undo/redo for every scene change (section 47)
- Duplicate (section 48)
- a Python scene model that owns all object state; QML renders it
- one `MediaSource` per file, referenced by media objects through `source_id`
- random object IDs, so importing a layout can never cause ID collisions
- Browse Objects: choose folder, optional subfolders, previous/next, preview with temporary zoom/pan, Add to Canvas (or double-click), close button; always drawn above other objects, with a see-through preview (section 26)
- free media objects: move, aspect-locked resize, rotate
- EXIF orientation applied to photos, on the canvas and in browser previews
- animated GIF and WebP playback, on the canvas and in browser previews; each instance can be paused or played from its right-click menu
- video on the canvas, in containers, and in browser previews, with per-instance play/pause, mute, and loop (right-click menu), and an on-object seek bar when selected
- per-video speed (0.25x to 4x), Keep pitch, and A-B loop; an Audio tab in the sidebar with every video's sound and playback settings (section 14.5)
- audio tracks added from a browser (double-click or Add to Audio), controlled in the Audio tab
- audio previews in browsers
- containers: move, resize, rotate; hold one clipped media instance with its own pan, zoom, and rotation (Adjust mode); fit/fill; locked or independent scaling; release/remove content
- media can be dragged into empty containers, or added from a browser to a selected empty container
- containers: scroll-wheel scaling around the pointer (when selected), content included
- free images: scroll-wheel scaling around the pointer (when selected), and Crop / Zoom Inside, which wraps the image in a matching container
- single selection; clicking empty canvas deselects
- z-order and Delete through a right-click menu, plus shortcuts
- a Layers panel (right-edge flyout): every object top first, selection linked both ways, Top/Up/Down/Bottom
- unit tests for `core/`

### How interactions reach the model

During a drag, resize, or rotate, QML moves the item directly so interaction stays smooth. On mouse release, the item sends its final geometry to the model in one call (`commitGeometry`) and re-binds its properties to the model, so later changes from Python (load, undo) flow back to the canvas. That single commit per interaction is the natural hook for undo/redo.

### Known limitations

- **Folder scanning runs on the UI thread.** Normal folders scan effectively instantly, but a very large tree or a slow network drive will freeze the app until the scan finishes. Background scanning can be added if this becomes a real problem.
- **Containers are rectangular only**, and hold one item.
- **Undo history isn't saved** with the project; it starts fresh each time a project is opened.
- **Rotation has no angle snapping** yet (e.g. to 15° steps).
- **No edge handles yet**, only corners; resizing one side on its own isn't possible.
- **Resize has no modifier options** yet (e.g. resize from center, or free aspect on images).
- **Browser folders are saved as absolute paths only**, so a browser's folder is not found automatically if the project is opened on a machine with a different folder layout.
- **Adjust mode shows no ghost for video**, only the orange bounds outline (a second copy of the video would play out of sync).
- **Each video instance runs its own decoder.** Two instances of the same file play independently, not in sync. Many simultaneous videos will be limited by decoding performance.
- **Hardware video decoding hasn't been verified** on the target machines. Qt prints "No HW decoder found" when it falls back to software decoding.

---

# 51. Development Backlog

Reviewed 2026-09-26. Keep this list current; it replaces the phase notes as the answer to "what next?".

### Next

1. **Video as audio** (section 14.2): use a video's sound as an audio track without showing its picture.
2. **Drag-to-reorder in the Layers panel.**
3. **Edge resize handles:** thin bars along each side (unlike the square corner handles), resizing one side at a time.
4. **Adjust-mode ghost for video:** show the part of a video outside the container's frame, as images already do.
5. **Browser folders found on another machine:** save a browser's folder relative to the project file too, as media sources already are.
6. **Hide the mouse cursor while idle in Present**, if it's easy.

### Soon

- Arrow keys to nudge the selected object (Shift for bigger steps).
- Keep undo history between sessions (open decision, section 55).

### Later (kept on the roadmap)

- **Layouts** (Phase 5): reusable canvas arrangements.
- **Inspector** (Phase 11): exact position, size, and rotation.

### Back burner

- Collections (Phase 7).
- Slideshows (section 13), with the browser's Make Container / Add as Slideshow; containers holding more than one item.
- Advanced presentation features (Phase 12), including non-rectangular containers.
- Layers: visibility and locking.
- Rotation snapping (e.g. 15° steps).
- Resize modifiers (e.g. Alt to resize around the center).
- Background folder scanning (scanning is fast enough so far; revisit if large folders or network drives freeze the app).
- Duplicate videos playing in sync / sharing one decoder (each instance decodes separately today).
- Checking hardware video decoding on the target machines (the Log window shows Qt's "No HW decoder found" when it falls back to software).

### Dropped

- Contain/Cover/Free/Stretch display modes for free media (section 5.1).
- Audio solo, and choosing between several audio streams in one file.
- Scaling the wall to other screen sizes (Phase 10).

---

# 52. Architectural Rule to Preserve

The most important rule for future development is:

```text
SOURCE
    ↓
MEDIA INSTANCE
    ↓
VIEWPORT / OBJECT
```

Do not collapse these concepts into one object.

For example, do not make a Container directly own a filename as its only media state.

Instead:

```text
MediaSource
    ↓
MediaInstance
    ↓
Container
```

This is what allows:

- cloning
- multiple appearances of one source
- different crops
- different zoom
- different rotation
- browsers
- collections
- slideshows
- audio tracks
- video-as-audio

without duplicating files or creating conflicting state.

---

# 53. Overall Architecture

The intended long-term architecture can be summarized as:

```text
                         MEDIAWALL
                             │
                    ┌────────┴────────┐
                    │                 │
                 Project           Workspace
                    │                 │
          ┌─────────┼─────────┐       ├── Browser
          │         │         │       ├── Inspector
       Sources    Objects   Audio     ├── Layers
          │         │       Tracks    └── Library
          │         │
          │      ┌──┴────────────────────┐
          │      │                       │
          │   Media                  Container
          │   Instance                   │
          │                              │
          └────────── source ─────────────┘
```

In code, this maps onto three layers (section 38):

```text
qml/     renders the scene, handles live interaction
  │
bridge/  exposes core to QML (SceneModel)
  │
core/    Scene, MediaSource, SceneObject, folder scanning; no Qt
```

With the rendering pipeline:

```text
Python data/model
        │
        ▼
     PySide6
        │
        ▼
       QML
        │
        ▼
   Qt Scene Graph
        │
        ▼
       GPU
```

And media playback:

```text
Media Source
      │
      ▼
 QtMultimedia
      │
 ┌────┴────┐
 ▼         ▼
Video     Audio
 │         │
 ▼         ▼
QML       Audio Rack
```

---

# 54. Design Philosophy in One Sentence

**MediaWall should let the user treat their filesystem as a huge media collection, browse and experiment with that collection directly on a visual canvas, arrange media into independent viewports and compositions, and then turn that workspace into a fullscreen multimedia presentation without copying or unnecessarily converting the original media.**

---

# 55. Status / Decision Log

The following design decisions are currently established:

- Python is the primary implementation language.
- PySide6/QML is the initial UI technology.
- The application is native/local rather than web-first.
- The canvas is the central workspace.
- Browser, Container, and Media are conceptual first-class scene objects.
- Browsers can exist independently of containers.
- Containers act as viewports.
- Media inside containers has an independent local coordinate system.
- Media files are referenced by path rather than copied.
- Cloning creates media instances, not duplicate files.
- Collections reference existing media rather than copying it.
- Projects and layouts are separate concepts.
- Video and audio playback use QtMultimedia with its FFmpeg backend, not GStreamer. QtMultimedia integrates directly with QML, ships with the PySide6 wheels on Linux and Windows, and supports audio-track selection (video-as-audio), playback rate, looping, and switchable pitch compensation (Qt 6.10+). Pitch compensation was confirmed as toggleable on the FFmpeg backend with PySide6 6.11.2; audio quality of shifted playback still needs a listening test at Phase 8. GStreamer remains a fallback only if a real limitation appears.
- Video files can provide audio without extraction.
- Audio has a dedicated rack/panel rather than requiring a visible canvas object.
- Presentation mode hides workspace/editor UI.
- Layers/z-order are fundamental.
- Missing media should produce a recoverable error state rather than breaking the project.
- Animation is a future capability and the data model should leave room for it.
- SQLite is a future optimization/library index, not a first requirement.
- C++ is not required for the initial implementation.
- GPU/QML/QtMultimedia should handle performance-sensitive work.
- Development should proceed incrementally, testing a working application at every major stage.
- The application is cross-platform: Linux primary, Windows also supported for development.
- Code is layered `qml → bridge → core`; `core/` never imports Qt.
- The Python scene model is the source of truth for object state. QML renders it and commits changes back on interaction release.
- Each file is registered once as a `MediaSource`; media objects reference it by `source_id`.
- Object IDs are random rather than sequential, so layouts can be imported without ID collisions.
- Every action must be reachable through visible UI. Keyboard shortcuts are accelerators only.
- Object actions live in a right-click context menu.
- Selecting an object does not change its z-order.
- Browsers can include subfolders; this is a per-browser setting stored in the scene model.
- Browser file lists are rescanned from disk rather than stored.
- Project files use the `.mediawall` extension and contain JSON with `"format": "mediawall-project"` and an integer `"version"`. Files from a newer format version are refused rather than half-loaded.
- Only media sources still used by an object are saved.
- Each source stores its current path, its original path (never discarded), and, when possible, a path relative to the project file. Loading tries the saved path first, then the relative path.
- Saving is atomic (write to a temporary file, then replace).
- Loading is tolerant: unknown object types, bad values, and missing files produce warnings and recoverable states, not a failed load.
- Undo/redo uses whole-scene snapshots; browser state is excluded from undo.
- Selection is not saved and does not mark the project as modified. A click that doesn't move anything also doesn't.
- A container's content is a media instance with `parent_id` set to the container; its geometry is in container-local coordinates. Containers never store filenames.
- A container holds at most one media instance, and a full container doesn't accept new media; its content must be released or removed first (2026-09-26). (`Scene.add_media_to_container` can still replace, releasing the old instance as a free object, but the UI never asks it to.)
- New container content is framed to fill (cover).
- "Scale Content with Container" (locked scaling) is on by default.
- Only top-level objects take part in z-order.
- Browsers form their own stacking group above everything else; z-order operations never move an object across groups (2026-09-26).
- Rotation handles rotate relative to where they are grabbed, so objects never jump when the knob is clicked.
- Double-clicking the rotation knob resets rotation to 0° (the content's rotation, in Adjust mode). The same resets are in the right-click menu (Reset Rotation / Reset Content Rotation), shown only when something is rotated.
- Every object has four corner resize handles (shared `ResizeHandles` component). Dragging a corner pins the opposite corner, including on rotated objects. Images keep their aspect ratio; containers and browsers resize freely.
- Cropping a free image is done by wrapping it in a container (Crop / Zoom Inside), not by giving free media its own crop state. Such containers start with locked scaling off.
- Videos placed on the canvas start **muted, playing, and looping**. Sound is meant to live mainly in the Audio Rack, and a wall of unmuted videos is chaotic. Each video can be unmuted individually.
- A video's size isn't known until the player loads it, so it is placed at a 16:9 placeholder and resized once the player reports its real size. This correction is not an undo step of its own.
- All media display goes through one QML component (`MediaView`), so video support added there applies to free media, container content, and previews at once.
- EXIF orientation is always applied; object sizes use the displayed (rotated) dimensions.
- GIF and WebP are treated as potentially animated and displayed with an animated image element. Playback state is per instance, stored in the scene model.
- Qt Quick Controls use the Fusion style everywhere, with a fixed dark palette, so the app looks the same on every platform and OS theme (2026-09-26).
- The toolbar overlays the canvas rather than pushing it down, so object screen positions are identical in the window, Full Screen, and Present (2026-09-26). Projects made earlier appear 50 px higher once.
- Present mode keeps Browsers visible and usable; the rest of the canvas is view-only (2026-09-26).
- Audio tracks are objects of type `audio` with no canvas presence; they start audible and looping (2026-09-26).
- Speed changes pitch by default (Keep pitch off), as in Celluloid (2026-09-26).
- The application's name is written **MediaWall** (one word) everywhere (2026-09-26).
- Free media always keeps its aspect ratio; no Contain/Cover/Free/Stretch modes for it (2026-09-26).
- No audio solo, and no choosing between audio streams in one file (2026-09-26).
- The wall is not scaled to the screen: a larger screen shows more canvas, with the wall at the same size in the top-left; multi-monitor walls use one MediaWall instance per screen (2026-09-26).
- The window uses 4x MSAA so rotated edges are smooth (2026-09-26).

### Open decisions

- **Undo history between sessions:** where to keep it. The suggestion is a separate file next to the project (e.g. `japan.mediawall.history`), capped at about 50 steps, rather than inside the `.mediawall` file: each step is a whole-scene snapshot, a lost or damaged history file can't affect the project, and the project file stays small and readable.

---

# 56. Guiding Development Rule

Do not implement future complexity merely for the sake of complexity.

Instead:

1. Preserve the important architectural boundaries.
2. Build the smallest working version of the current feature.
3. Test it.
4. Add the next capability without breaking those boundaries.

The application should grow from a simple working canvas into the full media wall rather than attempting to build the entire system before anything runs.