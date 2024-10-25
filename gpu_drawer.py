import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from .mesh_topology_analyzer import MeshTopologyAnalyzer


class GPUDrawer:  # Renamed from GPUDrawer
    def __init__(self):
        self.handle = None
        self.batch = None
        self.shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        self.is_running = False
        self.mesh_analyzer = None
        self._timer = None
        self.show_tris = True
        self.show_quads = True
        self.show_ngons = True

    def set_mesh_analyzer(self, analyzer):
        self.mesh_analyzer = analyzer

    def update_visibility():
        if hasattr(bpy.context.scene, "gpu_topology_overlay"):
            drawer.show_tris = bpy.context.scene.gpu_topology_overlay.show_tris
            drawer.show_quads = bpy.context.scene.gpu_topology_overlay.show_quads
            drawer.show_ngons = bpy.context.scene.gpu_topology_overlay.show_ngons

    def draw(self):
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        self.shader.bind()

        props = bpy.context.scene.GPU_Topology_Overlay_Properties

        obj = bpy.context.active_object
        if obj and self.mesh_analyzer:
            bpy.context.view_layer.update()
            if obj.mode == "EDIT":
                obj.update_from_editmode()

            # Get current colors from scene properties
            colors = {
                "tris": tuple(props.tris_color),  # Convert to tuple
                "quads": tuple(props.quads_color),
                "ngons": tuple(props.ngons_color),
            }

            self.mesh_analyzer.analyze_mesh(obj)
            mesh_data = self.mesh_analyzer.get_visible_data(
                self.show_tris,
                self.show_quads,
                self.show_ngons,
                colors=colors,  # Pass the current colors
            )

            if mesh_data["vertices"]:
                self.create_batch(mesh_data)
                self.batch.draw(self.shader)

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")

    def create_batch(self, mesh_data):
        self.batch = batch_for_shader(
            self.shader,
            "TRIS",
            {"pos": mesh_data["vertices"], "color": mesh_data["colors"]},
        )

    def start(self):
        if not self.is_running:
            self.handle = bpy.types.SpaceView3D.draw_handler_add(
                self.draw, (), "WINDOW", "POST_VIEW"
            )
            # Add timer for continuous updates
            self._timer = bpy.app.timers.register(self.timer_update, persistent=True)
            self.is_running = True

    def stop(self):
        if self.is_running:
            if self.handle:
                bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
            if self._timer:
                bpy.app.timers.unregister(self._timer)
            self.handle = None
            self._timer = None
            self.is_running = False

    def timer_update(self):
        if self.is_running:
            # Force viewport update
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
            return 1 / 60  # Update every 1/60 second
        return None


# Update the drawer instance
drawer = GPUDrawer()
drawer.set_mesh_analyzer(MeshTopologyAnalyzer())


drawer = GPUDrawer()
drawer.set_mesh_analyzer(MeshTopologyAnalyzer())


class GPU_Overlay_Topology(bpy.types.Operator):
    bl_idname = "view3d.gpu_overlay_topology"
    bl_label = "Toggle GPU Overlay Topology"
    bl_description = "Toggle the display of the GPU Overlay Topology in the 3D viewport"

    def execute(self, context):
        if drawer.is_running:
            drawer.stop()
        else:
            drawer.start()
        context.area.tag_redraw()
        return {"FINISHED"}  # Changed from RUNNING_MODAL to FINISHED


classes = (GPU_Overlay_Topology,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    if drawer:
        drawer.stop()

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass
