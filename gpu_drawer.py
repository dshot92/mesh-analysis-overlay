# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from .mesh_topology_analyzer import MeshTopologyAnalyzer


class GPUDrawer:
    def __init__(self):
        self.handle = None
        self.batch = None
        self.shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        self.is_running = False
        self.mesh_analyzer = MeshTopologyAnalyzer()
        self.show_tris = True
        self.show_quads = True
        self.show_ngons = True
        self.show_poles = True
        self.show_singles = True
        self.show_non_manifold_edges = True
        self.show_non_manifold_verts = True

    def update_visibility(self):
        props = bpy.context.scene.GPU_Topology_Overlay_Properties
        self.show_tris = props.show_tris
        self.show_quads = props.show_quads
        self.show_ngons = props.show_ngons
        self.show_poles = props.show_poles
        self.show_singles = props.show_singles
        self.show_non_manifold_edges = props.show_non_manifold_edges
        self.show_non_manifold_verts = props.show_non_manifold_verts

    def draw(self):

        props = bpy.context.scene.GPU_Topology_Overlay_Properties
        self.update_visibility()

        obj = bpy.context.active_object
        if obj and obj.type == "MESH":
            # Draw all elements using the stored data
            if self.show_tris:
                if self.mesh_analyzer.tris_data:
                    offset_verts = [
                        v + n * props.overlay_face_offset
                        for v, n in zip(
                            self.mesh_analyzer.tris_data,
                            self.mesh_analyzer.tris_normals,
                        )
                    ]
                self._draw_elements(offset_verts, props.tris_color, "TRIS")

            if self.show_quads:
                if self.mesh_analyzer.quads_data:
                    offset_verts = [
                        v + n * props.overlay_face_offset
                        for v, n in zip(
                            self.mesh_analyzer.quads_data,
                            self.mesh_analyzer.quads_normals,
                        )
                    ]
                    self._draw_elements(
                        offset_verts,
                        props.quads_color,
                        "TRIS",  # Quads are triangulated
                    )

            if self.show_ngons:
                if self.mesh_analyzer.ngons_data:
                    offset_verts = [
                        v + n * props.overlay_face_offset
                        for v, n in zip(
                            self.mesh_analyzer.ngons_data,
                            self.mesh_analyzer.ngons_normals,
                        )
                    ]
                self._draw_elements(offset_verts, props.ngons_color, "TRIS")

            if self.show_poles:
                if self.mesh_analyzer.poles_data:
                    self._draw_elements(
                        self.mesh_analyzer.poles_data,
                        props.poles_color,
                        "POINTS",
                        size=props.overlay_vertex_radius,
                    )

            if self.show_singles:
                if self.mesh_analyzer.singles_data:
                    self._draw_elements(
                        self.mesh_analyzer.singles_data,
                        props.singles_color,
                        "POINTS",
                        size=props.overlay_vertex_radius,
                    )

            if self.show_non_manifold_edges:
                if self.mesh_analyzer.non_manifold_edges_data:
                    self._draw_elements(
                        self.mesh_analyzer.non_manifold_edges_data,
                        props.non_manifold_edges_color,
                        "LINES",
                        line_width=props.overlay_edge_width,
                    )

            if self.show_non_manifold_verts:
                if self.mesh_analyzer.non_manifold_verts_data:
                    self._draw_elements(
                        self.mesh_analyzer.non_manifold_verts_data,
                        props.non_manifold_verts_color,
                        "POINTS",
                        size=props.overlay_vertex_radius,
                    )

    def update_topology(self, scene):
        if self.is_running:
            obj = bpy.context.active_object
            if obj and obj.type == "MESH":
                if obj.mode == "EDIT":
                    obj.update_from_editmode()

                # Analyze mesh
                props = scene.GPU_Topology_Overlay_Properties
                self.mesh_analyzer.analyze_mesh(obj, props.overlay_face_offset)

                # Redraw viewport
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == "VIEW_3D":
                            area.tag_redraw()

    def _draw_elements(self, vertices, color, primitive, size=None, line_width=None):
        if not vertices:
            return
        colors = [color] * len(vertices)
        self.shader.bind()

        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")

        # Set size/width based on primitive type
        if primitive == "POINTS":
            gpu.state.point_size_set(size)
        elif primitive == "LINES":
            gpu.state.line_width_set(line_width)

        self.batch = batch_for_shader(
            self.shader, primitive, {"pos": vertices, "color": colors}
        )
        self.batch.draw(self.shader)

    def _draw_points(self, positions, color):
        if not positions:
            return
        for pos in positions:
            self._draw_sphere(pos, color)

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
            bpy.app.handlers.depsgraph_update_post.append(self.update_topology)
            self.is_running = True

            # Force initial analysis
            obj = bpy.context.active_object
            if obj and obj.type == "MESH":
                props = bpy.context.scene.GPU_Topology_Overlay_Properties
                self.mesh_analyzer.analyze_mesh(obj, props.overlay_face_offset)
                # Force viewport redraw
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == "VIEW_3D":
                            area.tag_redraw()

    def stop(self):
        if self.is_running:
            if self.handle:
                bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
            # Remove depsgraph callback
            if self.update_topology in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(self.update_topology)
            self.handle = None
            self.is_running = False


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
