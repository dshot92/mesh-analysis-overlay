# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

from typing import Optional

import bmesh
import bpy
import math
from bpy.types import Object

debug_print = True


class MeshAnalyzer:
    def __init__(self, obj: Object):
        if not obj or obj.type != "MESH":
            raise ValueError("Invalid mesh object")

        self.active_object = obj
        self.analyzed_features = set()
        self.cache = MeshAnalyzerCache.get_instance()
        self.clear_data()
        self.update(obj)

    def clear_data(self):
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

    def update(self, obj):
        """Update analysis based on enabled toggles"""
        if obj != self.active_object:
            return

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

        # Get current toggle states
        current_states = {}
        for data_type, toggles in [
            (self.vertex_data, "vertices"),
            (self.edge_data, "edges"),
            (self.face_data, "faces"),
        ]:
            for feature in data_type.keys():
                toggle_name = f"show_{feature}_{toggles}"
                current_states[feature] = getattr(props, toggle_name, False)

        # Handle toggle changes
        for feature, is_enabled in current_states.items():
            if is_enabled and feature not in self.analyzed_features:
                self.analyze_specific_feature(obj, feature)
            elif not is_enabled and feature in self.analyzed_features:
                self.clear_feature_data(feature)

    def clear_feature_data(self, feature):
        """Clear data for a specific feature"""
        for data_dict in [self.vertex_data, self.edge_data, self.face_data]:
            if feature in data_dict:
                data_dict[feature] = ([], [])
        self.analyzed_features.discard(feature)

    def analyze_specific_feature(self, obj, feature):
        """Analyze a specific feature and cache results"""
        if not obj or obj.type != "MESH":
            return

        # Try to get cached data first
        cached_data = self.cache.get_feature_data(obj.name, feature)
        if cached_data:
            if debug_print:
                print(f"🟢 Cache HIT for {feature}")
            self._store_cached_data(feature, cached_data)
            self.analyzed_features.add(feature)
            return

        if debug_print:
            print(f"🔴 Cache MISS for {feature}")
        # Analyze if not cached
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        try:
            self._analyze_feature(bm, obj.matrix_world, feature)
            # Cache the new results
            self._cache_feature_data(obj.name, feature)
            self.analyzed_features.add(feature)
        finally:
            bm.free()

    def _store_cached_data(self, feature, data):
        """Store cached data in appropriate data structure"""
        if feature in self.vertex_data:
            self.vertex_data[feature] = data
        elif feature in self.edge_data:
            self.edge_data[feature] = data
        elif feature in self.face_data:
            self.face_data[feature] = data

    def _cache_feature_data(self, obj_name, feature):
        """Cache feature data"""
        data = None
        if feature in self.vertex_data:
            data = self.vertex_data[feature]
        elif feature in self.edge_data:
            data = self.edge_data[feature]
        elif feature in self.face_data:
            data = self.face_data[feature]

        if data:
            self.cache.add_feature_data(obj_name, feature, data)

    def _analyze_feature(self, bm, matrix_world, feature):
        """Unified analysis method"""
        if feature in self.vertex_data:
            self._analyze_vertex_feature(bm, matrix_world, feature)
        elif feature in self.edge_data:
            self._analyze_edge_feature(bm, matrix_world, feature)
        elif feature in self.face_data:
            self._analyze_face_feature(bm, matrix_world, feature)

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


class MeshAnalyzerCache:
    _instance = None

    def __init__(self):
        if self._instance is not None:
            raise Exception("This class is a singleton!")
        self.cache = {}  # {obj_name: {feature: data}}
        self.max_cache_size = 4
        self.access_history = []  # Track LRU

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _update_access_history(self, obj_name, feature):
        """Update LRU tracking"""
        key = (obj_name, feature)
        if key in self.access_history:
            self.access_history.remove(key)
        self.access_history.append(key)

    def _ensure_cache_size(self):
        """Maintain cache size limit using LRU"""
        while len(self.cache) > self.max_cache_size:
            oldest = self.access_history.pop(0)
            obj_name, feature = oldest
            if obj_name in self.cache:
                if feature in self.cache[obj_name]:
                    del self.cache[obj_name][feature]
                if not self.cache[obj_name]:
                    del self.cache[obj_name]

    def get_feature_data(self, obj_name: str, feature: str):
        """Get cached feature data"""
        if obj_name in self.cache and feature in self.cache[obj_name]:
            self._update_access_history(obj_name, feature)
            return self.cache[obj_name][feature]
        return None

    def add_feature_data(self, obj_name: str, feature: str, data: tuple):
        """Add feature data to cache"""
        if obj_name not in self.cache:
            self.cache[obj_name] = {}
        self.cache[obj_name][feature] = data
        self._update_access_history(obj_name, feature)
        self._ensure_cache_size()

    def clear(self):
        """Clear all cached data"""
        self.cache.clear()
        self.access_history.clear()
