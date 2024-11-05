# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh
import logging
import math
import numpy as np

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
        self.mesh_stats = {"verts": 0, "edges": 0, "faces": 0}  # Add mesh stats

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
        # Create bmesh and ensure lookup tables
        bm = bmesh.new()
        bm.from_mesh(self.obj.data)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        # Store mesh stats
        self.mesh_stats = {
            "verts": len(bm.verts),
            "edges": len(bm.edges),
            "faces": len(bm.faces),
        }

        # Convert to numpy arrays for faster processing
        vert_cos = np.empty((len(bm.verts), 3), "f")
        vert_norms = np.empty((len(bm.verts), 3), "f")

        # Get vertex data
        for i, v in enumerate(bm.verts):
            vert_cos[i] = v.co
            vert_norms[i] = v.normal

        indices = []

        # Use existing feature checks but with optimized data access
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
        # Convert to numpy arrays for faster processing
        link_edges_count = np.array([len(v.link_edges) for v in bm.verts])
        is_manifold = np.array([v.is_manifold for v in bm.verts])

        if feature == "single_vertices":
            indices.extend(np.where(link_edges_count == 0)[0])
        elif feature == "non_manifold_v_vertices":
            indices.extend(np.where(~is_manifold)[0])
        elif feature == "n_pole_vertices":
            indices.extend(np.where(link_edges_count == 3)[0])
        elif feature == "e_pole_vertices":
            indices.extend(np.where(link_edges_count == 5)[0])
        elif feature == "high_pole_vertices":
            indices.extend(np.where(link_edges_count >= 6)[0])

    def _analyze_edge_feature(self, bm: bmesh.types.BMesh, feature: str, indices: List):
        # Convert to numpy arrays for faster processing
        is_manifold = np.array([e.is_manifold for e in bm.edges])
        is_smooth = np.array([e.smooth for e in bm.edges])
        is_seam = np.array([e.seam for e in bm.edges])
        is_boundary = np.array([e.is_boundary for e in bm.edges])

        if feature == "non_manifold_e_edges":
            indices.extend(np.where(~is_manifold)[0])
        elif feature == "sharp_edges":
            indices.extend(np.where(~is_smooth)[0])
        elif feature == "seam_edges":
            indices.extend(np.where(is_seam)[0])
        elif feature == "boundary_edges":
            indices.extend(np.where(is_boundary)[0])

    def _analyze_face_feature(self, bm: bmesh.types.BMesh, feature: str, indices: List):
        # Convert to numpy arrays for faster processing
        vert_counts = np.array([len(f.verts) for f in bm.faces])

        if feature == "tri_faces":
            indices.extend(np.where(vert_counts == 3)[0])
        elif feature == "quad_faces":
            indices.extend(np.where(vert_counts == 4)[0])
        elif feature == "ngon_faces":
            indices.extend(np.where(vert_counts > 4)[0])
        elif feature == "non_planar_faces":
            # This check needs to be done per-face due to geometric calculations
            for f in bm.faces:
                if not self._is_planar(f):
                    indices.append(f.index)
        elif feature == "degenerate_faces":
            # This check needs to be done per-face due to geometric calculations
            for f in bm.faces:
                if self._is_degenerate(f):
                    indices.append(f.index)

    def _is_planar(self, face: bmesh.types.BMFace) -> bool:
        if len(face.verts) <= 3:
            return True

        # Convert vertices to numpy array for faster calculations
        verts = np.array([v.co for v in face.verts])
        normal = np.array(face.normal)
        center = np.mean(verts, axis=0)

        # Calculate vectors from center to vertices
        vectors = verts - center
        vectors /= np.linalg.norm(vectors, axis=1)[:, np.newaxis]

        # Calculate angles with normal
        dots = np.abs(np.dot(vectors, normal))
        angles = np.arccos(np.clip(dots, -1.0, 1.0))

        threshold_rad = math.radians(
            bpy.context.scene.Mesh_Analysis_Overlay_Properties.non_planar_threshold
        )
        return np.all(np.abs(angles - math.pi / 2) <= threshold_rad)

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
