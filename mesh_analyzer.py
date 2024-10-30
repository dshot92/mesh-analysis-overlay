# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh
import logging
import math

from typing import Tuple, List
from bpy.types import Object


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class MeshCache:
    def __init__(self):
        self.feature_cache = (
            {}
        )  # Format: {obj_name: {'is_valid': bool, 'features': {feature: {'indices': []}}}}

    def get(self, obj_name: str, feature: str) -> Tuple[bool, List]:
        """Get cached feature indices for an object"""
        obj_cache = self.feature_cache.get(obj_name)
        if not obj_cache or not obj_cache.get("is_valid", False):
            return (False, [])

        feature_data = obj_cache["features"].get(feature)
        if not feature_data:
            return (False, [])

        return (True, feature_data["indices"])

    def set(self, obj_name: str, feature: str, indices: List):
        """Cache feature indices for an object"""
        if obj_name not in self.feature_cache:
            self.feature_cache[obj_name] = {
                "is_valid": True,
                "features": {},
            }

        self.feature_cache[obj_name]["features"][feature] = {
            "indices": indices,
        }

    def clear(self):
        """Clear all cached data"""
        self.feature_cache.clear()

    def invalidate(self, obj_name: str = None, feature: str = None):
        """Invalidate cache for specific object or all objects"""
        if obj_name:
            if obj_name in self.feature_cache:
                if feature:
                    self.feature_cache[obj_name]["features"][feature] = {
                        "is_valid": False,
                        "indices": [],
                    }
                else:
                    self.feature_cache[obj_name][
                        "is_valid"
                    ] = False  # Set invalid instead of removing
        else:
            self.feature_cache.clear()


class MeshAnalyzer:
    _cache = MeshCache()
    _analyzer_cache = []
    _analyzer_cache_size = 5

    vertex_features = {
        "single_vertices",
        "non_manifold_v_vertices",
        "n_pole_vertices",
        "e_pole_vertices",
        "high_pole_vertices",
    }

    edge_features = {
        "non_manifold_e_edges",
        "sharp_edges",
        "seam_edges",
        "boundary_edges",
    }

    face_features = {
        "tri_faces",
        "quad_faces",
        "ngon_faces",
        "non_planar_faces",
        "degenerate_faces",
    }

    def __init__(self, obj: Object):
        logger.debug(f"\n=== Creating MeshAnalyzer for {obj.name} ===")
        if not obj or obj.type != "MESH":
            raise ValueError("Invalid mesh object")

        self.obj = obj
        self.scene_props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        self.analyzed_features = {}

    @classmethod
    def get_analyzer(cls, obj: Object) -> "MeshAnalyzer":
        # Check if object already has an analyzer in cache
        for analyzer in cls._analyzer_cache:
            if analyzer.obj == obj:
                return analyzer

        # Create new analyzer
        analyzer = cls(obj)
        logger.debug(f"\nCreating new analyzer for {obj.name}\n")

        # Add to cache, removing oldest if at capacity
        if len(cls._analyzer_cache) >= cls._analyzer_cache_size:
            cls._analyzer_cache.pop(0)
        cls._analyzer_cache.append(analyzer)
        return analyzer

    @classmethod
    def clear_analyzer_cache(cls):
        cls._analyzer_cache.clear()

    def analyze_feature(self, feature: str) -> List:
        # Add feature tracking to avoid redundant cache checks
        if feature in self.analyzed_features:
            return self.analyzed_features[feature]

        # Get cached result if available
        cached = self._cache.get(self.obj.name, feature)
        if cached[0]:
            logger.debug(f"Cache hit: {self.obj.name} - {feature}")
            self.analyzed_features[feature] = cached[1]
            return cached[1]

        logger.debug(f"Cache miss: {self.obj.name} - {feature}")
        # Analyze and cache the result
        indices = self._analyze_feature_impl(feature)
        self._cache.set(self.obj.name, feature, indices)
        self.analyzed_features[feature] = indices
        return indices

    def _analyze_feature_impl(self, feature: str) -> List:
        bm = bmesh.new()
        bm.from_mesh(self.obj.data)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        indices = []

        if feature in self.vertex_features:
            self._analyze_vertex_feature(bm, feature, indices)
        elif feature in self.edge_features:
            self._analyze_edge_feature(bm, feature, indices)
        elif feature in self.face_features:
            self._analyze_face_feature(bm, feature, indices)

        bm.free()
        return indices

    def _analyze_vertex_feature(
        self, bm: bmesh.types.BMesh, feature: str, indices: List
    ):
        for v in bm.verts:
            if feature == "single_vertices" and len(v.link_edges) == 0:
                indices.append(v.index)
            elif feature == "non_manifold_v_vertices" and not v.is_manifold:
                indices.append(v.index)
            elif feature == "n_pole_vertices" and len(v.link_edges) == 3:
                indices.append(v.index)
            elif feature == "e_pole_vertices" and len(v.link_edges) == 5:
                indices.append(v.index)
            elif feature == "high_pole_vertices" and len(v.link_edges) >= 6:
                indices.append(v.index)

    def _analyze_edge_feature(self, bm: bmesh.types.BMesh, feature: str, indices: List):
        for e in bm.edges:
            if feature == "non_manifold_e_edges" and not e.is_manifold:
                indices.append(e.index)  # Changed from extend to append
            elif feature == "sharp_edges" and e.smooth is False:
                indices.append(e.index)  # Changed from extend to append
            elif feature == "seam_edges" and e.seam:
                indices.append(e.index)  # Changed from extend to append
            elif feature == "boundary_edges" and e.is_boundary:
                indices.append(e.index)  # Changed from extend to append

    def _analyze_face_feature(self, bm: bmesh.types.BMesh, feature: str, indices: List):
        for f in bm.faces:
            if feature == "tri_faces" and len(f.verts) == 3:
                indices.append(f.index)
            elif feature == "quad_faces" and len(f.verts) == 4:
                indices.append(f.index)
            elif feature == "ngon_faces" and len(f.verts) > 4:
                indices.append(f.index)
            elif feature == "non_planar_faces" and not self._is_planar(f):
                indices.append(f.index)
            elif feature == "degenerate_faces" and self._is_degenerate(f):
                indices.append(f.index)

    def _is_planar(self, face: bmesh.types.BMFace) -> bool:
        if len(face.verts) <= 3:
            return True

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        # Convert degrees to radians for math operations
        threshold_rad = math.radians(props.non_planar_threshold)

        normal = face.normal.normalized()
        center = face.calc_center_median()

        # Get the average edge vector as reference
        ref_edge = (face.verts[1].co - face.verts[0].co).normalized()

        # Check each vertex's plane formed with adjacent vertices
        for v in face.verts:
            # Get vectors to adjacent vertices
            v_pos = v.co - center
            if v_pos.length < 1e-6:  # Skip if vertex is at center
                continue

            # Calculate angle between vertex normal and face normal
            angle = math.acos(min(1.0, max(-1.0, normal.dot(v_pos.normalized()))))
            if abs(angle - math.pi / 2) > threshold_rad:
                return False

        return True

    def _is_degenerate(self, face: bmesh.types.BMFace) -> bool:
        # Check for zero area
        if face.calc_area() < 1e-8:
            return True

        # Check for invalid vertex count
        verts = face.verts
        if len(verts) < 3:
            return True

        # Check for duplicate vertices
        unique_verts = set(vert.co.to_tuple() for vert in verts)
        if len(unique_verts) < len(verts):
            return True

        # TODO
        # Disabled check, as a planar ngon of non zero area is not degenerate

        # Check all consecutive vertices for collinearity
        # for i in range(len(verts)):
        #     v1 = verts[i].co
        #     v2 = verts[(i + 1) % len(verts)].co
        #     v3 = verts[(i + 2) % len(verts)].co

        #     # Get vectors between consecutive vertices
        #     edge1 = (v2 - v1).normalized()
        #     edge2 = (v3 - v2).normalized()

        #     Check if vectors are parallel (collinear)
        #     cross_prod = edge1.cross(edge2)
        #     if cross_prod.length < 1e-6:
        #         return True

        return False

    @classmethod
    def invalidate_cache(cls, obj_name: str, features: List[str] = None):
        """
        Invalidate cache for specific object and features
        If features is None, invalidates all features
        """
        # Clear the analyzed_features when invalidating cache
        for analyzer in cls._analyzer_cache:
            if analyzer.obj.name == obj_name:
                analyzer.analyzed_features.clear()
                break

        if features:
            for feature in features:
                cls._cache.invalidate(obj_name, feature)
        else:
            cls._cache.invalidate(obj_name)
