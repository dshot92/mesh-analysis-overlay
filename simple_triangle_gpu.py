import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector


class MeshTopologyAnalyzer:
    @staticmethod
    def analyze_mesh(obj, show_tris=True, show_quads=True, show_ngons=True):
        if not obj or obj.type != "MESH":
            return None

        mesh_data = {
            "vertices": [],
            "colors": [],
        }

        for face in obj.data.polygons:
            vert_count = len(face.vertices)
            # Skip faces based on visibility settings
            if (
                (vert_count == 3 and not show_tris)
                or (vert_count == 4 and not show_quads)
                or (vert_count > 4 and not show_ngons)
            ):
                continue

            offset = face.normal * 0.001
            face_verts = [
                (obj.matrix_world @ Vector(obj.data.vertices[v].co)) + offset
                for v in face.vertices
            ]

            face_color = (
                (1, 0, 0, 0.5)
                if vert_count == 3
                else (0, 0, 1, 0.5) if vert_count == 4 else (0, 1, 0, 0.5)
            )

            for i in range(1, len(face_verts) - 1):
                mesh_data["vertices"].extend(
                    [face_verts[0], face_verts[i], face_verts[i + 1]]
                )
                mesh_data["colors"].extend([face_color, face_color, face_color])

        return mesh_data


class GPUDrawer:
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

    def draw(self):
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")

        self.shader.bind()

        obj = bpy.context.active_object
        if obj and self.mesh_analyzer:
            bpy.context.view_layer.update()  # Force update
            if obj.mode == "EDIT":
                obj.update_from_editmode()
            mesh_data = self.mesh_analyzer.analyze_mesh(
                obj, self.show_tris, self.show_quads, self.show_ngons
            )
            if mesh_data:
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


drawer = GPUDrawer()
drawer.set_mesh_analyzer(MeshTopologyAnalyzer())


class SimpleTriangleOperator(bpy.types.Operator):
    bl_idname = "view3d.simple_triangle"
    bl_label = "Toggle Simple Triangle"
    bl_description = "Toggle the display of a simple triangle in the 3D viewport"

    def execute(self, context):
        if drawer.is_running:
            drawer.stop()
        else:
            drawer.start()
        context.area.tag_redraw()
        return {"FINISHED"}  # Changed from RUNNING_MODAL to FINISHED


class SimpleTrianglePanel(bpy.types.Panel):
    bl_label = "Simple Triangle GPU"
    bl_idname = "VIEW3D_PT_simple_triangle"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Simple Triangle"

    def draw(self, context):
        layout = self.layout

        # Toggle button for overlay
        row = layout.row()
        if drawer.is_running:
            row.operator(
                SimpleTriangleOperator.bl_idname, text="Hide Overlay", icon="HIDE_ON"
            )
        else:
            row.operator(
                SimpleTriangleOperator.bl_idname, text="Show Overlay", icon="HIDE_OFF"
            )

        # Polygon type toggles
        box = layout.box()
        box.label(text="Show Polygons:")
        row = box.row()
        row.prop(context.scene, "show_tris", text="Triangles", toggle=True)
        row = box.row()
        row.prop(context.scene, "show_quads", text="Quads", toggle=True)
        row = box.row()
        row.prop(context.scene, "show_ngons", text="N-Gons", toggle=True)


classes = (SimpleTriangleOperator, SimpleTrianglePanel)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Register properties
    bpy.types.Scene.show_tris = bpy.props.BoolProperty(
        default=True, update=lambda self, context: update_visibility()
    )
    bpy.types.Scene.show_quads = bpy.props.BoolProperty(
        default=True, update=lambda self, context: update_visibility()
    )
    bpy.types.Scene.show_ngons = bpy.props.BoolProperty(
        default=True, update=lambda self, context: update_visibility()
    )


def unregister():
    if drawer:
        drawer.stop()

    # Unregister properties
    del bpy.types.Scene.show_tris
    del bpy.types.Scene.show_quads
    del bpy.types.Scene.show_ngons

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass


def update_visibility():
    drawer.show_tris = bpy.context.scene.show_tris
    drawer.show_quads = bpy.context.scene.show_quads
    drawer.show_ngons = bpy.context.scene.show_ngons
