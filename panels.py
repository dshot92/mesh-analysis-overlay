# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from .operators import drawer
from .mesh_analyzer import MeshAnalyzer


class Mesh_Analysis_Overlay_Panel(bpy.types.Panel):
    bl_label = "Mesh Analysis Overlay"
    bl_idname = "VIEW3D_PT_mesh_analysis_overlay"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mesh Analysis Overlay"

    _stats_cache = {}  # Class variable to store statistics

    @classmethod
    def clear_stats_cache(cls):
        """Clear the statistics cache"""
        cls._stats_cache.clear()

    def draw(self, context):
        layout = self.layout
        props = context.scene.Mesh_Analysis_Overlay_Properties
        factor = 0.85

        # Toggle button for overlay
        row = layout.row()
        row.operator(
            "view3d.mesh_analysis_overlay",
            text="Show Mesh Overlay",
            icon="OVERLAY",
            depress=drawer.is_running,
        )

        # Info text
        ROW_SCALE = 0.5
        ALIGNMENT = "LEFT"
        row = layout.row()
        row.scale_y = ROW_SCALE
        row.alignment = ALIGNMENT
        row.label(text="Overlay data is cached.", icon="INFO")
        row = layout.row()
        row.scale_y = ROW_SCALE
        row.alignment = ALIGNMENT
        row.label(text="Refresh by:")
        row = layout.row()
        row.scale_y = ROW_SCALE
        row.alignment = ALIGNMENT
        row.label(text="• Toggling Overlay off/on")
        row = layout.row()
        row.scale_y = ROW_SCALE
        row.alignment = ALIGNMENT
        row.label(text="• Toggling Edit Mode off/on")

        # Faces panel
        header, panel = layout.panel("faces_panel", default_closed=False)
        header.label(text="Faces")
        if panel:
            # Triangles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "tri_faces_enabled", text="Triangles")
            split.prop(props, "tri_faces_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "tri_faces"

            # Quads row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "quad_faces_enabled", text="Quads")
            split.prop(props, "quad_faces_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "quad_faces"

            # N-gons row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "ngon_faces_enabled", text="N-Gons")
            split.prop(props, "ngon_faces_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "ngon_faces"

            # Non-planar faces row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "non_planar_faces_enabled", text="Non-Planar Faces")
            split.prop(props, "non_planar_faces_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "non_planar_faces"

            # Degenerate faces row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "degenerate_faces_enabled", text="Degenerate Faces")
            split.prop(props, "degenerate_faces_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "degenerate_faces"

        # Edges panel
        header, panel = layout.panel("edges_panel", default_closed=False)
        header.label(text="Edges")
        if panel:
            # Non-manifold edges row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "non_manifold_e_edges_enabled", text="Non-Manifold Edges")
            split.prop(props, "non_manifold_e_edges_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "non_manifold_e_edges"

            # Sharp edges row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "sharp_edges_enabled", text="Sharp Edges")
            split.prop(props, "sharp_edges_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "sharp_edges"

            # Seam edges row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "seam_edges_enabled", text="Seam Edges")
            split.prop(props, "seam_edges_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "seam_edges"

            # Boundary edges
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "boundary_edges_enabled", text="Boundary Edges")
            split.prop(props, "boundary_edges_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "boundary_edges"

        # Vertices panel
        header, panel = layout.panel("vertices_panel", default_closed=False)
        header.label(text="Vertices")
        if panel:
            # Singles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "single_vertices_enabled", text="Single Vertices")
            split.prop(props, "single_vertices_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "single_vertices"

            # Non-manifold vertices row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(
                props, "non_manifold_v_vertices_enabled", text="Non-Manifold Vertices"
            )
            split.prop(props, "non_manifold_v_vertices_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "non_manifold_v_vertices"

            # N-poles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "n_pole_vertices_enabled", text="N-Poles (3)")
            split.prop(props, "n_pole_vertices_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "n_pole_vertices"

            # E-poles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "e_pole_vertices_enabled", text="E-Poles (5)")
            split.prop(props, "e_pole_vertices_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "e_pole_vertices"

            # High-poles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "high_pole_vertices_enabled", text="High-Poles (6+)")
            split.prop(props, "high_pole_vertices_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "high_pole_vertices"

        # Statistics panel
        header, panel = layout.panel("statistics_panel", default_closed=False)
        header.label(text="Statistics")

        if panel:
            self.draw_statistics(context, panel)

        # Offset settings
        header, panel = layout.panel("panel_settings", default_closed=True)
        header.label(text="Overlay Settings")

        if panel:
            panel.prop(props, "overlay_offset", text="Overlay Offset")
            panel.prop(props, "overlay_edge_width", text="Overlay Edge Width")
            panel.prop(props, "overlay_vertex_radius", text="Overlay Vertex Radius")
            panel.prop(props, "non_planar_threshold", text="Non-Planar Threshold")

    def draw_statistics(self, context, panel):
        """Draw statistics using cached values when possible"""
        if not (
            drawer.is_running
            and context.active_object
            and context.active_object.type == "MESH"
        ):
            panel.label(text="Enable overlay to see statistics")
            return

        obj = context.active_object
        props = context.scene.Mesh_Analysis_Overlay_Properties

        # Get cached stats or calculate new ones
        if obj.name not in self._stats_cache:
            analyzer = MeshAnalyzer.get_analyzer(obj)
            stats = {"mode": context.mode, "features": {}}

            feature_groups = [
                ("Faces", MeshAnalyzer._cache.face_features),
                ("Edges", MeshAnalyzer._cache.edge_features),
                ("Vertices", MeshAnalyzer._cache.vertex_features),
            ]

            for group_name, features in feature_groups:
                active_features = [
                    f for f in features if getattr(props, f"{f}_enabled", False)
                ]
                if active_features:
                    stats["features"][group_name] = {
                        feature: len(analyzer.analyze_feature(feature))
                        for feature in active_features
                    }

            self._stats_cache[obj.name] = stats

        # Draw statistics from cache
        stats = self._stats_cache[obj.name]
        box = panel.box()

        for group_name, features in stats["features"].items():
            if features:
                col = box.column(align=True)
                col.label(text=f"{group_name}:")
                for feature_name, count in features.items():
                    row = col.row()
                    row.label(text=feature_name.replace("_", " ").title())
                    row.label(text=str(count))


classes = (Mesh_Analysis_Overlay_Panel,)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)


def unregister():
    for bl_class in reversed(classes):
        bpy.utils.unregister_class(bl_class)
