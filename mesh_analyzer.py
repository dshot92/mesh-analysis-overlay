# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh
import logging
import math
import gpu
import numpy as np
from gpu_extras.batch import batch_for_shader
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


class MeshAnalyzer:
    # Define feature sets as class attributes
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

    # Add batch cache storage
    _batch_cache = {}

    def __init__(self, obj: Object):
        if not obj or obj.type != "MESH":
            raise ValueError("Invalid mesh object")
        self.obj = obj
        self.scene_props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        self.mesh_stats = {"verts": 0, "edges": 0, "faces": 0}
        self._shader = gpu.shader.from_builtin("FLAT_COLOR")

    def analyze_feature(self, feature: str) -> List:
        return self._analyze_feature_impl(feature)

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
            logger.debug("Analysis interrupted")
        finally:
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

    def get_batch(
        self, feature: str, color: tuple, primitive_type: str
    ) -> Optional[gpu.types.GPUBatch]:
        """Get or create a batch for the given feature"""
        cache_key = (self.obj.name, feature)

        # Return cached batch if mesh hasn't been modified
        if cache_key in self._batch_cache:
            return self._batch_cache[cache_key]

        indices = self.analyze_feature(feature)
        if not indices:
            return None

        # Create batch based on primitive type
        try:
            mesh = self.obj.data
            world_matrix = self.obj.matrix_world

            if primitive_type == "POINTS":
                positions = [world_matrix @ mesh.vertices[i].co for i in indices]
            elif primitive_type == "LINES":
                positions = []
                for i in indices:
                    edge = mesh.edges[i]
                    positions.extend(
                        [
                            world_matrix @ mesh.vertices[edge.vertices[0]].co,
                            world_matrix @ mesh.vertices[edge.vertices[1]].co,
                        ]
                    )
            else:  # TRIS
                positions = []
                for i in indices:
                    face = mesh.polygons[i]
                    # Triangulate the face
                    if len(face.vertices) > 3:
                        # Get triangulation from tessface
                        triangles = []
                        for tri_idx in range(1, len(face.vertices) - 1):
                            triangles.extend([0, tri_idx, tri_idx + 1])

                        # Add vertices for each triangle
                        for tri_idx in range(0, len(triangles), 3):
                            for offset in range(3):
                                vert_idx = face.vertices[triangles[tri_idx + offset]]
                                positions.append(
                                    world_matrix @ mesh.vertices[vert_idx].co
                                )
                    else:
                        # Handle regular triangles
                        for vert_idx in face.vertices:
                            positions.append(world_matrix @ mesh.vertices[vert_idx].co)

            batch = batch_for_shader(
                self._shader,
                primitive_type,
                {"pos": positions, "color": [color] * len(positions)},
            )

            # Cache the batch
            self._batch_cache[cache_key] = batch
            return batch

        except (AttributeError, IndexError, ReferenceError):
            return None

    @classmethod
    def clear_cache(cls):
        """Clear the batch cache"""
        cls._batch_cache.clear()

    @classmethod
    def get_analyzer(cls, obj: Object) -> "MeshAnalyzer":
        """Get or create a MeshAnalyzer instance for the given object"""
        if not obj or obj.type != "MESH":
            raise ValueError("Invalid mesh object")
        return cls(obj)
