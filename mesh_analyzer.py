# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

from collections import OrderedDict
from typing import List, Tuple

import bmesh
import bpy
import math


class MeshAnalyzer:
    def __init__(self):
        self.clear_data()
        # LRU cache with max size 10
        self.cache = (
            OrderedDict()
        )  # Keys are object names, values are AnalysisCache objects
        self.MAX_CACHE_SIZE = 10

    def clear_data(self):
        # Initialize with tuples of (vertices, normals)
        self.face_data = {
            "tri": ([], []),
            "quad": ([], []),
            "ngon": ([], []),
            "non_planar": ([], []),
        }

        self.vertex_data = {
            "single": ([], []),
            "n_pole": ([], []),
            "e_pole": ([], []),
            "high_pole": ([], []),
            "non_manifold": ([], []),
        }

        self.edge_data = {
            "non_manifold": ([], []),
            "sharp": ([], []),
            "seam": ([], []),
            "boundary": ([], []),
        }

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

    def analyze_mesh(self, obj):
        """Main analysis method organized by toggle type"""
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

        if not obj or obj.type != "MESH":
            return

        self.clear_data()
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        matrix_world = obj.matrix_world

        # Single vertices
        if props.show_single_vertices:
            for vert in bm.verts:
                if len(vert.link_edges) == 0:
                    pos = matrix_world @ vert.co
                    normal = matrix_world.to_3x3() @ vert.normal
                    self.vertex_data["single"][0].append(pos)
                    self.vertex_data["single"][1].append(normal)

        # N-pole vertices
        if props.show_n_pole_vertices:
            for vert in bm.verts:
                if len(vert.link_edges) == 3:
                    pos = matrix_world @ vert.co
                    normal = matrix_world.to_3x3() @ vert.normal
                    self.vertex_data["n_pole"][0].append(pos)
                    self.vertex_data["n_pole"][1].append(normal)

        # E-pole vertices
        if props.show_e_pole_vertices:
            for vert in bm.verts:
                if len(vert.link_edges) == 5:
                    pos = matrix_world @ vert.co
                    normal = matrix_world.to_3x3() @ vert.normal
                    self.vertex_data["e_pole"][0].append(pos)
                    self.vertex_data["e_pole"][1].append(normal)

        # High-pole vertices
        if props.show_high_pole_vertices:
            for vert in bm.verts:
                if len(vert.link_edges) >= 6:
                    pos = matrix_world @ vert.co
                    normal = matrix_world.to_3x3() @ vert.normal
                    self.vertex_data["high_pole"][0].append(pos)
                    self.vertex_data["high_pole"][1].append(normal)

        # Non-manifold vertices
        if props.show_non_manifold_vertices:
            for vert in bm.verts:
                if not vert.is_manifold:
                    pos = matrix_world @ vert.co
                    normal = matrix_world.to_3x3() @ vert.normal
                    self.vertex_data["non_manifold"][0].append(pos)

        # Edge Analysis
        if props.show_non_manifold_edges:
            for edge in bm.edges:
                if not edge.is_manifold:
                    pos = [matrix_world @ v.co for v in edge.verts]
                    normal = [matrix_world.to_3x3() @ v.normal for v in edge.verts]
                    self.edge_data["non_manifold"][0].extend(pos)
                    self.edge_data["non_manifold"][1].extend(normal)

        if props.show_sharp_edges:
            for edge in bm.edges:
                if edge.smooth is False:
                    pos = [matrix_world @ v.co for v in edge.verts]
                    normal = [matrix_world.to_3x3() @ v.normal for v in edge.verts]
                    self.edge_data["sharp"][0].extend(pos)
                    self.edge_data["sharp"][1].extend(normal)

        if props.show_seam_edges:
            for edge in bm.edges:
                if edge.seam:
                    pos = [matrix_world @ v.co for v in edge.verts]
                    normal = [matrix_world.to_3x3() @ v.normal for v in edge.verts]
                    self.edge_data["seam"][0].extend(pos)
                    self.edge_data["seam"][1].extend(normal)

        if props.show_boundary_edges:
            for edge in bm.edges:
                if edge.is_boundary:
                    pos = [matrix_world @ v.co for v in edge.verts]
                    normal = [matrix_world.to_3x3() @ v.normal for v in edge.verts]
                    self.edge_data["boundary"][0].extend(pos)
                    self.edge_data["boundary"][1].extend(normal)

        # Face Analysis - separated loops
        if props.show_tri_faces:
            for face in bm.faces:
                if len(face.verts) == 3:
                    pos = [matrix_world @ v.co for v in face.verts]
                    normal = [matrix_world.to_3x3() @ v.normal for v in face.verts]
                    self.face_data["tri"][0].extend(pos)
                    self.face_data["tri"][1].extend(normal)

        if props.show_quad_faces:
            for face in bm.faces:
                if len(face.verts) == 4:
                    verts = [matrix_world @ v.co for v in face.verts]
                    normals = [matrix_world.to_3x3() @ v.normal for v in face.verts]
                    # Create two triangles from quad
                    self.face_data["quad"][0].extend([verts[0], verts[1], verts[2]])
                    self.face_data["quad"][0].extend([verts[0], verts[2], verts[3]])
                    self.face_data["quad"][1].extend(
                        [normals[0], normals[1], normals[2]]
                    )
                    self.face_data["quad"][1].extend(
                        [normals[0], normals[2], normals[3]]
                    )

        if props.show_ngon_faces:
            for face in bm.faces:
                if len(face.verts) > 4:
                    verts = [matrix_world @ v.co for v in face.verts]
                    normals = [matrix_world.to_3x3() @ v.normal for v in face.verts]
                    # Fan triangulation from first vertex
                    for i in range(1, len(verts) - 1):
                        self.face_data["ngon"][0].extend(
                            [verts[0], verts[i], verts[i + 1]]
                        )
                        self.face_data["ngon"][1].extend(
                            [normals[0], normals[i], normals[i + 1]]
                        )

        if props.show_non_planar_faces:
            for face in bm.faces:
                if len(face.verts) > 3:
                    if not self.is_face_planar(face, props.non_planar_threshold):
                        verts = [matrix_world @ v.co for v in face.verts]
                        normals = [matrix_world.to_3x3() @ v.normal for v in face.verts]
                        # Fan triangulation from first vertex
                        for i in range(1, len(verts) - 1):
                            self.face_data["non_planar"][0].extend(
                                [verts[0], verts[i], verts[i + 1]]
                            )
                            self.face_data["non_planar"][1].extend(
                                [normals[0], normals[i], normals[i + 1]]
                            )

        bm.free()
