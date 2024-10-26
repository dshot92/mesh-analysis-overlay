# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

import bmesh
import bpy
import math


class MeshAnalyzer:
    def __init__(self):
        self.clear_data()

    def clear_data(self):
        self.tris_data = []
        self.tris_normals = []
        self.quads_data = []
        self.quads_normals = []
        self.ngons_data = []
        self.ngons_normals = []
        self.n_poles_data = []
        self.e_poles_data = []
        self.high_poles_data = []
        self.singles_data = []
        self.non_manifold_edges_data = []
        self.non_manifold_verts_data = []
        self.sharp_edges_data = []
        self.seam_edges_data = []
        self.non_planar_data = []
        self.non_planar_normals = []

    def is_face_planar(self, face, threshold_degrees):

        # Get first 3 vertices to define the reference plane
        v1, v2, v3 = [v.co for v in face.verts[:3]]

        # Calculate plane normal using first 3 vertices
        plane_normal = (v2 - v1).cross(v3 - v1).normalized()
        plane_point = v1

        # Check each remaining vertex's distance from plane
        for vert in face.verts[3:]:
            to_vert = (vert.co - plane_point).normalized()

            # Calculate angle between vertex direction and plane normal
            # cos(90° - angle) = sin(angle)
            angle = abs(90 - math.degrees(math.acos(abs(to_vert.dot(plane_normal)))))

            if angle > threshold_degrees:
                return False

        return True

    def analyze_mesh(self, obj, offset):
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

        # Check if any analysis is needed
        analyze_verts = (
            props.show_singles
            or props.show_non_manifold_verts
            or props.show_n_poles
            or props.show_e_poles
            or props.show_high_poles
        )
        analyze_edges = (
            props.show_non_manifold_edges
            or props.show_sharp_edges
            or props.show_seam_edges
        )
        analyze_faces = (
            props.show_tris
            or props.show_quads
            or props.show_ngons
            or props.show_non_planar
        )

        # Early return if nothing to analyze
        if not (analyze_verts or analyze_edges or analyze_faces):
            return

        # Clear previous data
        self.clear_data()

        mesh = obj.data
        matrix_world = obj.matrix_world

        # Create BMesh only if needed
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        # recalculate bm normals
        # bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

        # Analyze vertices for poles and singles and non-manifold verts
        if analyze_verts:
            for v in bm.verts:
                world_pos = matrix_world @ v.co
                edge_count = len(v.link_edges)

                if (edge_count == 0) and props.show_singles:
                    self.singles_data.append(world_pos)
                if edge_count == 3 and props.show_n_poles:
                    self.n_poles_data.append(world_pos)
                if edge_count == 5 and props.show_e_poles:
                    self.e_poles_data.append(world_pos)
                if edge_count >= 6 and props.show_high_poles:
                    self.high_poles_data.append(world_pos)

                if (not v.is_manifold) and props.show_non_manifold_verts:
                    self.non_manifold_verts_data.append(world_pos)

        # Analyze non-manifold edges
        if analyze_edges:
            for edge in bm.edges:
                if (not edge.is_manifold) and props.show_non_manifold_edges:
                    v1 = matrix_world @ edge.verts[0].co
                    v2 = matrix_world @ edge.verts[1].co
                    self.non_manifold_edges_data.extend([v1, v2])
                if (not edge.smooth) and props.show_sharp_edges:
                    v1 = matrix_world @ edge.verts[0].co
                    v2 = matrix_world @ edge.verts[1].co
                    self.sharp_edges_data.extend([v1, v2])
                if (edge.seam) and props.show_seam_edges:
                    v1 = matrix_world @ edge.verts[0].co
                    v2 = matrix_world @ edge.verts[1].co
                    self.seam_edges_data.extend([v1, v2])

        # Analyze faces
        if analyze_faces:
            for face in bm.faces:
                if (len(face.verts) == 3) and props.show_tris:  # Triangle
                    # Get vertex normals instead of face normal
                    analyze_verts = face.verts[:]
                    vert_normals = [
                        matrix_world.to_3x3() @ v.normal for v in analyze_verts
                    ]
                    vert_coords = [matrix_world @ v.co for v in analyze_verts]

                    # Apply offset using vertex normals
                    analyze_verts = [
                        vert_coords[i] + vert_normals[i] * offset for i in range(3)
                    ]
                    self.tris_data.extend(analyze_verts)
                    self.tris_normals.extend([matrix_world.to_3x3() @ face.normal] * 3)
                elif (len(face.verts) == 4) and props.show_quads:  # Quad
                    # quads_to_process.append(face)
                    analyze_verts = face.verts[:]
                    vert_normals = [
                        matrix_world.to_3x3() @ v.normal for v in analyze_verts
                    ]
                    vert_coords = [matrix_world @ v.co for v in analyze_verts]

                    # Create two triangles from the quad (0,1,2) and (0,2,3)
                    tri1_indices = [0, 1, 2]
                    tri2_indices = [0, 2, 3]

                    # First triangle
                    tri1_verts = [
                        vert_coords[i] + vert_normals[i] * offset for i in tri1_indices
                    ]
                    self.quads_data.extend(tri1_verts)
                    self.quads_normals.extend([matrix_world.to_3x3() @ face.normal] * 3)

                    # Second triangle
                    tri2_verts = [
                        vert_coords[i] + vert_normals[i] * offset for i in tri2_indices
                    ]
                    self.quads_data.extend(tri2_verts)
                    self.quads_normals.extend([matrix_world.to_3x3() @ face.normal] * 3)
                elif (len(face.verts) > 4) and props.show_ngons:  # N-gon
                    # ngons_to_process.append(face)
                    analyze_verts = face.verts[:]
                    vert_normals = [
                        matrix_world.to_3x3() @ v.normal for v in analyze_verts
                    ]
                    vert_coords = [matrix_world @ v.co for v in analyze_verts]

                    # Create triangles by fanning from the first vertex
                    for i in range(1, len(analyze_verts) - 1):
                        # Create triangle indices (0, i, i+1)
                        tri_indices = [0, i, i + 1]

                        # Create triangle vertices with offset
                        tri_verts = [
                            vert_coords[idx] + vert_normals[idx] * offset
                            for idx in tri_indices
                        ]
                        self.ngons_data.extend(tri_verts)
                        self.ngons_normals.extend(
                            [matrix_world.to_3x3() @ face.normal] * 3
                        )
                if props.show_non_planar and len(face.verts) > 3:
                    if not self.is_face_planar(face, props.non_planar_threshold):
                        analyze_verts = face.verts[:]
                        vert_normals = [
                            matrix_world.to_3x3() @ v.normal for v in analyze_verts
                        ]
                        vert_coords = [matrix_world @ v.co for v in analyze_verts]

                        # Triangulate the face for display
                        for i in range(1, len(analyze_verts) - 1):
                            tri_indices = [0, i, i + 1]
                            tri_verts = [
                                vert_coords[idx] + vert_normals[idx] * offset
                                for idx in tri_indices
                            ]
                            self.non_planar_data.extend(tri_verts)
                            self.non_planar_normals.extend(
                                [matrix_world.to_3x3() @ face.normal] * 3
                            )

        # Free BMesh
        bm.free()
