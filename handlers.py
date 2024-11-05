from venv import logger
from .mesh_analyzer import MeshAnalyzer
from .operators import drawer


# Used as a callback for property updates in properties.py
def update_overlay_enabled_toggles(self, context):
    if not drawer or not drawer.is_running:
        return

    obj = context.active_object
    if obj and obj.type == "MESH":
        # Get the name of the changed property
        for prop_name in dir(self):
            if prop_name.endswith("_enabled"):
                feature = prop_name[:-8]  # Remove "_enabled" suffix
                MeshAnalyzer.update_analysis(obj, [feature])

    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


def update_non_planar_threshold(self, context):
    pass


def register():
    pass


def unregister():
    pass
