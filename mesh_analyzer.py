# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

from collections import OrderedDict
from typing import List, Tuple

import bmesh
import bpy
import math
from bpy.types import Object


class MeshAnalyzer:
    def __init__(self, obj: Object):
        if not obj or obj.type != "MESH":
            raise ValueError("Invalid mesh object")

        self.clear_data()
        self.active_object = obj
        self.analyzed_features = set()
        self.update(obj)  # Perform initial analysis

    def update(self, obj):
        """Update analysis if needed"""
        if obj != self.active_object:
            return  # Only analyze the object we were initialized with

        # Get currently enabled features from properties
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        enabled_features = self._get_enabled_features(props)

        # Analyze any enabled features that haven't been analyzed yet
        for feature in enabled_features:
            if feature not in self.analyzed_features:
                self.analyze_specific_feature(obj, feature)
                self.analyzed_features.add(feature)

    def _get_enabled_features(self, props):
        """Get list of currently enabled features from properties"""
        enabled = []

        # Check vertex features
        for key in self.vertex_data.keys():
            if getattr(props, f"show_{key}_vertices", False):
                enabled.append(key)

        # Check edge features
        for key in self.edge_data.keys():
            if getattr(props, f"show_{key}_edges", False):
                enabled.append(key)

        # Check face features
        for key in self.face_data.keys():
            if getattr(props, f"show_{key}_faces", False):
                enabled.append(key)

        return enabled

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

    def analyze_specific_feature(self, obj, feature_type: str):
        """Analyze a single feature type"""
        if not obj or obj.type != "MESH":
            return

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        matrix_world = obj.matrix_world

        if feature_type in self.vertex_data:
            self._analyze_vertex_feature(bm, matrix_world, feature_type)
        elif feature_type in self.edge_data:
            self._analyze_edge_feature(bm, matrix_world, feature_type)
        elif feature_type in self.face_data:
            self._analyze_face_feature(bm, matrix_world, feature_type)

        bm.free()

    def _analyze_vertex_feature(self, bm, matrix_world, feature_type):
        """Analyze a specific vertex feature"""
        for vert in bm.verts:
            if self._check_vertex_condition(vert, feature_type):
                pos = matrix_world @ vert.co
                normal = matrix_world.to_3x3() @ vert.normal
                self.vertex_data[feature_type][0].append(pos)
                self.vertex_data[feature_type][1].append(normal)

    def _check_vertex_condition(self, vert, feature_type):
        conditions = {
            "single": lambda v: len(v.link_edges) == 0,
            "n_pole": lambda v: len(v.link_edges) == 3,
            "e_pole": lambda v: len(v.link_edges) == 5,
            "high_pole": lambda v: len(v.link_edges) >= 6,
            "non_manifold": lambda v: not v.is_manifold,
        }
        return conditions.get(feature_type, lambda _: False)(vert)

    def _analyze_edge_feature(self, bm, matrix_world, feature_type):
        """Analyze a specific edge feature"""
        for edge in bm.edges:
            if self._check_edge_condition(edge, feature_type):
                pos = [matrix_world @ v.co for v in edge.verts]
                normal = [matrix_world.to_3x3() @ v.normal for v in edge.verts]
                self.edge_data[feature_type][0].extend(pos)
                self.edge_data[feature_type][1].extend(normal)

    def _check_edge_condition(self, edge, feature_type):
        conditions = {
            "non_manifold": lambda e: not e.is_manifold,
            "sharp": lambda e: not e.smooth,
            "seam": lambda e: e.seam,
            "boundary": lambda e: e.is_boundary,
        }
        return conditions.get(feature_type, lambda _: False)(edge)

    def _analyze_face_feature(self, bm, matrix_world, feature_type):
        """Analyze a specific face feature"""
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

        for face in bm.faces:
            if self._check_face_condition(face, feature_type, props):
                verts = [matrix_world @ v.co for v in face.verts]
                normals = [matrix_world.to_3x3() @ v.normal for v in face.verts]

                # Handle triangulation for different face types
                if len(face.verts) == 3:
                    self.face_data[feature_type][0].extend(verts)
                    self.face_data[feature_type][1].extend(normals)
                else:
                    # Fan triangulation for quads, ngons, and non-planar faces
                    for i in range(1, len(verts) - 1):
                        self.face_data[feature_type][0].extend(
                            [verts[0], verts[i], verts[i + 1]]
                        )
                        self.face_data[feature_type][1].extend(
                            [normals[0], normals[i], normals[i + 1]]
                        )

    def _check_face_condition(self, face, feature_type, props):
        conditions = {
            "tri": lambda f, _: len(f.verts) == 3,
            "quad": lambda f, _: len(f.verts) == 4,
            "ngon": lambda f, _: len(f.verts) > 4,
            "non_planar": lambda f, p: len(f.verts) > 3
            and not self.is_face_planar(f, p.non_planar_threshold),
        }
        return conditions.get(feature_type, lambda f, _: False)(face, props)
