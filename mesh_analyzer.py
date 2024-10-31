# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh
import logging
import math

from typing import List, Optional
from bpy.types import Object

from .feature_data import FEATURE_DATA

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class MeshAnalyzerCache:
    def __init__(self, max_size=2):
        self.max_size = max_size
        self._analyzers = {}  # {obj_name: (analyzer, feature_results)}
        self._access_order = []  # LRU queue

        # Feature type definitions from feature_data
        self.vertex_features = {feature["id"] for feature in FEATURE_DATA["vertices"]}
        self.edge_features = {feature["id"] for feature in FEATURE_DATA["edges"]}
        self.face_features = {feature["id"] for feature in FEATURE_DATA["faces"]}

    def get(self, obj_name: str) -> tuple[Optional["MeshAnalyzer"], dict]:
        """Get analyzer and its results from cache"""
        if obj_name in self._analyzers:
            # Move to most recently used
            self._access_order.remove(obj_name)
            self._access_order.append(obj_name)
            return self._analyzers[obj_name]
        return None, {}

    def put(self, obj_name: str, analyzer: "MeshAnalyzer", feature_results: dict):
        """Add or update cache entry"""
        if obj_name in self._analyzers:
            self._access_order.remove(obj_name)
        elif len(self._analyzers) >= self.max_size:
            # Evict least recently used
            lru_name = self._access_order.pop(0)
            del self._analyzers[lru_name]
            logger.debug(f"Evicting analyzer for: {lru_name}")

        self._analyzers[obj_name] = (analyzer, feature_results)
        self._access_order.append(obj_name)
        logger.debug(f"\nCache state: {self._access_order}")

    def clear(self):
        """Clear all cache entries"""
        self._analyzers.clear()
        self._access_order.clear()


class MeshAnalyzer:
    _cache = MeshAnalyzerCache(max_size=10)

    def __init__(self, obj: Object):
        # logger.debug(f"\n=== Creating MeshAnalyzer for {obj.name} ===")
        if not obj or obj.type != "MESH":
            raise ValueError("Invalid mesh object")
        self.obj = obj
        self.scene_props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        self.analyzed_features = {}

    @classmethod
    def get_analyzer(cls, obj: Object) -> "MeshAnalyzer":
        analyzer, features = cls._cache.get(obj.name)
        if analyzer:
            # logger.debug(f"Cache hit for {obj.name}")
            analyzer.analyzed_features = features
            return analyzer

        analyzer = cls(obj)
        cls._cache.put(obj.name, analyzer, {})
        return analyzer

    def analyze_feature(self, feature: str) -> List:
        try:
            if feature in self.analyzed_features:
                logger.debug(f"Feature cache hit: {feature}")
                return self.analyzed_features[feature]

            logger.debug(f"Feature cache miss: {feature}")
            indices = self._analyze_feature_impl(feature)
            self.analyzed_features[feature] = indices
            # Update cache with new feature results
            self._cache.put(self.obj.name, self, self.analyzed_features)
            return indices
        except ReferenceError:
            # Object reference became invalid (e.g. during undo)
            logger.debug("Object reference invalid - clearing cache")
            self._cache.clear()
            return []

    def _analyze_feature_impl(self, feature: str) -> List:
        bm = bmesh.new()
        bm.from_mesh(self.obj.data)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        indices = []

        if feature in self._cache.vertex_features:
            self._analyze_vertex_feature(bm, feature, indices)
        elif feature in self._cache.edge_features:
            self._analyze_edge_feature(bm, feature, indices)
        elif feature in self._cache.face_features:
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
        # ref_edge = (face.verts[1].co - face.verts[0].co).normalized()

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

        # # Check all consecutive vertices for collinearity
        # for i in range(len(verts)):
        #     v1 = verts[i].co
        #     v2 = verts[(i + 1) % len(verts)].co
        #     v3 = verts[(i + 2) % len(verts)].co

        #     # Get vectors between consecutive vertices
        #     edge1 = (v2 - v1).normalized()
        #     edge2 = (v3 - v2).normalized()

        #     # Check if vectors are parallel (collinear)
        #     cross_prod = edge1.cross(edge2)
        #     if cross_prod.length < 1e-8:
        #         return True

        return False

    @classmethod
    def invalidate_cache(cls, obj_name: str, features: Optional[List[str]] = None):
        """Invalidate cache for specific object and features"""
        # Get analyzer from cache
        analyzer, _ = cls._cache.get(obj_name)
        if analyzer:
            if features:
                # Clear only specified features
                for feature in features:
                    if feature in analyzer.analyzed_features:
                        del analyzer.analyzed_features[feature]
            else:
                # Clear all features
                analyzer.analyzed_features.clear()

            # Update cache
            cls._cache.put(obj_name, analyzer, analyzer.analyzed_features)

    def get_feature_type(self, feature: str) -> str:
        """Return the type of feature: 'VERT', 'EDGE', or 'FACE'"""
        if feature in self._cache.vertex_features:
            return "VERT"
        elif feature in self._cache.edge_features:
            return "EDGE"
        elif feature in self._cache.face_features:
            return "FACE"
        raise ValueError(f"Unknown feature type: {feature}")
