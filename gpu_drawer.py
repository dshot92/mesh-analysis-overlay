# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from .mesh_analyzer import MeshAnalyzer


class GPUDrawer:
    def __init__(self):
        self.handle = None
        self.batch = None
        self.shader = gpu.shader.from_builtin("FLAT_COLOR")
        self.is_running = False
        self.mesh_analyzer = MeshAnalyzer()
        self.show_tris = True
        self.show_quads = True
        self.show_ngons = True
        self.show_singles = True
        self.show_non_manifold_edges = True
        self.show_non_manifold_verts = True
        self.show_n_poles = True
        self.show_e_poles = True
        self.show_high_poles = True
        self.show_sharp_edges = True

    def update_visibility(self):
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        self.show_tris = props.show_tris
        self.show_quads = props.show_quads
        self.show_ngons = props.show_ngons
        self.show_singles = props.show_singles
        self.show_non_manifold_edges = props.show_non_manifold_edges
        self.show_non_manifold_verts = props.show_non_manifold_verts
        self.show_n_poles = props.show_n_poles
        self.show_e_poles = props.show_e_poles
        self.show_high_poles = props.show_high_poles
        self.show_sharp_edges = props.show_sharp_edges

    def draw(self):

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        self.update_visibility()

        obj = bpy.context.active_object
        if obj and obj.type == "MESH":
            # Draw all elements using the stored data
            if self.show_tris:
                self._draw_elements(
                    self.mesh_analyzer.tris_data, props.tris_color, "TRIS"
                )

            if self.show_quads:
                self._draw_elements(
                    self.mesh_analyzer.quads_data,
                    props.quads_color,
                    "TRIS",  # Quads are triangulated
                )

            if self.show_ngons:
                self._draw_elements(
                    self.mesh_analyzer.ngons_data,
                    props.ngons_color,
                    "TRIS",
                )

            if self.show_singles:
                self._draw_elements(
                    self.mesh_analyzer.singles_data,
                    props.singles_color,
                    "POINTS",
                )

            if self.show_non_manifold_edges:
                self._draw_elements(
                    self.mesh_analyzer.non_manifold_edges_data,
                    props.non_manifold_edges_color,
                    "LINES",
                )

            if self.show_non_manifold_verts:
                self._draw_elements(
                    self.mesh_analyzer.non_manifold_verts_data,
                    props.non_manifold_verts_color,
                    "POINTS",
                )

            if self.show_n_poles:
                self._draw_elements(
                    self.mesh_analyzer.n_poles_data,
                    props.n_poles_color,
                    "POINTS",
                )

            if self.show_e_poles:
                self._draw_elements(
                    self.mesh_analyzer.e_poles_data,
                    props.e_poles_color,
                    "POINTS",
                )

            if self.show_high_poles:
                self._draw_elements(
                    self.mesh_analyzer.high_poles_data,
                    props.high_poles_color,
                    "POINTS",
                )

            if self.show_sharp_edges:
                self._draw_elements(
                    self.mesh_analyzer.sharp_edges_data,
                    props.sharp_edges_color,
                    "LINES",
                )

    def depsgraph_update(self, scene, depsgraph):
        if self.is_running:
            obj = bpy.context.active_object
            if obj and obj.type == "MESH":
                if obj.mode == "EDIT":
                    obj.update_from_editmode()

                # Analyze mesh
                props = scene.Mesh_Analysis_Overlay_Properties
                self.mesh_analyzer.analyze_mesh(obj, props.overlay_face_offset)

                # Redraw viewport
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == "VIEW_3D":
                            area.tag_redraw()

    def _draw_elements(self, vertices, color, primitive_type):
        if not vertices:
            return
        colors = [color] * len(vertices)
        self.shader.bind()

        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

        # Set size/width based on primitive type
        if primitive_type == "POINTS":
            gpu.state.point_size_set(props.overlay_vertex_radius)
        elif primitive_type == "LINES":
            gpu.state.line_width_set(props.overlay_edge_width)

        self.batch = batch_for_shader(
            self.shader, primitive_type, {"pos": vertices, "color": colors}
        )
        self.batch.draw(self.shader)

    def start(self):
        if not self.is_running:
            self.handle = bpy.types.SpaceView3D.draw_handler_add(
                self.draw, (), "WINDOW", "POST_VIEW"
            )
            bpy.app.handlers.depsgraph_update_post.append(self.depsgraph_update)
            self.is_running = True

            # Force initial analysis
            obj = bpy.context.active_object
            if obj and obj.type == "MESH":
                props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
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
            if self.depsgraph_update in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(self.depsgraph_update)
            self.handle = None
            self.is_running = False
