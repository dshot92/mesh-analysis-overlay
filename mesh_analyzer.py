# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh
import logging

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
        )  # Format: {obj_name: {'is_valid': bool, 'features': {feature: {'verts': [], 'normals': []}}}}

    def get(self, obj_name: str, feature: str) -> Tuple[bool, List, List]:
        """Get cached feature data for an object"""
        obj_cache = self.feature_cache.get(obj_name)
        if not obj_cache or not obj_cache.get("is_valid", False):
            return (False, [], [])

        feature_data = obj_cache["features"].get(feature)
        if not feature_data:
            return (False, [], [])

        return (True, feature_data["verts"], feature_data["normals"])

    def set(self, obj_name: str, feature: str, verts: List, normals: List):
        """Cache feature data for an object"""
        if obj_name not in self.feature_cache:
            self.feature_cache[obj_name] = {
                "is_valid": True,  # Add is_valid flag
                "features": {},
            }

        self.feature_cache[obj_name]["features"][feature] = {
            "verts": verts,
            "normals": normals,
        }

    def clear(self):
        """Clear all cached data"""
        self.feature_cache.clear()

    def invalidate(self, obj_name: str = None):
        """Invalidate cache for specific object or all objects"""
        if obj_name:
            if obj_name in self.feature_cache:
                self.feature_cache[obj_name][
                    "is_valid"
                ] = False  # Set invalid instead of removing
        else:
            self.feature_cache.clear()


class MeshAnalyzer:
    _cache = MeshCache()

    vertex_features = {
        "single_vertices",  # corresponds to show_single_vertices
        "non_manifold_v_vertices",  # corresponds to show_non_manifold_v_vertices
        "n_pole_vertices",  # corresponds to show_n_pole_vertices
        "e_pole_vertices",  # corresponds to show_e_pole_vertices
        "high_pole_vertices",  # corresponds to show_high_pole_vertices
    }

    edge_features = {
        "non_manifold_e_edges",  # corresponds to show_non_manifold_e_edges
        "sharp_edges",  # corresponds to show_sharp_edges
        "seam_edges",  # corresponds to show_seam_edges
        "boundary_edges",  # corresponds to show_boundary_edges
    }

    face_features = {
        "tri_faces",  # corresponds to show_tri_faces
        "quad_faces",  # corresponds to show_quad_faces
        "ngon_faces",  # corresponds to show_ngon_faces
        "non_planar_faces",  # corresponds to show_non_planar_faces
    }

    def __init__(self, obj: Object):
        logger.debug(f"\n=== Creating MeshAnalyzer for {obj.name} ===")
        if not obj or obj.type != "MESH":
            raise ValueError("Invalid mesh object")

        self.obj = obj
        self.scene_props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        self.analyzed_features = {}

    def analyze_feature(self, feature: str) -> Tuple[List, List]:
        logger.debug(f"\n=== Starting Analysis ===")
        logger.debug(f"Object: {self.obj.name}")
        logger.debug(f"Feature: {feature}")

        # Get cached result if available
        cached = self._cache.get(self.obj.name, feature)
        if cached[0]:
            logger.debug(f"✓ Using cached data")
            logger.debug(f"Found {len(cached[1])} vertices in cache")
            return (cached[1], cached[2])

        logger.debug("× Cache miss - performing new analysis")

        # Analyze and cache the result
        verts, normals = self._analyze_feature_impl(feature)
        logger.debug(f"✓ Analysis complete")
        logger.debug(f"Found {len(verts)} vertices")
        logger.debug(f"Found {len(normals)} normals")
        self._cache.set(self.obj.name, feature, verts, normals)
        return (verts, normals)

    def _analyze_feature_impl(self, feature: str) -> Tuple[List, List]:
        logger.debug(f"\n=== Feature Implementation ===")
        logger.debug(f"Creating BMesh for {self.obj.name}")
        bm = bmesh.new()
        bm.from_mesh(self.obj.data)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        verts = []
        normals = []

        if feature in self.vertex_features:
            logger.debug("Analyzing vertex feature")
            self._analyze_vertex_feature(bm, feature, verts, normals)
        elif feature in self.edge_features:
            logger.debug("Analyzing edge feature")
            self._analyze_edge_feature(bm, feature, verts, normals)
        elif feature in self.face_features:
            logger.debug("Analyzing face feature")
            self._analyze_face_feature(bm, feature, verts, normals)

        logger.debug(f"BMesh analysis complete")
        logger.debug(f"Total BMesh elements:")
        logger.debug(f"- Vertices: {len(bm.verts)}")
        logger.debug(f"- Edges: {len(bm.edges)}")
        logger.debug(f"- Faces: {len(bm.faces)}")

        bm.free()
        return (verts, normals)

    def _analyze_vertex_feature(
        self, bm: bmesh.types.BMesh, feature: str, verts: List, normals: List
    ):
        logger.debug(f"[DEBUG] Analyzing vertex feature: {feature}")
        world_matrix = self.obj.matrix_world
        for v in bm.verts:
            if feature == "single_vertices" and len(v.link_edges) == 0:
                # logger.debug(f"[DEBUG] Found single vertex at {v.co}")
                verts.append(world_matrix @ v.co.copy())
                normals.append(
                    (
                        world_matrix.inverted().transposed().to_3x3() @ v.normal
                    ).normalized()
                )
            elif feature == "non_manifold_v_vertices" and not v.is_manifold:
                verts.append(world_matrix @ v.co.copy())
                normals.append(
                    (
                        world_matrix.inverted().transposed().to_3x3() @ v.normal
                    ).normalized()
                )
            elif feature == "n_pole_vertices" and len(v.link_edges) == 3:
                verts.append(world_matrix @ v.co.copy())
                normals.append(
                    (
                        world_matrix.inverted().transposed().to_3x3() @ v.normal
                    ).normalized()
                )
            elif feature == "e_pole_vertices" and len(v.link_edges) == 5:
                verts.append(world_matrix @ v.co.copy())
                normals.append(
                    (
                        world_matrix.inverted().transposed().to_3x3() @ v.normal
                    ).normalized()
                )
            elif feature == "high_pole_vertices" and len(v.link_edges) >= 6:
                verts.append(world_matrix @ v.co.copy())
                normals.append(
                    (
                        world_matrix.inverted().transposed().to_3x3() @ v.normal
                    ).normalized()
                )

    def _analyze_edge_feature(
        self, bm: bmesh.types.BMesh, feature: str, verts: List, normals: List
    ):
        logger.debug(f"[DEBUG] Analyzing edge feature: {feature}")
        world_matrix = self.obj.matrix_world
        for e in bm.edges:
            if feature == "non_manifold_e_edges" and not e.is_manifold:
                # logger.debug(f"[DEBUG] Found non-manifold edge")
                verts.extend([world_matrix @ v.co.copy() for v in e.verts])
                normals.extend(
                    [
                        (
                            world_matrix.inverted().transposed().to_3x3() @ v.normal
                        ).normalized()
                        for v in e.verts
                    ]
                )
            elif feature == "sharp_edges" and e.smooth is False:
                verts.extend([world_matrix @ v.co.copy() for v in e.verts])
                normals.extend(
                    [
                        (
                            world_matrix.inverted().transposed().to_3x3() @ v.normal
                        ).normalized()
                        for v in e.verts
                    ]
                )
            elif feature == "seam_edges" and e.seam:
                verts.extend([world_matrix @ v.co.copy() for v in e.verts])
                normals.extend(
                    [
                        (
                            world_matrix.inverted().transposed().to_3x3() @ v.normal
                        ).normalized()
                        for v in e.verts
                    ]
                )
            elif feature == "boundary_edges" and e.is_boundary:
                verts.extend([world_matrix @ v.co.copy() for v in e.verts])
                normals.extend(
                    [
                        (
                            world_matrix.inverted().transposed().to_3x3() @ v.normal
                        ).normalized()
                        for v in e.verts
                    ]
                )

    def _analyze_face_feature(
        self, bm: bmesh.types.BMesh, feature: str, verts: List, normals: List
    ):
        logger.debug(f"[DEBUG] Analyzing face feature: {feature}")
        world_matrix = self.obj.matrix_world
        for f in bm.faces:
            if feature == "tri_faces" and len(f.verts) == 3:
                verts.extend([world_matrix @ v.co.copy() for v in f.verts])
                normals.extend(
                    [
                        (
                            world_matrix.inverted().transposed().to_3x3() @ v.normal
                        ).normalized()
                        for v in f.verts
                    ]
                )
            elif feature == "quad_faces" and len(f.verts) == 4:
                face_verts = [world_matrix @ v.co.copy() for v in f.verts]
                face_normals = [
                    (
                        world_matrix.inverted().transposed().to_3x3() @ v.normal
                    ).normalized()
                    for v in f.verts
                ]
                # First triangle (0,1,2)
                verts.extend([face_verts[0], face_verts[1], face_verts[2]])
                normals.extend([face_normals[0], face_normals[1], face_normals[2]])
                # Second triangle (0,2,3)
                verts.extend([face_verts[0], face_verts[2], face_verts[3]])
                normals.extend([face_normals[0], face_normals[2], face_normals[3]])
            elif feature == "ngon_faces" and len(f.verts) > 4:
                face_verts = [world_matrix @ v.co.copy() for v in f.verts]
                face_normals = [
                    (
                        world_matrix.inverted().transposed().to_3x3() @ v.normal
                    ).normalized()
                    for v in f.verts
                ]
                # Create triangles: (0,i,i+1) for i in range(1, n-1)
                for i in range(1, len(face_verts) - 1):
                    verts.extend([face_verts[0], face_verts[i], face_verts[i + 1]])
                    normals.extend(
                        [face_normals[0], face_normals[i], face_normals[i + 1]]
                    )
            elif feature == "non_planar_faces" and not self._is_planar(f):
                face_verts = [world_matrix @ v.co.copy() for v in f.verts]
                face_normals = [
                    (
                        world_matrix.inverted().transposed().to_3x3() @ v.normal
                    ).normalized()
                    for v in f.verts
                ]
                if len(face_verts) == 4:
                    # First triangle (0,1,2)
                    verts.extend([face_verts[0], face_verts[1], face_verts[2]])
                    normals.extend([face_normals[0], face_normals[1], face_normals[2]])
                    # Second triangle (0,2,3)
                    verts.extend([face_verts[0], face_verts[2], face_verts[3]])
                    normals.extend([face_normals[0], face_normals[2], face_normals[3]])
                elif len(face_verts) > 4:
                    for i in range(1, len(face_verts) - 1):
                        verts.extend([face_verts[0], face_verts[i], face_verts[i + 1]])
                        normals.extend(
                            [face_normals[0], face_normals[i], face_normals[i + 1]]
                        )

    def _is_planar(self, face: bmesh.types.BMFace, threshold: float = 0.0) -> bool:
        if len(face.verts) <= 3:
            # logger.debug("[DEBUG] Face is triangle or less - automatically planar")
            return True

        normal = face.normal
        center = face.calc_center_median()

        for v in face.verts:
            d = abs(normal.dot(v.co - center))
            if d > threshold:
                # logger.debug(f"[DEBUG] Non-planar face detected - deviation: {d}")
                return False
        return True

    @classmethod
    def invalidate_cache(cls, obj_name: str = None):
        cls._cache.invalidate(obj_name)
