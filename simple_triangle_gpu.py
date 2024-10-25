import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector


class MeshTopologyAnalyzer:
    def __init__(self):
        self.tris = []
        self.quads = []
        self.ngons = []

    def analyze_mesh(self, obj):
        if not obj or obj.type != "MESH":
            return

        # Get offset from scene property
        offset_value = bpy.context.scene.poly_offset

        # Clear previous data
        self.tris = []
        self.quads = []
        self.ngons = []

        # Process each type only if visible
        if bpy.context.scene.show_tris:
            for face in obj.data.polygons:
                if len(face.vertices) == 3:
                    offset = face.normal * offset_value
                    face_verts = [
                        (obj.matrix_world @ Vector(obj.data.vertices[v].co)) + offset
                        for v in face.vertices
                    ]
                    for i in range(1, len(face_verts) - 1):
                        self.tris.extend(
                            [face_verts[0], face_verts[i], face_verts[i + 1]]
                        )

        if bpy.context.scene.show_quads:
            for face in obj.data.polygons:
                if len(face.vertices) == 4:
                    offset = face.normal * offset_value
                    face_verts = [
                        (obj.matrix_world @ Vector(obj.data.vertices[v].co)) + offset
                        for v in face.vertices
                    ]
                    for i in range(1, len(face_verts) - 1):
                        self.quads.extend(
                            [face_verts[0], face_verts[i], face_verts[i + 1]]
                        )

        if bpy.context.scene.show_ngons:
            for face in obj.data.polygons:
                if len(face.vertices) > 4:
                    offset = face.normal * offset_value
                    face_verts = [
                        (obj.matrix_world @ Vector(obj.data.vertices[v].co)) + offset
                        for v in face.vertices
                    ]
                    for i in range(1, len(face_verts) - 1):
                        self.ngons.extend(
                            [face_verts[0], face_verts[i], face_verts[i + 1]]
                        )

    def get_visible_data(
        self, show_tris=True, show_quads=True, show_ngons=True, colors=None
    ):
        vertices = []
        vert_colors = []

        if colors is None:
            colors = {
                "tris": (1, 0, 0, 0.5),
                "quads": (0, 0, 1, 0.5),
                "ngons": (0, 1, 0, 0.5),
            }

        if show_tris:
            vertices.extend(self.tris)
            vert_colors.extend([colors["tris"]] * len(self.tris))
        if show_quads:
            vertices.extend(self.quads)
            vert_colors.extend([colors["quads"]] * len(self.quads))
        if show_ngons:
            vertices.extend(self.ngons)
            vert_colors.extend([colors["ngons"]] * len(self.ngons))

        return {"vertices": vertices, "colors": vert_colors}


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
            bpy.context.view_layer.update()
            if obj.mode == "EDIT":
                obj.update_from_editmode()

            # Get current colors from scene properties
            colors = {
                "tris": tuple(bpy.context.scene.tris_color),  # Convert to tuple
                "quads": tuple(bpy.context.scene.quads_color),
                "ngons": tuple(bpy.context.scene.ngons_color),
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

        # Polygon type toggles with color pickers
        box = layout.box()
        box.label(text="Show Polygons:")

        # Triangles row
        row = box.row(align=True)
        split = row.split(factor=0.7)
        split.prop(context.scene, "show_tris", text="Triangles")
        split.prop(context.scene, "tris_color", text="")

        # Quads row
        row = box.row(align=True)
        split = row.split(factor=0.7)
        split.prop(context.scene, "show_quads", text="Quads")
        split.prop(context.scene, "quads_color", text="")

        # N-gons row
        row = box.row(align=True)
        split = row.split(factor=0.7)
        split.prop(context.scene, "show_ngons", text="N-Gons")
        split.prop(context.scene, "ngons_color", text="")

        # Add offset slider after the color boxes
        box = layout.box()
        box.label(text="Offset Settings:")
        box.prop(context.scene, "poly_offset", text="Overlay Face Offset")


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

    bpy.types.Scene.tris_color = bpy.props.FloatVectorProperty(
        name="Triangles Color",
        subtype="COLOR_GAMMA",  # This gives better color picking
        default=(1.0, 0.0, 0.0, 0.5),
        min=0.0,
        max=1.0,
        size=4,
        update=lambda self, context: update_visibility(),
    )
    bpy.types.Scene.quads_color = bpy.props.FloatVectorProperty(
        name="Quads Color",
        subtype="COLOR_GAMMA",
        default=(0.0, 0.0, 1.0, 0.5),
        min=0.0,
        max=1.0,
        size=4,
        update=lambda self, context: update_visibility(),
    )
    bpy.types.Scene.ngons_color = bpy.props.FloatVectorProperty(
        name="N-Gons Color",
        subtype="COLOR_GAMMA",
        default=(0.0, 1.0, 0.0, 0.5),
        min=0.0,
        max=1.0,
        size=4,
        update=lambda self, context: update_visibility(),
    )


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Register properties
    bpy.types.Scene.show_tris = bpy.props.BoolProperty(
        name="Show Triangles",
        description="Show triangle overlays",
        default=True,
        update=lambda self, context: update_visibility(),
    )
    bpy.types.Scene.show_quads = bpy.props.BoolProperty(
        name="Show Quads",
        description="Show quad overlays",
        default=True,
        update=lambda self, context: update_visibility(),
    )
    bpy.types.Scene.show_ngons = bpy.props.BoolProperty(
        name="Show N-gons",
        description="Show n-gon overlays",
        default=True,
        update=lambda self, context: update_visibility(),
    )

    # Add offset property
    bpy.types.Scene.poly_offset = bpy.props.FloatProperty(
        name="Polygon Offset",
        description="Offset distance for polygon overlays",
        default=0.001,
        min=0.0,
        max=1.0,
        precision=4,
        update=lambda self, context: update_visibility(),
    )


def unregister():
    if drawer:
        drawer.stop()

    # Unregister properties
    del bpy.types.Scene.show_tris
    del bpy.types.Scene.show_quads
    del bpy.types.Scene.show_ngons
    del bpy.types.Scene.poly_offset

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass


def update_visibility():
    drawer.show_tris = bpy.context.scene.show_tris
    drawer.show_quads = bpy.context.scene.show_quads
    drawer.show_ngons = bpy.context.scene.show_ngons
