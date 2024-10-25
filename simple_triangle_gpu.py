import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector


class SimpleTriangleGPU:
    def __init__(self):
        self.handle = None
        self.batch = None
        self.shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        self.is_running = False

    def draw(self):
        # Enable alpha blending
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")

        self.shader.bind()

        # Get the active object
        obj = bpy.context.active_object

        if obj and obj.type == "MESH":
            # Update the batch for the current object
            self.create_batch(obj)

            # Draw the batch
            self.batch.draw(self.shader)

        # Restore GPU state
        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")

    def create_batch(self, obj):
        vertices = []
        colors = []

        # Iterate through faces
        for face in obj.data.polygons:
            # Get face normal and create small offset
            offset = face.normal * 0.001

            # Apply offset to vertices
            face_verts = [
                (obj.matrix_world @ Vector(obj.data.vertices[v].co)) + offset
                for v in face.vertices
            ]
            face_color = (
                (1, 0, 0, 0.5)
                if len(face.vertices) == 3
                else (0, 0, 1, 0.5) if len(face.vertices) == 4 else (0, 1, 0, 0.5)
            )

            # Triangulate the face
            for i in range(1, len(face_verts) - 1):
                vertices.extend([face_verts[0], face_verts[i], face_verts[i + 1]])
                colors.extend([face_color, face_color, face_color])

        self.batch = batch_for_shader(
            self.shader, "TRIS", {"pos": vertices, "color": colors}
        )

    def start(self):
        if not self.is_running:
            self.handle = bpy.types.SpaceView3D.draw_handler_add(
                self.draw, (), "WINDOW", "POST_VIEW"
            )
            self.is_running = True

    def stop(self):
        if self.is_running:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
            self.handle = None
            self.is_running = False


simple_triangle = SimpleTriangleGPU()


class SimpleTriangleOperator(bpy.types.Operator):
    bl_idname = "view3d.simple_triangle"
    bl_label = "Toggle Simple Triangle"
    bl_description = "Toggle the display of a simple triangle in the 3D viewport"

    def execute(self, context):
        if simple_triangle.is_running:
            simple_triangle.stop()
        else:
            simple_triangle.start()
        context.area.tag_redraw()
        return {"FINISHED"}


class SimpleTrianglePanel(bpy.types.Panel):
    bl_label = "Simple Triangle GPU"
    bl_idname = "VIEW3D_PT_simple_triangle"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Simple Triangle"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        if simple_triangle.is_running:
            row.operator(
                SimpleTriangleOperator.bl_idname, text="Hide Triangle", icon="HIDE_ON"
            )
        else:
            row.operator(
                SimpleTriangleOperator.bl_idname, text="Show Triangle", icon="HIDE_OFF"
            )


classes = (SimpleTriangleOperator, SimpleTrianglePanel)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    simple_triangle.stop()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
