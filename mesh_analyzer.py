# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Dict, Tuple, Set, Optional, List
import bmesh
import bpy
import math
from bpy.types import Object
from mathutils import Matrix

debug_print = False


class MeshAnalyzer:
    def __init__(self, obj: Object):
        if not obj or obj.type != "MESH":
            raise ValueError("Invalid mesh object")

        self.is_dirty = False
        self.active_object = obj
        self.analyzed_features = set()
        self.cache = MeshAnalyzerCache.get_instance()
        self.scene_props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        self.clear_data()
        self.update(obj)

    def clear_data(self) -> None:
        """Initialize/clear all feature data containers"""
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

    def _get_feature_configs(self) -> Dict[str, Tuple[str, str]]:
        """Returns mapping of features to their property names and primitive types"""
        configs = {}
        for prop_name in dir(self.scene_props):
            if not prop_name.startswith("show_"):
                continue

            if prop_name.endswith("_faces"):
                key = prop_name[5:-6]  # Remove 'show_' and '_faces'
                configs[key] = (prop_name, "TRIS")
            elif prop_name.endswith("_edges"):
                key = prop_name[5:-6]
                configs[key] = (prop_name, "LINES")
            elif prop_name.endswith("_vertices"):
                key = prop_name[5:-9]  # Remove 'show_' and '_vertices'
                configs[key] = (prop_name, "POINTS")

        return configs

    def _get_current_toggle_state(self) -> Dict[str, bool]:
        """Get current state of analysis toggles using property reflection"""
        toggle_state = {}
        for feature, (prop_name, _) in self._get_feature_configs().items():
            toggle_state[feature] = getattr(self.scene_props, prop_name)
        return toggle_state

    def update(self, obj: Object) -> None:
        """Update analysis based on cache state and enabled toggles"""
        if obj != self.active_object:
            return

        cached_state = self.cache.get_object_state(obj.name)
        current_toggle_state = self._get_current_toggle_state()

        # Check if mesh data has been modified (edit mode changes)
        mesh_modified = False
        if cached_state and hasattr(obj.data, "is_updated"):
            mesh_modified = obj.data.is_updated

        # Force full update if:
        # 1. Mesh was modified (edit mode changes)
        # 2. Object mode changed
        # 3. Transform changed
        needs_full_update = False
        if cached_state:
            mode_changed = obj.mode != cached_state["mode"]
            matrix_changed = not matrix_equivalent(
                obj.matrix_world, cached_state["matrix"]
            )

            if mesh_modified or mode_changed or matrix_changed:
                needs_full_update = True
                self.is_dirty = True  # Mark analyzer as dirty to force recomputation
                if debug_print:
                    print(
                        f"State changed - Mode: {mode_changed}, Matrix: {matrix_changed}, Mesh modified: {mesh_modified}"
                    )
        else:
            needs_full_update = True
            if debug_print:
                print(f"No cached state found for {obj.name}")

        # Determine which features need updating
        features_to_update: Set[str] = set()
        if needs_full_update:
            if debug_print:
                print("Full update needed - updating all enabled features")
            features_to_update = {
                f for f, enabled in current_toggle_state.items() if enabled
            }
        elif cached_state:
            # Check which toggles changed state
            cached_toggles = cached_state["toggle_state"]
            for feature, is_enabled in current_toggle_state.items():
                was_enabled = cached_toggles.get(feature, False)
                if is_enabled and (
                    not was_enabled or feature not in self.analyzed_features
                ):
                    if debug_print:
                        print(f"Toggle changed for feature: {feature}")
                    features_to_update.add(feature)
        else:
            if debug_print:
                print("No cache - analyzing all enabled features")
            features_to_update = {
                f for f, enabled in current_toggle_state.items() if enabled
            }

        if debug_print:
            print(f"Features to update: {features_to_update}")

        # Update features and cache
        for feature in features_to_update:
            self.analyze_specific_feature(obj, feature)

        # Update cache state after analysis
        self.cache.update_object_state(
            obj.name,
            obj.matrix_world.copy(),
            obj.mode,  # Make sure mode is being stored
            current_toggle_state,
        )

    def analyze_specific_feature(self, obj: Object, feature: str) -> None:
        """Analyze a specific feature, using cache when possible"""
        if not obj or obj.type != "MESH":
            return

        # Only use cache if object hasn't changed state
        cached_data = self.cache.get_feature_data(obj.name, feature)
        if cached_data and not self.is_dirty:
            if debug_print:
                print(f"Cache HIT for {obj.name} - {feature}")
            self._store_cached_data(feature, cached_data)
            self.analyzed_features.add(feature)
            return

        if debug_print:
            print(f"Cache MISS for {obj.name} - {feature}")
        # Analyze and cache the feature
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        self._analyze_feature(bm, obj.matrix_world, feature)
        self._cache_feature_data(obj.name, feature)
        self.analyzed_features.add(feature)
        bm.free()

    def _store_cached_data(self, feature: str, data: Tuple[List, List]) -> None:
        """Store cached data in appropriate data structure"""
        if feature in self.vertex_data:
            self.vertex_data[feature] = data
        elif feature in self.edge_data:
            self.edge_data[feature] = data
        elif feature in self.face_data:
            self.face_data[feature] = data

    def _cache_feature_data(self, obj_name: str, feature: str) -> None:
        """Cache feature data for future use"""
        data = None
        if feature in self.vertex_data:
            data = self.vertex_data[feature]
        elif feature in self.edge_data:
            data = self.edge_data[feature]
        elif feature in self.face_data:
            data = self.face_data[feature]

        if data:
            self.cache.add_feature_data(obj_name, feature, data)

    def is_face_planar(self, face, threshold_degrees: float) -> bool:
        """Check if a face is planar within the given threshold"""
        if len(face.verts) <= 3:
            return True

        v1, v2, v3 = [v.co for v in face.verts[:3]]
        plane_normal = (v2 - v1).cross(v3 - v1).normalized()

        for vert in face.verts[3:]:
            to_vert = (vert.co - v1).normalized()
            angle = abs(90 - math.degrees(math.acos(abs(to_vert.dot(plane_normal)))))
            if angle > threshold_degrees:
                return False
        return True

    def _analyze_feature(
        self, bm: bmesh.types.BMesh, matrix_world: Matrix, feature: str
    ) -> None:
        """Route feature analysis to appropriate handler"""
        if feature in self.vertex_data:
            bm.verts.ensure_lookup_table()
            self._analyze_vertex_feature(bm, matrix_world, feature)
        elif feature in self.edge_data:
            bm.edges.ensure_lookup_table()
            self._analyze_edge_feature(bm, matrix_world, feature)
        elif feature in self.face_data:
            bm.faces.ensure_lookup_table()
            self._analyze_face_feature(bm, matrix_world, feature)

    def _analyze_vertex_feature(
        self, bm: bmesh.types.BMesh, matrix_world: Matrix, feature: str
    ) -> None:
        """Analyze vertex-based features"""
        for v in bm.verts:
            world_pos = matrix_world @ v.co
            edge_count = len(v.link_edges)
            normal = matrix_world.to_3x3() @ v.normal

            if feature == "single" and edge_count == 0:
                self.vertex_data["single"][0].append(world_pos)
                self.vertex_data["single"][1].append(normal)
            elif feature == "n_pole" and edge_count == 3:
                self.vertex_data["n_pole"][0].append(world_pos)
                self.vertex_data["n_pole"][1].append(normal)
            elif feature == "e_pole" and edge_count == 5:
                self.vertex_data["e_pole"][0].append(world_pos)
                self.vertex_data["e_pole"][1].append(normal)
            elif feature == "high_pole" and edge_count >= 6:
                self.vertex_data["high_pole"][0].append(world_pos)
                self.vertex_data["high_pole"][1].append(normal)
            elif feature == "non_manifold_v" and not v.is_manifold:
                self.vertex_data["non_manifold_v"][0].append(world_pos)
                self.vertex_data["non_manifold_v"][1].append(normal)

    def _analyze_edge_feature(
        self, bm: bmesh.types.BMesh, matrix_world: Matrix, feature: str
    ) -> None:
        """Analyze edge-based features"""
        for edge in bm.edges:
            v1 = matrix_world @ edge.verts[0].co
            v2 = matrix_world @ edge.verts[1].co
            n1 = matrix_world.to_3x3() @ edge.verts[0].normal
            n2 = matrix_world.to_3x3() @ edge.verts[1].normal

            if feature == "sharp" and not edge.smooth:
                self.edge_data["sharp"][0].extend([v1, v2])
                self.edge_data["sharp"][1].extend([n1, n2])
            elif feature == "seam" and edge.seam:
                self.edge_data["seam"][0].extend([v1, v2])
                self.edge_data["seam"][1].extend([n1, n2])
            elif feature == "boundary" and edge.is_boundary:
                self.edge_data["boundary"][0].extend([v1, v2])
                self.edge_data["boundary"][1].extend([n1, n2])
            elif feature == "non_manifold_e" and not edge.is_manifold:
                self.edge_data["non_manifold_e"][0].extend([v1, v2])
                self.edge_data["non_manifold_e"][1].extend([n1, n2])

    def _analyze_face_feature(
        self, bm: bmesh.types.BMesh, matrix_world: Matrix, feature: str
    ) -> None:
        """Analyze face-based features"""
        for face in bm.faces:
            verts = [matrix_world @ v.co for v in face.verts]
            normals = [matrix_world.to_3x3() @ v.normal for v in face.verts]
            vert_count = len(face.verts)

            if feature == "tri" and vert_count == 3:
                self.face_data["tri"][0].extend(verts)
                self.face_data["tri"][1].extend(normals)
            elif feature == "quad" and vert_count == 4:
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
            elif feature == "ngon" and vert_count > 4:
                for i in range(1, vert_count - 1):
                    self.face_data["ngon"][0].extend([verts[0], verts[i], verts[i + 1]])
                    self.face_data["ngon"][1].extend(
                        [normals[0], normals[i], normals[i + 1]]
                    )
            elif feature == "non_planar" and vert_count > 3:
                if not self.is_face_planar(face, self.scene_props.non_planar_threshold):
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
        self.feature_cache = {}  # {obj_name: {feature: data}}
        self.state_cache = {}  # {obj_name: {matrix, mode, toggle_state}}
        self.max_cache_size = 10
        self.access_history = []

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _update_access_history(self, obj_name: str, feature: str) -> None:
        """Update LRU tracking"""
        key = (obj_name, feature)
        if key in self.access_history:
            self.access_history.remove(key)
        self.access_history.append(key)

    def _ensure_cache_size(self) -> None:
        """Maintain cache size limit using LRU"""
        while len(self.feature_cache) > self.max_cache_size:
            oldest = self.access_history.pop(0)
            obj_name, feature = oldest
            if obj_name in self.feature_cache:
                if feature in self.feature_cache[obj_name]:
                    del self.feature_cache[obj_name][feature]
                if not self.feature_cache[obj_name]:
                    del self.feature_cache[obj_name]

    def get_feature_data(
        self, obj_name: str, feature: str
    ) -> Optional[Tuple[List, List]]:
        """Get cached feature data"""
        if obj_name in self.feature_cache and feature in self.feature_cache[obj_name]:
            self._update_access_history(obj_name, feature)
            return self.feature_cache[obj_name][feature]
        return None

    def add_feature_data(
        self, obj_name: str, feature: str, data: Tuple[List, List]
    ) -> None:
        """Add feature data to cache"""
        if obj_name not in self.feature_cache:
            self.feature_cache[obj_name] = {}

        # Store deep copies of the data to prevent reference issues
        positions, normals = data
        self.feature_cache[obj_name][feature] = (
            [v.copy() if hasattr(v, "copy") else v for v in positions],
            [n.copy() if hasattr(n, "copy") else n for n in normals],
        )

        self._update_access_history(obj_name, feature)
        self._ensure_cache_size()

    def get_object_state(self, obj_name: str) -> Optional[Dict]:
        """Get cached object state"""
        return self.state_cache.get(obj_name)

    def update_object_state(
        self, obj_name: str, matrix: Matrix, mode: str, toggle_state: Dict[str, bool]
    ) -> None:
        """Update cached object state"""
        self.state_cache[obj_name] = {
            "matrix": matrix.copy(),  # Store a copy of the matrix
            "mode": mode,
            "toggle_state": toggle_state.copy(),  # Store a copy of the toggle state
        }

    def clear(self) -> None:
        """Clear all cached data"""
        self.feature_cache.clear()
        self.state_cache.clear()
        self.access_history.clear()


def matrix_equivalent(m1: Matrix, m2: Matrix, threshold: float = 1e-6) -> bool:
    """Compare matrices with threshold to handle floating point imprecision"""
    if m1 is None or m2 is None:
        return m1 is m2

    # Convert matrices to flat lists for comparison
    m1_list = [item for row in m1 for item in row]
    m2_list = [item for row in m2 for item in row]

    return all(abs(a - b) < threshold for a, b in zip(m1_list, m2_list))
