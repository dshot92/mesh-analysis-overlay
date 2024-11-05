# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh
import math
import gpu
import numpy as np

from typing import List, Optional
from bpy.types import Object

from .feature_data import FEATURE_DATA


class MeshAnalyzer:
    # Define feature sets from feature_data
    vertex_features = {feature["id"] for feature in FEATURE_DATA["vertices"]}
    edge_features = {feature["id"] for feature in FEATURE_DATA["edges"]}
    face_features = {feature["id"] for feature in FEATURE_DATA["faces"]}

    # Class-level cache for analyzers
    _analyzers = {}  # {obj_name: (timestamp, analyzer)}
    _analysis_cache = {}  # {(obj_name, feature): indices}
    _batch_cache = {}  # {(obj_name, feature): batch_data}
    _max_queue_size = 5  # Increased cache size

    def __init__(self, obj: Object):
        if not obj or obj.type != "MESH":
            raise ValueError("Invalid mesh object")
        self.obj = obj
        self.scene_props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        self.mesh_stats = {"verts": 0, "edges": 0, "faces": 0}
        self._shader = gpu.shader.from_builtin("FLAT_COLOR")

    def analyze_feature(self, feature: str) -> List:
        if not self.obj or not self.obj.id_data:
            return []

        # Create cache key including object name
        cache_key = (self.obj.name, feature)

        # Check cache first
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        # Perform analysis and cache result
        indices = self._analyze_feature_impl(feature)
        self._analysis_cache[cache_key] = indices
        return indices

    def _analyze_feature_impl(self, feature: str) -> List:

        print("test")
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

        indices = []

        try:
            # Use existing feature checks but with optimized data access
            if feature in self.vertex_features:
                self._analyze_vertex_feature(bm, feature, indices)
            elif feature in self.edge_features:
                self._analyze_edge_feature(bm, feature, indices)
            elif feature in self.face_features:
                self._analyze_face_feature(bm, feature, indices)
        except KeyboardInterrupt:
            pass
        finally:
            bm.free()

        return indices

    def _analyze_vertex_feature(
        self, bm: bmesh.types.BMesh, feature: str, indices: List
    ):
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
        vert_counts = np.array([len(f.verts) for f in bm.faces])

        if feature == "tri_faces":
            indices.extend(np.where(vert_counts == 3)[0])
        elif feature == "quad_faces":
            indices.extend(np.where(vert_counts == 4)[0])
        elif feature == "ngon_faces":
            indices.extend(np.where(vert_counts > 4)[0])
        elif feature == "non_planar_faces":
            for f in bm.faces:
                if not self._is_planar(f):
                    indices.append(f.index)
        elif feature == "degenerate_faces":
            for f in bm.faces:
                if self._is_degenerate(f):
                    indices.append(f.index)

    def _is_planar(self, face: bmesh.types.BMFace) -> bool:
        if len(face.verts) <= 3:
            return True

        verts = np.array([v.co for v in face.verts])
        normal = np.array(face.normal)
        center = np.mean(verts, axis=0)

        vectors = verts - center
        vectors /= np.linalg.norm(vectors, axis=1)[:, np.newaxis]

        dots = np.abs(np.dot(vectors, normal))
        angles = np.arccos(np.clip(dots, -1.0, 1.0))

        threshold_rad = math.radians(
            bpy.context.scene.Mesh_Analysis_Overlay_Properties.non_planar_threshold
        )
        return np.all(np.abs(angles - math.pi / 2) <= threshold_rad)

    def _is_degenerate(self, face: bmesh.types.BMFace) -> bool:
        if face.calc_area() < 1e-8:
            return True

        verts = face.verts
        if len(verts) < 3:
            return True

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

    def get_batch(
        self, feature: str, indices: List[int], primitive_type: str
    ) -> Optional[dict]:
        if not indices:
            return None

        cache_key = (
            self.obj.id_data.id_properties_ensure(),
            feature,
            self.obj.data.id_data.original.id_properties_ensure(),
        )

        # Check cache first
        if cache_key in self._batch_cache:
            return self._batch_cache[cache_key]

        try:
            mesh = self.obj.data
            world_matrix = self.obj.matrix_world
            normal_matrix = world_matrix.inverted().transposed().to_3x3()

            positions = []
            normals = []

            if primitive_type == "POINTS":
                for i in indices:
                    vert = mesh.vertices[i]
                    positions.append(world_matrix @ vert.co)
                    normals.append(normal_matrix @ vert.normal)
            elif primitive_type == "LINES":
                for i in indices:
                    edge = mesh.edges[i]
                    for vert_idx in edge.vertices:
                        vert = mesh.vertices[vert_idx]
                        positions.append(world_matrix @ vert.co)
                        normals.append(normal_matrix @ vert.normal)
            else:  # TRIS
                for i in indices:
                    face = mesh.polygons[i]
                    if len(face.vertices) > 3:
                        triangles = []
                        for tri_idx in range(1, len(face.vertices) - 1):
                            triangles.extend([0, tri_idx, tri_idx + 1])

                        for tri_idx in range(0, len(triangles), 3):
                            for offset in range(3):
                                vert_idx = face.vertices[triangles[tri_idx + offset]]
                                vert = mesh.vertices[vert_idx]
                                positions.append(world_matrix @ vert.co)
                                normals.append(normal_matrix @ vert.normal)
                    else:
                        for vert_idx in face.vertices:
                            vert = mesh.vertices[vert_idx]
                            positions.append(world_matrix @ vert.co)
                            normals.append(normal_matrix @ vert.normal)

            batch_data = {"positions": positions, "normals": normals}
            self._batch_cache[cache_key] = batch_data
            return batch_data

        except Exception as e:
            print(f"Error creating batch: {e}")
            return None

    @classmethod
    def clear_cache(cls):
        cls._analyzers.clear()
        cls._analysis_cache.clear()
        cls._batch_cache.clear()

    @classmethod
    def get_analyzer(cls, obj: Object) -> "MeshAnalyzer":
        if not obj or obj.type != "MESH":
            raise ValueError("Invalid mesh object")

        obj_name = obj.name
        current_time = bpy.context.scene.frame_current

        if obj_name in cls._analyzers:
            timestamp, analyzer = cls._analyzers[obj_name]
            if analyzer.obj.id_data:  # Check if object still exists
                cls._analyzers[obj_name] = (current_time, analyzer)  # Update timestamp
                return analyzer

        # Create new analyzer
        analyzer = cls(obj)

        # Manage cache size
        if len(cls._analyzers) >= cls._max_queue_size:
            # Remove oldest analyzer and its associated caches
            oldest_name = min(cls._analyzers.keys(), key=lambda k: cls._analyzers[k][0])
            del cls._analyzers[oldest_name]

            # Clear caches for oldest object
            cls._analysis_cache = {
                k: v for k, v in cls._analysis_cache.items() if k[0] != oldest_name
            }
            cls._batch_cache = {
                k: v for k, v in cls._batch_cache.items() if k[0] != oldest_name
            }

        cls._analyzers[obj_name] = (current_time, analyzer)
        return analyzer

    @classmethod
    def update_analysis(cls, obj: Object, features=None):
        from .operators import drawer  # Import here to avoid circular import

        analyzer = cls.get_analyzer(obj)
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

        if not features:
            # Update all features (enabled or not)
            features = []
            for feature_set in [
                cls.vertex_features,
                cls.edge_features,
                cls.face_features,
            ]:
                features.extend(feature_set)

        if drawer:
            for feature in features:
                if feature in drawer.batches:
                    del drawer.batches[feature]

        # Only create batches for enabled features
        for feature in features:
            if hasattr(props, f"{feature}_enabled") and getattr(
                props, f"{feature}_enabled"
            ):
                indices = analyzer.analyze_feature(feature)
                if indices and drawer:
                    primitive_type = cls.get_primitive_type(feature)
                    color = tuple(getattr(props, f"{feature}_color"))
                    drawer.update_feature_batch(feature, indices, color, primitive_type)
            else:
                # If feature is disabled, remove its batch if it exists
                if drawer and feature in drawer.batches:
                    del drawer.batches[feature]

        return analyzer

    @classmethod
    def get_primitive_type(cls, feature: str) -> str:
        """Get the primitive type for a given feature"""
        if feature in cls.face_features:
            return "TRIS"
        elif feature in cls.edge_features:
            return "LINES"
        elif feature in cls.vertex_features:
            return "POINTS"
        return None
