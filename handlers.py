import bpy
from bpy.app.handlers import persistent
from .mesh_analyzer import MeshAnalyzer
from .gpu_drawer import drawer


# Used as a callback for depsgraph updates
@persistent
def mesh_analysis_depsgraph_update(scene, depsgraph):
    print("\n=== Depsgraph Update Handler ===")
    for update in depsgraph.updates:
        if isinstance(update.id, bpy.types.Object):
            obj = update.id
            print(f"Object updated: {obj.name} ({obj.type})")
            print(f"Geometry updated: {update.is_updated_geometry}")

            if obj.type == "MESH" and update.is_updated_geometry:
                print(f"Invalidating cache for: {obj.name}")
                MeshAnalyzer.invalidate_cache(obj.name)
                if drawer and drawer.is_running:
                    print("Updating drawer batches")
                    drawer.update_batches(obj)


# Used as a callback for property updates in properties.py
def property_update(self, context):
    print("\n=== Property Update Handler ===")
    if context and context.active_object:
        print(f"Active object: {context.active_object.name}")

    if drawer and drawer.is_running:
        obj = context.active_object
        if obj and obj.type == "MESH":
            # pass
            drawer.batches.clear()
            print("Updating drawer batches")
            drawer.update_batches(obj)


# Used as a callback for offset property updates in properties.py
def offset_update(self, context):
    """Callback for when offset property changes"""
    if context and context.area:
        context.area.tag_redraw()
    if drawer and drawer.is_running:
        obj = context.active_object
        if obj and obj.type == "MESH":
            drawer.update_batches(obj)


def register():
    print("\n=== Registering Handlers ===")
    bpy.app.handlers.depsgraph_update_post.append(mesh_analysis_depsgraph_update)


def unregister():
    print("\n=== Unregistering Handlers ===")
    if mesh_analysis_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(mesh_analysis_depsgraph_update)
