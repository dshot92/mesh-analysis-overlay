import bpy
import gpu
from gpu_extras.batch import batch_for_shader


class SimpleTriangleGPU:
    def __init__(self):
        self.handle = None
        self.batch = None
        self.shader = None
        self.is_running = False

    def draw(self):
        self.shader.bind()
        self.shader.uniform_float("color", (1, 0, 0, 1))  # Red color (R, G, B, A)
        self.batch.draw(self.shader)

    def create_batch(self):
        vertices = [(0, 0, 0), (0.5, 1, 0), (1, 0, 0)]
        self.shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        self.batch = batch_for_shader(self.shader, "TRIS", {"pos": vertices})

    def start(self):
        if not self.is_running:
            self.create_batch()
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
