"""
A browsing container whose files come from a tag search (readme section
44.5): made from the Library's Find mode, stepping through what it finds,
looking again as files are tagged, saying so when a tag has gone, saved
with the project, and opened again without the Library window.
"""

import os
import shutil

from harness import GIF, MOV, OUT, PHOTO, Check, SCREENSHOT, media
from core.project import load_project, save_project
from core.scene import Scene

c = Check("library_search")

FOLDER = OUT / "media"
FOLDER.mkdir(parents=True, exist_ok=True)
for name, source in [("a_car.jpg", PHOTO), ("b_car.png", SCREENSHOT), ("c_ferrari.gif", GIF),
                     ("d_other.mov", MOV), ("e_later.jpg", PHOTO)]:
    try:
        os.link(media(source), FOLDER / name)
    except OSError:
        shutil.copy(media(source), FOLDER / name)


def window():
    return c.js("libraryLoader.item")


def tag(names, tag_name):
    rows = [c.js("tagLibrary.fileAt(%d).name" % i) for i in range(c.js("tagLibrary.files.rowCount()"))]
    first = True
    for i, name in enumerate(rows):
        if name in names:
            c.js("tagLibrary.clickFile(%d, %s, false)" % (i, "false" if first else "true"))
            first = False
    c.js("tagLibrary.createAndApply(%r)" % tag_name)


def tag_id(name):
    c.js("tagLibrary.setQuery(%r)" % name)
    found = c.js("tagLibrary.results[0].id")
    c.js("tagLibrary.setQuery('')")
    return found


def containers():
    return [o for o in c.scene.objects if o.type == "container"]


def box(expression):
    """About the first browsing container: `box` is its item on the wall."""
    return c.js("(function() { var box = objectItem(%r); return (%s) })()" % (containers()[0].id, expression))


def shown():
    content = c.scene.content_of(containers()[0].id)
    return os.path.basename(c.scene.sources[content.source_id].path) if content else None


def browsed():
    return sorted(box("box.browseFiles.map(function(e) { return e.name })"))


def step_open():
    c.js("showLibrary()")
    window().requestActivate()
    c.js("tagLibrary.setFolder(%r)" % str(FOLDER))


def step_tag():
    tag(["a_car.jpg", "b_car.png"], "car")
    tag(["c_ferrari.gif"], "ferrari")
    tag(["b_car.png"], "red")
    tag(["d_other.mov"], "other")
    c.js("tagLibrary.moveTag(%d, %d)" % (tag_id("ferrari"), tag_id("car")))
    c.js("tagLibrary.findMode = true")
    c.js("tagLibrary.toggleTag(%d)" % tag_id("car"))


def step_search():
    c.check("the search finds the parent's files too", c.js("tagLibrary.fileCount") == 3, str(c.js("tagLibrary.fileCount")))
    c.check("nothing on the wall yet", containers() == [])
    c.check("the wall is saved as unchanged so far", c.js("sceneModel.canUndo") is False)
    c.js("libraryLoader.item.addSearchContainer()")


def step_made():
    c.check("a new browsing container is on the wall", len(containers()) == 1)
    o = containers()[0]
    c.check("...which stores the search, not a folder",
            o.browse_query == {"include": ["car"], "exclude": []} and o.browse_mode and o.browse_folder == "",
            str(o.browse_query))
    c.check("it finds the same files", browsed() == ["a_car.jpg", "b_car.png", "c_ferrari.gif"], str(browsed()))
    c.check("it starts on the first", shown() == "a_car.jpg", str(shown()))
    c.check("it knows what it looks for", box("box.searchText") == "car")
    c.js("sceneModel.select(%r)" % o.id)
    c.js("objectItem(%r).browseStep(1)" % o.id)


def step_stepped():
    c.check("stepping goes through the search's files", shown() == "b_car.png", str(shown()))
    c.js("objectItem(%r).browseStep(1)" % containers()[0].id)


def step_stepped_again():
    c.check("...a GIF among them", shown() == "c_ferrari.gif", str(shown()))
    c.js("objectItem(%r).browseStep(1)" % containers()[0].id)


def step_round():
    c.check("...and round again", shown() == "a_car.jpg", str(shown()))
    c.js("sceneModel.setFavorite(%r, %r, true)" % (containers()[0].id, str(FOLDER / "b_car.png")))
    c.js("sceneModel.setMediaFilter(%r, 'favorites')" % containers()[0].id)


def step_favorites():
    c.check("Show Favorites Only works on a search", browsed() == ["b_car.png"], str(browsed()))
    c.js("sceneModel.setMediaFilter(%r, 'all')" % containers()[0].id)
    # Tag another file while it's on the wall.
    c.js("tagLibrary.findMode = false")


def step_tag_mode():
    tag(["e_later.jpg"], "car")


def step_picked_up():
    c.check("a file tagged later is picked up once tagging pauses", "e_later.jpg" in browsed(), str(browsed()))
    c.js("tagLibrary.undo()")


def step_untagged_again():
    c.check("...and undoing it takes it out", "e_later.jpg" not in browsed(), str(browsed()))
    project = OUT / "with-search.mediawall"
    save_project(c.scene, project)
    loaded, warnings = load_project(project)
    c.check("it saves and loads with the project", [o.browse_query for o in loaded.objects if o.type == "container"]
            == [{"include": ["car"], "exclude": []}] and warnings == [], str(warnings))
    c.js("tagLibrary.renameTag(%d, 'autos')" % tag_id("car"))


def step_renamed():
    c.check("a tag renamed in the Library matches nothing", browsed() == [], str(browsed()))
    c.js("sceneModel.select(%r)" % containers()[0].id)
    c.win.requestActivate()


def step_says_so():
    note = c.item_js("browsingNote", "item.children[0].text")
    c.check("...and the container says so", note == "No files match: car", str(note))
    c.check("what it was showing stays", shown() is not None)
    c.grab("search-container.png")
    c.js("tagLibrary.renameTag(%d, 'car')" % tag_id("autos"))


def step_renamed_back():
    c.check("named back, it finds them again", len(browsed()) == 3, str(browsed()))
    c.js("sceneModel.undo()")                # the favorite marked earlier
    c.js("sceneModel.undo()")


def step_undone():
    c.check("adding it was one undo step", containers() == [] and c.js("sceneModel.canUndo") is False, str(containers()))
    c.js("sceneModel.redo()")


def step_redone():
    c.check("...and redoes, with its search", len(containers()) == 1 and containers()[0].browse_query is not None)
    c.check("...and looks again", len(browsed()) == 3, str(browsed()))
    c.finish()


c.run(Scene(), [
    (800, step_open), (1200, step_tag), (800, step_search), (500, step_made), (400, step_stepped),
    (400, step_stepped_again), (400, step_round), (500, step_favorites), (500, step_tag_mode),
    (800, step_picked_up), (800, step_untagged_again), (800, step_renamed), (300, step_says_so),
    (800, step_renamed_back), (400, step_undone), (500, step_redone),
])
