# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

from collections import OrderedDict
from typing import List, Tuple
from mathutils import Vector
from dataclasses import dataclass, field
import bmesh
import bpy
import math

debug_print = False


@dataclass
class AnalysisCache:
    # Face data
    tri_faces: List[Vector] = field(default=None)
    quad_faces: List[Vector] = field(default=None)
    ngon_faces: List[Vector] = field(default=None)
    non_planar_faces: List[Vector] = field(default=None)

    # Vertex data
    single_vertices: List[Vector] = field(default=None)
    n_pole_vertices: List[Vector] = field(default=None)
    e_pole_vertices: List[Vector] = field(default=None)
    high_pole_vertices: List[Vector] = field(default=None)
    non_manifold_vertices: List[Vector] = field(default=None)

    # Edge data
    non_manifold_edges: List[Vector] = field(default=None)
    sharp_edges: List[Vector] = field(default=None)
    seam_edges: List[Vector] = field(default=None)
    boundary_edges: List[Vector] = field(default=None)

    def update_from_analyzer(self, analyzer, props):
        """Update only the enabled analysis types"""
        # Face data
        for key in analyzer.face_data:
            if getattr(props, f"show_{key}_faces"):
                data = analyzer.face_data[key]
                setattr(self, f"{key}_faces", data.copy() if data is not None else [])
                if debug_print and data:
                    print(f"Caching {key}_faces: {len(data)} vertices")
            else:
                setattr(self, f"{key}_faces", None)

        # Vertex data
        for key in analyzer.vertex_data:
            if getattr(props, f"show_{key}_vertices"):
                data = analyzer.vertex_data[key]
                setattr(
                    self, f"{key}_vertices", data.copy() if data is not None else []
                )
                if debug_print and data:
                    print(f"Caching {key}_vertices: {len(data)} vertices")
            else:
                setattr(self, f"{key}_vertices", None)

        # Edge data
        for key in analyzer.edge_data:
            if getattr(props, f"show_{key}_edges"):
                data = analyzer.edge_data[key]
                setattr(self, f"{key}_edges", data.copy() if data is not None else [])
                if debug_print and data:
                    print(f"Caching {key}_edges: {len(data)} vertices")
            else:
                setattr(self, f"{key}_edges", None)

    def restore_to_analyzer(self, analyzer, props):
        """Restore ONLY the empty data types that are newly enabled"""
        # Face data
        for key in analyzer.face_data:
            if getattr(props, f"show_{key}_faces"):
                data = getattr(self, f"{key}_faces")
                # Only restore if: has cached data AND current data is empty AND analyzer data is empty
                if (
                    data is not None
                    and not analyzer.face_data[key]
                    and len(analyzer.face_data[key]) == 0
                ):  # Extra check to ensure it's truly empty
                    analyzer.face_data[key] = data.copy()
                    if debug_print:
                        print(f"Restoring {key}_faces: {len(data)} vertices")

        # Vertex data
        for key in analyzer.vertex_data:
            if getattr(props, f"show_{key}_vertices"):
                data = getattr(self, f"{key}_vertices")
                if (
                    data is not None
                    and not analyzer.vertex_data[key]
                    and len(analyzer.vertex_data[key]) == 0
                ):  # Extra check to ensure it's truly empty
                    analyzer.vertex_data[key] = data.copy()
                    if debug_print:
                        print(f"Restoring {key}_vertices: {len(data)} vertices")

        # Edge data
        for key in analyzer.edge_data:
            if getattr(props, f"show_{key}_edges"):
                data = getattr(self, f"{key}_edges")
                if (
                    data is not None
                    and not analyzer.edge_data[key]
                    and len(analyzer.edge_data[key]) == 0
                ):  # Extra check to ensure it's truly empty
                    analyzer.edge_data[key] = data.copy()
                    if debug_print:
                        print(f"Restoring {key}_edges: {len(data)} vertices")


class MeshAnalyzer:
    def __init__(self):
        self.clear_data()
        # LRU cache with max size 10
        self.cache = OrderedDict()
        self.MAX_CACHE_SIZE = 10

    def clear_data(self):
        self.face_data = {
            "tri": [],
            "quad": [],
            "ngon": [],
            "non_planar": [],
        }

        self.vertex_data = {
            "single": [],
            "n_pole": [],
            "e_pole": [],
            "high_pole": [],
            "non_manifold": [],
        }

        self.edge_data = {
            "non_manifold": [],
            "sharp": [],
            "seam": [],
            "boundary": [],
        }

    def _cache_analysis(self, obj_name: str, props):
        cache_entry = AnalysisCache()
        cache_entry.update_from_analyzer(self, props)

        if obj_name in self.cache:
            if debug_print:
                print(f"Updating existing cache for {obj_name}")
            self.cache[obj_name] = cache_entry
        else:
            if len(self.cache) >= self.MAX_CACHE_SIZE:
                removed_key, _ = self.cache.popitem(last=False)
                if debug_print:
                    print(f"Cache full, removing oldest entry: {removed_key}")
            self.cache[obj_name] = cache_entry
            if debug_print:
                print(f"Added new cache entry for {obj_name}")

    def get_cached_analysis(self, obj_name: str, props) -> bool:
        if obj_name not in self.cache:
            if debug_print:
                print(f"Cache miss for {obj_name}")
            return False

        cache_entry = self.cache[obj_name]

        # Check if all enabled analysis types are present in the cache
        analyze_verts, analyze_edges, analyze_faces = self._should_analyze(props)

        if analyze_faces:
            for key in self.face_data:
                if (
                    getattr(props, f"show_{key}_faces")
                    and getattr(cache_entry, f"{key}_faces") is None
                ):
                    if debug_print:
                        print(f"Cache miss: missing {key}_faces")
                    return False

        if analyze_verts:
            for key in self.vertex_data:
                if (
                    getattr(props, f"show_{key}_vertices")
                    and getattr(cache_entry, f"{key}_vertices") is None
                ):
                    if debug_print:
                        print(f"Cache miss: missing {key}_vertices")
                    return False

        if analyze_edges:
            for key in self.edge_data:
                if (
                    getattr(props, f"show_{key}_edges")
                    and getattr(cache_entry, f"{key}_edges") is None
                ):
                    if debug_print:
                        print(f"Cache miss: missing {key}_edges")
                    return False

        # Restore cached data
        cache_entry.restore_to_analyzer(self, props)

        # Update LRU order
        self.cache.move_to_end(obj_name)

        return True

    def _should_analyze(self, props) -> Tuple[bool, bool, bool]:
        """Determine which mesh elements need analysis"""
        analyze_verts = any(
            [
                props.show_single_vertices,
                props.show_non_manifold_vertices,
                props.show_n_pole_vertices,
                props.show_e_pole_vertices,
                props.show_high_pole_vertices,
            ]
        )

        analyze_edges = any(
            [
                props.show_non_manifold_edges,
                props.show_sharp_edges,
                props.show_seam_edges,
                props.show_boundary_edges,  # Add boundary check
            ]
        )

        analyze_faces = any(
            [
                props.show_tri_faces,
                props.show_quad_faces,
                props.show_ngon_faces,
                props.show_non_planar_faces,
            ]
        )

        return analyze_verts, analyze_edges, analyze_faces

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

    def _get_face_data_with_offset(self, face, matrix_world, offset) -> List[Vector]:
        """Get transformed and offset vertex positions for a face"""
        return [
            (matrix_world @ v.co) + ((matrix_world.to_3x3() @ v.normal) * offset)
            for v in face.verts
        ]

    def _process_face(self, face, matrix_world, props):
        """Process a single face for triangles, quads, ngons and planarity"""
        vert_count = len(face.verts)
        offset = props.overlay_offset
        offset_verts = self._get_face_data_with_offset(face, matrix_world, offset)

        # Triangulate and store vertices based on face type
        if vert_count == 3 and props.show_tri_faces:
            self.face_data["tri"].extend(offset_verts)
        elif vert_count == 4 and props.show_quad_faces:
            self.face_data["quad"].extend([offset_verts[i] for i in (0, 1, 2, 0, 2, 3)])
        elif vert_count > 4 and props.show_ngon_faces:
            for i in range(1, vert_count - 1):
                self.face_data["ngon"].extend(
                    [offset_verts[0], offset_verts[i], offset_verts[i + 1]]
                )

        # Check planarity for faces with more than 3 vertices
        if vert_count > 3 and props.show_non_planar_faces:
            if not self.is_face_planar(face, props.non_planar_threshold):
                for i in range(1, vert_count - 1):
                    self.face_data["non_planar"].extend(
                        [offset_verts[0], offset_verts[i], offset_verts[i + 1]]
                    )

    def _get_vertex_data_with_offset(self, vert, matrix_world, offset) -> Vector:
        """Get transformed and offset vertex position"""
        world_pos = matrix_world @ vert.co
        return world_pos + ((matrix_world.to_3x3() @ vert.normal) * offset)

    def _process_vertex(self, vert, matrix_world, props):
        """Process a single vertex for poles and manifold status"""
        offset_pos = self._get_vertex_data_with_offset(
            vert, matrix_world, props.overlay_offset
        )
        edge_count = len(vert.link_edges)

        if edge_count == 0 and props.show_single_vertices:
            self.vertex_data["single"].append(offset_pos)
        if edge_count == 3 and props.show_n_pole_vertices:
            self.vertex_data["n_pole"].append(offset_pos)
        if edge_count == 5 and props.show_e_pole_vertices:
            self.vertex_data["e_pole"].append(offset_pos)
        if edge_count >= 6 and props.show_high_pole_vertices:
            self.vertex_data["high_pole"].append(offset_pos)
        if not vert.is_manifold and props.show_non_manifold_vertices:
            self.vertex_data["non_manifold"].append(offset_pos)

    def _process_edge(self, edge, matrix_world, props):
        """Process a single edge for manifold status, sharpness, seams and boundaries"""
        offset_v1 = self._get_vertex_data_with_offset(
            edge.verts[0], matrix_world, props.overlay_offset
        )
        offset_v2 = self._get_vertex_data_with_offset(
            edge.verts[1], matrix_world, props.overlay_offset
        )

        if not edge.is_manifold and props.show_non_manifold_edges:
            self.edge_data["non_manifold"].extend([offset_v1, offset_v2])
        if not edge.smooth and props.show_sharp_edges:
            self.edge_data["sharp"].extend([offset_v1, offset_v2])
        if edge.seam and props.show_seam_edges:
            self.edge_data["seam"].extend([offset_v1, offset_v2])
        if len(edge.link_faces) == 1 and props.show_boundary_edges:
            self.edge_data["boundary"].extend([offset_v1, offset_v2])

    def analyze_mesh(self, obj):
        """Main analysis method"""
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

        # Ensure object is valid and in correct mode
        if not obj or obj.type != "MESH":
            return

        # Clear existing data before analysis
        self.clear_data()

        # Try to use cached data
        if self.get_cached_analysis(obj.name, props):
            return

        if debug_print:
            print("Performing analysis")

        # If cache miss, perform full analysis
        matrix_world = obj.matrix_world
        bm = bmesh.new()
        bm.from_mesh(obj.data)

        analyze_verts, analyze_edges, analyze_faces = self._should_analyze(props)

        if analyze_verts:
            bm.verts.ensure_lookup_table()
            for vert in bm.verts:
                self._process_vertex(vert, matrix_world, props)

        if analyze_edges:
            bm.edges.ensure_lookup_table()
            for edge in bm.edges:
                self._process_edge(edge, matrix_world, props)

        if analyze_faces:
            bm.faces.ensure_lookup_table()
            for face in bm.faces:
                self._process_face(face, matrix_world, props)

        bm.free()

        # Cache the results
        self._cache_analysis(obj.name, props)
