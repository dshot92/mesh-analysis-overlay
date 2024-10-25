import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from .mesh_topology_analyzer import MeshTopologyAnalyzer
import math


class GPUDrawer:
    def __init__(self):
        self.handle = None
        self.batch = None
        self.shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        self.is_running = False
        self._timer = None
        self.mesh_analyzer = MeshTopologyAnalyzer()
        self.show_tris = True
        self.show_quads = True
        self.show_ngons = True
        self.show_poles = True
        self.sphere_vertices = self.create_sphere_vertices(radius=0.02, segments=8)

    def update_visibility(self):
        self.show_tris = bpy.context.scene.GPU_Topology_Overlay_Properties.show_tris
        self.show_quads = bpy.context.scene.GPU_Topology_Overlay_Properties.show_quads
        self.show_ngons = bpy.context.scene.GPU_Topology_Overlay_Properties.show_ngons
        self.show_poles = bpy.context.scene.GPU_Topology_Overlay_Properties.show_poles

    def create_sphere_vertices(self, radius=0.02, segments=8):
        """Create vertices for a low-poly sphere"""
        vertices = []
        # Create vertices for a UV sphere
        for i in range(segments):
            for j in range(segments):
                phi = (i * 2 * 3.141592) / segments
                theta = (j * 3.141592) / segments

                x = radius * math.sin(theta) * math.cos(phi)
                y = radius * math.sin(theta) * math.sin(phi)
                z = radius * math.cos(theta)

                vertices.append(Vector((x, y, z)))
        return vertices

    def draw(self):
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        props = bpy.context.scene.GPU_Topology_Overlay_Properties
        self.update_visibility()

        obj = bpy.context.active_object
        if obj and self.mesh_analyzer:
            bpy.context.view_layer.update()
            if obj.mode == "EDIT":
                obj.update_from_editmode()

            # Collect faces
            faces = []
            face_colors = []
            offset_value = props.poly_offset

            if self.show_tris:
                self.mesh_analyzer.analyze_tris(obj, offset_value)
                faces.extend(self.mesh_analyzer.tris)
                face_colors.extend(
                    [tuple(props.tris_color)] * len(self.mesh_analyzer.tris)
                )

            if self.show_quads:
                self.mesh_analyzer.analyze_quads(obj, offset_value)
                faces.extend(self.mesh_analyzer.quads)
                face_colors.extend(
                    [tuple(props.quads_color)] * len(self.mesh_analyzer.quads)
                )

            if self.show_ngons:
                self.mesh_analyzer.analyze_ngons(obj, offset_value)
                faces.extend(self.mesh_analyzer.ngons)
                face_colors.extend(
                    [tuple(props.ngons_color)] * len(self.mesh_analyzer.ngons)
                )

            # Collect vertices
            vertices = []
            vertex_colors = []
            if self.show_poles:
                self.mesh_analyzer.analyze_poles(obj)
                vertices = self.mesh_analyzer.poles
                vertex_colors = [tuple(props.poles_color)] * len(vertices)

            # Draw faces
            if faces:
                vertex_shader = gpu.shader.from_builtin("SMOOTH_COLOR")
                vertex_shader.bind()
                mesh_data = {"vertices": faces, "colors": face_colors}
                self.create_batch(mesh_data, "TRIS")
                self.batch.draw(vertex_shader)

            # Draw vertices
            if vertices:
                vertex_shader = gpu.shader.from_builtin("SMOOTH_COLOR")
                vertex_shader.bind()
                gpu.state.point_size_set(props.poles_radius)
                mesh_data = {"vertices": vertices, "colors": vertex_colors}
                self.create_batch(mesh_data, "POINTS")
                self.batch.draw(vertex_shader)

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")

    def create_batch(self, mesh_data, primitive="TRIS"):
        self.batch = batch_for_shader(
            self.shader,
            primitive,
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


class GPU_Overlay_Topology(bpy.types.Operator):
    bl_idname = "view3d.gpu_overlay_topology"
    bl_label = "Toggle GPU Overlay Topology"
    bl_description = "Toggle the display of the GPU Overlay Topology in the 3D viewport"

    def execute(self, context):
        if drawer.is_running:
            drawer.stop()
        else:
            drawer.start()
        # Force panel refresh
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
        return {"FINISHED"}


classes = (GPU_Overlay_Topology,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    if drawer:
        drawer.stop()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
