# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Dict, Tuple, Set, Optional, List
import bmesh
import bpy
import math
from bpy.types import Object
from mathutils import Matrix
from bpy.app.handlers import persistent


def get_debug_print() -> bool:
    """Get debug print setting from addon preferences"""
    return bpy.context.preferences.addons[__package__].preferences.debug_print


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

        needs_full_update = self._check_if_full_update_needed(obj, cached_state)
        features_to_update = self._determine_features_to_update(
            needs_full_update, cached_state, current_toggle_state
        )

        if features_to_update:
            bm = bmesh.new()
            bm.from_mesh(obj.data)

            if get_debug_print():
                print("")

            # Check cache for features
            uncached_features = set()
            for f in features_to_update:
                cached_data = self.cache.get_feature_data(obj.name, f)
                if (cached_data is not None) and not self.is_dirty:
                    if get_debug_print():
                        print(
                            f"Cache HIT for {obj.name} - {f} (Feature data length: pos:{len(cached_data[0])}, norm:{len(cached_data[1])})"
                        )
                    self._store_cached_data(f, cached_data)
                    self.analyzed_features.add(f)
                else:
                    if get_debug_print():
                        print(f"Cache MISS for {obj.name} - {f}")
                    uncached_features.add(f)

            # Analyze uncached features
            if uncached_features:
                # if get_debug_print():
                #     print(f"Analyzing features: {uncached_features}")
                self._analyze_all_features(bm, obj.matrix_world, uncached_features)

                # Cache results
                for f in uncached_features:
                    self._cache_feature_data(obj.name, f)
                    self.analyzed_features.add(f)

            bm.free()

        self._update_cache_state(obj, current_toggle_state)

    def _check_if_full_update_needed(
        self, obj: Object, cached_state: Optional[Dict]
    ) -> bool:
        """Simplified update check since cache invalidation is handled by handlers"""
        if not cached_state:
            return True
        return False

    def _determine_features_to_update(
        self,
        needs_full_update: bool,
        cached_state: Optional[Dict],
        current_toggle_state: Dict[str, bool],
    ) -> Set[str]:
        """Determine which features need to be updated"""
        if needs_full_update:
            # if get_debug_print():
            #     print(f"Full update needed - updating all enabled features")
            return {f for f, enabled in current_toggle_state.items() if enabled}

        if not cached_state:
            return {f for f, enabled in current_toggle_state.items() if enabled}

        # Get only features that have actually changed state
        changed_features = set()
        cached_toggles = cached_state["toggle_state"]

        for feature, is_enabled in current_toggle_state.items():
            was_enabled = cached_toggles.get(feature, False)
            cached_data = self.cache.get_feature_data(self.active_object.name, feature)

            is_newly_enabled = is_enabled and not was_enabled
            is_not_analyzed = feature not in self.analyzed_features
            has_valid_cache = cached_data is None or (
                cached_data and len(cached_data[0]) > 0
            )

            if is_enabled and (is_newly_enabled or is_not_analyzed) and has_valid_cache:
                changed_features.add(feature)

        # if changed_features and get_debug_print():
        #     print(f"Changed features: {changed_features}")

        return changed_features

    def _get_changed_features(
        self, cached_toggles: Dict[str, bool], current_toggle_state: Dict[str, bool]
    ) -> Set[str]:
        """Identify which features have changed state"""
        features_to_update = set()
        for feature, is_enabled in current_toggle_state.items():
            was_enabled = cached_toggles.get(feature, False)
            if is_enabled and (
                not was_enabled or feature not in self.analyzed_features
            ):
                if get_debug_print():
                    print(f"Toggle changed for feature: {feature}")
                features_to_update.add(feature)
        return features_to_update

    def _process_features(self, obj: Object, features_to_update: Set[str]) -> None:
        """Process all features that need updating"""
        if get_debug_print():
            print(f"Features to update: {features_to_update}")
        for feature in features_to_update:
            self.analyze_specific_feature(obj, feature)

    def _update_cache_state(
        self, obj: Object, current_toggle_state: Dict[str, bool]
    ) -> None:
        """Update the cache with current object state"""
        self.cache.update_object_state(
            obj.name,
            obj.matrix_world.copy(),
            obj.mode,
            current_toggle_state,
        )

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

    def _analyze_all_features(
        self, bm: bmesh.types.BMesh, matrix_world: Matrix, features: Set[str]
    ) -> None:
        """Analyze all needed features in a single pass"""
        # Determine which types of elements we need to process
        need_verts = any(f in self.vertex_data for f in features)
        need_edges = any(f in self.edge_data for f in features)
        need_faces = any(f in self.face_data for f in features)

        if get_debug_print():
            print("analaysing")

        # Process vertices if needed
        if need_verts:
            bm.verts.ensure_lookup_table()
            for v in bm.verts:
                world_pos = matrix_world @ v.co
                edge_count = len(v.link_edges)
                normal = matrix_world.to_3x3() @ v.normal

                if "single" in features and edge_count == 0:
                    self.vertex_data["single"][0].append(world_pos)
                    self.vertex_data["single"][1].append(normal)
                if "n_pole" in features and edge_count == 3:
                    self.vertex_data["n_pole"][0].append(world_pos)
                    self.vertex_data["n_pole"][1].append(normal)
                if "e_pole" in features and edge_count == 5:
                    self.vertex_data["e_pole"][0].append(world_pos)
                    self.vertex_data["e_pole"][1].append(normal)
                if "high_pole" in features and edge_count >= 6:
                    self.vertex_data["high_pole"][0].append(world_pos)
                    self.vertex_data["high_pole"][1].append(normal)
                if "non_manifold_v" in features and not v.is_manifold:
                    self.vertex_data["non_manifold_v"][0].append(world_pos)
                    self.vertex_data["non_manifold_v"][1].append(normal)

        # Process edges if needed
        if need_edges:
            bm.edges.ensure_lookup_table()
            for edge in bm.edges:
                v1 = matrix_world @ edge.verts[0].co
                v2 = matrix_world @ edge.verts[1].co
                n1 = matrix_world.to_3x3() @ edge.verts[0].normal
                n2 = matrix_world.to_3x3() @ edge.verts[1].normal

                if "sharp" in features and not edge.smooth:
                    self.edge_data["sharp"][0].extend([v1, v2])
                    self.edge_data["sharp"][1].extend([n1, n2])
                if "seam" in features and edge.seam:
                    self.edge_data["seam"][0].extend([v1, v2])
                    self.edge_data["seam"][1].extend([n1, n2])
                if "boundary" in features and edge.is_boundary:
                    self.edge_data["boundary"][0].extend([v1, v2])
                    self.edge_data["boundary"][1].extend([n1, n2])
                if "non_manifold_e" in features and not edge.is_manifold:
                    self.edge_data["non_manifold_e"][0].extend([v1, v2])
                    self.edge_data["non_manifold_e"][1].extend([n1, n2])

        # Process faces if needed
        if need_faces:
            bm.faces.ensure_lookup_table()
            for face in bm.faces:
                verts = [matrix_world @ v.co for v in face.verts]
                normals = [matrix_world.to_3x3() @ v.normal for v in face.verts]
                vert_count = len(face.verts)

                if vert_count == 3:
                    if "tri" in features:
                        self.face_data["tri"][0].extend(verts)
                        self.face_data["tri"][1].extend(normals)
                if vert_count == 4:
                    if "quad" in features:
                        for i in range(1, vert_count - 1):
                            self.face_data["quad"][0].extend(
                                [verts[0], verts[i], verts[i + 1]]
                            )
                            self.face_data["quad"][1].extend(
                                [normals[0], normals[i], normals[i + 1]]
                            )
                if vert_count > 4:
                    if "ngon" in features:
                        for i in range(1, vert_count - 1):
                            self.face_data["ngon"][0].extend(
                                [verts[0], verts[i], verts[i + 1]]
                            )
                            self.face_data["ngon"][1].extend(
                                [normals[0], normals[i], normals[i + 1]]
                            )
                if vert_count > 3:
                    if "non_planar" in features and not self.is_face_planar(
                        face, self.scene_props.non_planar_threshold
                    ):
                        for i in range(1, vert_count - 1):
                            self.face_data["non_planar"][0].extend(
                                [verts[0], verts[i], verts[i + 1]]
                            )
                            self.face_data["non_planar"][1].extend(
                                [normals[0], normals[i], normals[i + 1]]
                            )


class MeshAnalyzerCache:
    _instance = None
    _handlers_registered = False

    @staticmethod
    def register():
        """Register all handlers and RNA subscribers"""
        if not MeshAnalyzerCache._handlers_registered:
            # Convert method to function for message bus
            def mode_change_handler(*args):
                obj = bpy.context.active_object
                if obj and obj.type == "MESH":
                    MeshAnalyzerCache.get_instance().invalidate_cache(obj.name)

            bpy.app.handlers.depsgraph_update_post.append(
                MeshAnalyzerCache._handle_depsgraph_update
            )
            bpy.msgbus.subscribe_rna(
                key=(bpy.types.Object, "mode"),
                owner=object(),
                args=(),
                notify=mode_change_handler,
            )
            MeshAnalyzerCache._handlers_registered = True

    @staticmethod
    def unregister():
        """Unregister all handlers and RNA subscribers"""
        if MeshAnalyzerCache._handlers_registered:
            if (
                MeshAnalyzerCache._handle_depsgraph_update
                in bpy.app.handlers.depsgraph_update_post
            ):
                bpy.app.handlers.depsgraph_update_post.remove(
                    MeshAnalyzerCache._handle_depsgraph_update
                )
            bpy.msgbus.clear_by_owner(object())  # Clear all message bus subscriptions
            MeshAnalyzerCache._handlers_registered = False
            # Clear instance and cache
            if MeshAnalyzerCache._instance:
                MeshAnalyzerCache._instance.clear()
                MeshAnalyzerCache._instance = None

    def __init__(self):
        if self._instance is not None:
            raise Exception("This class is a singleton!")
        self.feature_cache = {}
        self.state_cache = {}
        self.max_cache_size = 10
        self.access_history = []

    @staticmethod
    @persistent
    def _handle_depsgraph_update(scene, depsgraph):
        """Handle object transformations and mesh modifications"""
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for update in depsgraph.updates:
            # Only process mesh objects
            if isinstance(update.id, bpy.types.Object) and update.id.type == "MESH":
                obj = update.id
                # Invalidate cache if object is transformed or geometry is modified
                if update.is_updated_transform or update.is_updated_geometry:
                    if get_debug_print():
                        print(
                            f"Invalidating cache for {obj.name} due to {'transform' if update.is_updated_transform else 'geometry'} update"
                        )
                    MeshAnalyzerCache.get_instance().invalidate_cache(obj.name)

    def invalidate_cache(self, obj_name: str) -> None:
        """Invalidate cache for specific object"""
        if obj_name in self.feature_cache:
            del self.feature_cache[obj_name]
        if obj_name in self.state_cache:
            del self.state_cache[obj_name]
        self.access_history = [(o, f) for o, f in self.access_history if o != obj_name]

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


def matrix_equivalent(m1: Matrix, m2: Matrix) -> bool:
    """Compare matrices for equality"""
    if m1 is None or m2 is None:
        return m1 is m2
    return m1 == m2
