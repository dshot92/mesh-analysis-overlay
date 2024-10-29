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

        self.is_dirty = False
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
            "non_manifold_v": ([], []),
        }
        self.edge_data = {
            "non_manifold_e": ([], []),
            "sharp": ([], []),
            "seam": ([], []),
            "boundary": ([], []),
        }

    def _is_edit_mode_dirty(self, obj: Object) -> bool:
        depsgraph = bpy.context.evaluated_depsgraph_get()

        # Check if in edit mode and mesh data has been modified
        if obj.mode == "EDIT" and obj.is_updated_data:
            return True

        # Check if mesh data has been updated in the depsgraph
        return obj.data.is_editmode or obj.data in {
            update.id.original for update in depsgraph.updates
        }

    def update(self, obj):
        """Update analysis based on enabled toggles"""
        if obj != self.active_object:
            return

        # Check if object is dirty
        is_currently_dirty = self._is_edit_mode_dirty(obj)

        # If state changed from clean to dirty, clear cache
        if not self.is_dirty and is_currently_dirty:
            self.cache.clear()

        self.is_dirty = is_currently_dirty
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

        # Handle toggle changes - force reanalysis when dirty
        for feature, is_enabled in current_states.items():
            if is_enabled and (feature not in self.analyzed_features or self.is_dirty):
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

        if cached_data and not self.is_dirty:
            if debug_print:
                print(f"🟢 Using cached data for {feature} in {obj.name}")
            self._store_cached_data(feature, cached_data)
            self.analyzed_features.add(feature)
            return

        if debug_print:
            print(f"🔴 Analyzing {feature} in {obj.name}")

        # Analyze if not cached or dirty
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        self._analyze_feature(bm, obj.matrix_world, feature)
        # Cache the new results
        self._cache_feature_data(obj.name, feature)
        self.analyzed_features.add(feature)
        self.is_dirty = False  # Reset dirty flag after reanalyzing
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
            bm.verts.ensure_lookup_table()
            self._analyze_vertex_feature(bm, matrix_world, feature)
        elif feature in self.edge_data:
            bm.edges.ensure_lookup_table()
            self._analyze_edge_feature(bm, matrix_world, feature)
        elif feature in self.face_data:
            bm.faces.ensure_lookup_table()
            self._analyze_face_feature(bm, matrix_world, feature)

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
        # bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

        for v in bm.verts:
            world_pos = matrix_world @ v.co
            edge_count = len(v.link_edges)
            normal = matrix_world.to_3x3() @ v.normal

            if feature_type == "single" and edge_count == 0:
                self.vertex_data["single"][0].append(world_pos)
                self.vertex_data["single"][1].append(normal)
            elif feature_type == "n_pole" and edge_count == 3:
                self.vertex_data["n_pole"][0].append(world_pos)
                self.vertex_data["n_pole"][1].append(normal)
            elif feature_type == "e_pole" and edge_count == 5:
                self.vertex_data["e_pole"][0].append(world_pos)
                self.vertex_data["e_pole"][1].append(normal)
            elif feature_type == "high_pole" and edge_count >= 6:
                self.vertex_data["high_pole"][0].append(world_pos)
                self.vertex_data["high_pole"][1].append(normal)
            elif feature_type == "non_manifold_v" and (not v.is_manifold):
                self.vertex_data["non_manifold_v"][0].append(world_pos)
                self.vertex_data["non_manifold_v"][1].append(normal)

    def _analyze_edge_feature(self, bm, matrix_world, feature_type):
        """Analyze a specific edge feature"""
        if debug_print:
            print(f"Feature type requested: {feature_type}")
            print(f"Edge count: {len(bm.edges)}")

        # Get all property names for debugging
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        if debug_print:
            print(
                "Available properties:",
                [p for p in dir(props) if p.startswith("show_")],
            )

        for edge in bm.edges:
            v1 = matrix_world @ edge.verts[0].co
            v2 = matrix_world @ edge.verts[1].co
            n1 = matrix_world.to_3x3() @ edge.verts[0].normal
            n2 = matrix_world.to_3x3() @ edge.verts[1].normal

            if feature_type == "sharp" and not edge.smooth:
                self.edge_data["sharp"][0].extend([v1, v2])
                self.edge_data["sharp"][1].extend([n1, n2])
            if feature_type == "seam" and edge.seam:
                self.edge_data["seam"][0].extend([v1, v2])
                self.edge_data["seam"][1].extend([n1, n2])
            if feature_type == "boundary" and edge.is_boundary:
                self.edge_data["boundary"][0].extend([v1, v2])
                self.edge_data["boundary"][1].extend([n1, n2])
            if feature_type == "non_manifold_e" and (not edge.is_manifold):
                print("non manifold edge")
                self.edge_data["non_manifold_e"][0].extend([v1, v2])
                self.edge_data["non_manifold_e"][1].extend([n1, n2])

    def _analyze_face_feature(self, bm, matrix_world, feature_type):
        """Analyze a specific face feature"""
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

        for face in bm.faces:
            verts = [matrix_world @ v.co for v in face.verts]
            normals = [matrix_world.to_3x3() @ v.normal for v in face.verts]
            vert_count = len(face.verts)

            if feature_type == "tri" and vert_count == 3:
                self.face_data["tri"][0].extend(verts)
                self.face_data["tri"][1].extend(normals)
            elif feature_type == "quad" and vert_count == 4:
                # Fan triangulation for quads
                self.face_data["quad"][0].extend(
                    [verts[0], verts[1], verts[2], verts[0], verts[2], verts[3]]
                )
                self.face_data["quad"][1].extend(
                    [
                        normals[0],
                        normals[1],
                        normals[2],
                        normals[0],
                        normals[2],
                        normals[3],
                    ]
                )
            elif feature_type == "ngon" and vert_count > 4:
                # Fan triangulation for ngons
                for i in range(1, vert_count - 1):
                    self.face_data["ngon"][0].extend([verts[0], verts[i], verts[i + 1]])
                    self.face_data["ngon"][1].extend(
                        [normals[0], normals[i], normals[i + 1]]
                    )
            elif feature_type == "non_planar" and vert_count > 3:
                if not self.is_face_planar(face, props.non_planar_threshold):
                    # Fan triangulation for non-planar faces
                    for i in range(1, vert_count - 1):
                        self.face_data["non_planar"][0].extend(
                            [verts[0], verts[i], verts[i + 1]]
                        )
                        self.face_data["non_planar"][1].extend(
                            [normals[0], normals[i], normals[i + 1]]
                        )


class MeshAnalyzerCache:
    _instance = None

    def __init__(self):
        if self._instance is not None:
            raise Exception("This class is a singleton!")
        self.cache = {}  # {obj_name: {feature: data}}
        self.max_cache_size = 10
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
