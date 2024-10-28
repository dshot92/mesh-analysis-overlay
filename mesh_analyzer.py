# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

import bpy
import math
import bmesh

from typing import List, Tuple
from mathutils import Vector


class MeshAnalyzer:
    def __init__(self):
        self.clear_data()

    def clear_data(self):
        self.face_data = {
            "tris": [],
            "quads": [],
            "ngons": [],
            "non_planar": [],
        }
        self.vertex_data = {
            "singles": [],
            "n_poles": [],
            "e_poles": [],
            "high_poles": [],
            "non_manifold": [],
        }
        self.edge_data = {
            "non_manifold": [],
            "sharp": [],
            "seam": [],
            "boundary": [],  # Add boundary edges
        }

    def _should_analyze(self, props) -> Tuple[bool, bool, bool]:
        """Determine which mesh elements need analysis"""
        analyze_verts = any(
            [
                props.show_singles_vertices,
                props.show_non_manifold_vertices,
                props.show_n_poles_vertices,
                props.show_e_poles_vertices,
                props.show_high_poles_vertices,
            ]
        )

        analyze_edges = any(
            [
                props.show_non_manifold_edges,
                props.show_sharp_edges,
                props.show_seam_edges,
                props.show_boundary_edges,  # Add boundary check
            ]
        )

        analyze_faces = any(
            [
                props.show_tris_faces,
                props.show_quads_faces,
                props.show_ngons_faces,
                props.show_non_planar_faces,
            ]
        )

        return analyze_verts, analyze_edges, analyze_faces

    def is_face_planar(self, face, threshold_degrees: float) -> bool:
        """Check if a face is planar within the given threshold"""
        if len(face.verts) <= 3:
            return True

        # Get first 3 vertices to define reference plane
        v1, v2, v3 = [v.co for v in face.verts[:3]]
        plane_normal = (v2 - v1).cross(v3 - v1).normalized()

        # Check remaining vertices against plane
        for vert in face.verts[3:]:
            to_vert = (vert.co - v1).normalized()
            angle = abs(90 - math.degrees(math.acos(abs(to_vert.dot(plane_normal)))))
            if angle > threshold_degrees:
                return False
        return True

    def _get_face_data_with_offset(self, face, matrix_world, offset) -> List[Vector]:
        """Get transformed and offset vertex positions for a face"""
        return [
            (matrix_world @ v.co) + ((matrix_world.to_3x3() @ v.normal) * offset)
            for v in face.verts
        ]

    def _process_face(self, face, matrix_world, props):
        """Process a single face for triangles, quads, ngons and planarity"""
        vert_count = len(face.verts)
        offset = props.overlay_offset
        offset_verts = self._get_face_data_with_offset(face, matrix_world, offset)

        # Triangulate and store vertices based on face type
        if vert_count == 3 and props.show_tris_faces:
            self.face_data["tris"].extend(offset_verts)
        elif vert_count == 4 and props.show_quads_faces:
            self.face_data["quads"].extend(
                [offset_verts[i] for i in (0, 1, 2, 0, 2, 3)]
            )
        elif vert_count > 4 and props.show_ngons_faces:
            for i in range(1, vert_count - 1):
                self.face_data["ngons"].extend(
                    [offset_verts[0], offset_verts[i], offset_verts[i + 1]]
                )

        # Check planarity for faces with more than 3 vertices
        if vert_count > 3 and props.show_non_planar_faces:
            if not self.is_face_planar(face, props.non_planar_threshold):
                for i in range(1, vert_count - 1):
                    self.face_data["non_planar"].extend(
                        [offset_verts[0], offset_verts[i], offset_verts[i + 1]]
                    )

    def _get_vertex_data_with_offset(self, vert, matrix_world, offset) -> Vector:
        """Get transformed and offset vertex position"""
        world_pos = matrix_world @ vert.co
        return world_pos + ((matrix_world.to_3x3() @ vert.normal) * offset)

    def _process_vertex(self, vert, matrix_world, props):
        """Process a single vertex for poles and manifold status"""
        offset_pos = self._get_vertex_data_with_offset(
            vert, matrix_world, props.overlay_offset
        )
        edge_count = len(vert.link_edges)

        if edge_count == 0 and props.show_singles_vertices:
            self.vertex_data["singles"].append(offset_pos)
        if edge_count == 3 and props.show_n_poles_vertices:
            self.vertex_data["n_poles"].append(offset_pos)
        if edge_count == 5 and props.show_e_poles_vertices:
            self.vertex_data["e_poles"].append(offset_pos)
        if edge_count >= 6 and props.show_high_poles_vertices:
            self.vertex_data["high_poles"].append(offset_pos)
        if not vert.is_manifold and props.show_non_manifold_vertices:
            self.vertex_data["non_manifold"].append(offset_pos)

    def _process_edge(self, edge, matrix_world, props):
        """Process a single edge for manifold status, sharpness, seams and boundaries"""
        offset_v1 = self._get_vertex_data_with_offset(
            edge.verts[0], matrix_world, props.overlay_offset
        )
        offset_v2 = self._get_vertex_data_with_offset(
            edge.verts[1], matrix_world, props.overlay_offset
        )

        if not edge.is_manifold and props.show_non_manifold_edges:
            self.edge_data["non_manifold"].extend([offset_v1, offset_v2])
        if not edge.smooth and props.show_sharp_edges:
            self.edge_data["sharp"].extend([offset_v1, offset_v2])
        if edge.seam and props.show_seam_edges:
            self.edge_data["seam"].extend([offset_v1, offset_v2])
        if len(edge.link_faces) == 1 and props.show_boundary_edges:
            self.edge_data["boundary"].extend([offset_v1, offset_v2])

    def analyze_mesh(self, obj):
        """Main analysis method"""
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        offset = props.overlay_offset

        analyze_verts, analyze_edges, analyze_faces = self._should_analyze(props)

        if not any([analyze_verts, analyze_edges, analyze_faces]):
            return

        self.clear_data()
        matrix_world = obj.matrix_world

        # Create BMesh
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        # Process vertices
        if analyze_verts:
            for vert in bm.verts:
                self._process_vertex(vert, matrix_world, props)

        # Process edges
        if analyze_edges:
            for edge in bm.edges:
                self._process_edge(edge, matrix_world, props)

        # Process faces
        if analyze_faces:
            for face in bm.faces:
                self._process_face(face, matrix_world, props)

        bm.free()
