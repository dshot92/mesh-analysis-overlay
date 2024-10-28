# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

from collections import OrderedDict
from typing import List, Tuple, Dict, Any
from mathutils import Vector
from dataclasses import dataclass, field
import bmesh
import bpy
import math

debug_print = False


@dataclass
class AnalysisCache:
    # Face data
    tri_faces: List[Vector] = field(default_factory=list)
    quad_faces: List[Vector] = field(default_factory=list)
    ngon_faces: List[Vector] = field(default_factory=list)
    non_planar_faces: List[Vector] = field(default_factory=list)

    # Vertex data
    single_vertices: List[Vector] = field(default_factory=list)
    n_pole_vertices: List[Vector] = field(default_factory=list)
    e_pole_vertices: List[Vector] = field(default_factory=list)
    high_pole_vertices: List[Vector] = field(default_factory=list)
    non_manifold_vertices: List[Vector] = field(default_factory=list)

    # Edge data
    non_manifold_edges: List[Vector] = field(default_factory=list)
    sharp_edges: List[Vector] = field(default_factory=list)
    seam_edges: List[Vector] = field(default_factory=list)
    boundary_edges: List[Vector] = field(default_factory=list)

    def update_from_analyzer(self, analyzer, props):
        """Update only the enabled analysis types"""
        # Face data
        for key in analyzer.face_data:
            if getattr(props, f"show_{key}_faces"):
                data = analyzer.face_data[key].copy()
                setattr(self, f"{key}_faces", data)
                if debug_print:
                    print(f"Caching {key}_faces: {len(data)} vertices")
            else:
                setattr(self, f"{key}_faces", [])

        # Vertex data
        for key in analyzer.vertex_data:
            if getattr(props, f"show_{key}_vertices"):
                data = analyzer.vertex_data[key].copy()
                setattr(self, f"{key}_vertices", data)
                if debug_print:
                    print(f"Caching {key}_vertices: {len(data)} vertices")
            else:
                setattr(self, f"{key}_vertices", [])

        # Edge data
        for key in analyzer.edge_data:
            if getattr(props, f"show_{key}_edges"):
                data = analyzer.edge_data[key].copy()
                setattr(self, f"{key}_edges", data)
                if debug_print:
                    print(f"Caching {key}_edges: {len(data)} vertices")
            else:
                setattr(self, f"{key}_edges", [])

    def restore_to_analyzer(self, analyzer, props):
        """Restore only the enabled analysis types"""
        # Face data
        for key in analyzer.face_data:
            if getattr(props, f"show_{key}_faces"):
                data = getattr(self, f"{key}_faces")
                analyzer.face_data[key] = data.copy()
                if debug_print:
                    print(f"Restoring {key}_faces: {len(data)} vertices")

        # Vertex data
        for key in analyzer.vertex_data:
            if getattr(props, f"show_{key}_vertices"):
                data = getattr(self, f"{key}_vertices")
                analyzer.vertex_data[key] = data.copy()
                if debug_print:
                    print(f"Restoring {key}_vertices: {len(data)} vertices")

        # Edge data
        for key in analyzer.edge_data:
            if getattr(props, f"show_{key}_edges"):
                data = getattr(self, f"{key}_edges")
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
                print(f"Updating cache for {obj_name}")
            del self.cache[obj_name]
        elif len(self.cache) >= self.MAX_CACHE_SIZE:
            removed_key = next(iter(self.cache))
            if debug_print:
                print(f"Cache full, removing oldest entry: {removed_key}")
            self.cache.popitem(last=False)

        self.cache[obj_name] = cache_entry
        if debug_print:
            print(f"Added new cache entry for {obj_name}")

    def get_cached_analysis(self, obj_name: str, props) -> bool:
        if obj_name not in self.cache:
            if debug_print:
                print(f"Cache miss for {obj_name}")
            return False

        cache_entry = self.cache[obj_name]

        # Only check if the attribute exists, empty lists are valid
        for key in self.face_data:
            if getattr(props, f"show_{key}_faces"):
                if not hasattr(cache_entry, f"{key}_faces"):
                    if debug_print:
                        print(
                            f"Cache miss: missing {key} faces attribute for {obj_name}"
                        )
                    return False

        for key in self.vertex_data:
            if getattr(props, f"show_{key}_vertices"):
                if not hasattr(cache_entry, f"{key}_vertices"):
                    if debug_print:
                        print(
                            f"Cache miss: missing {key} vertex attribute for {obj_name}"
                        )
                    return False

        for key in self.edge_data:
            if getattr(props, f"show_{key}_edges"):
                if not hasattr(cache_entry, f"{key}_edges"):
                    if debug_print:
                        print(
                            f"Cache miss: missing {key} edge attribute for {obj_name}"
                        )
                    return False

        # If we get here, all requested overlays are present
        cache_entry.restore_to_analyzer(self, props)
        if debug_print:
            print(f"Cache hit for {obj_name}")

        # Update LRU order
        del self.cache[obj_name]
        self.cache[obj_name] = cache_entry

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
            print("Performing full analysis")

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
