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

debug_print = True


@dataclass
class AnalysisCache:
    # Face data with normals and cache flag
    tri_faces: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )  # (has_data, verts, normals)
    quad_faces: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )
    ngon_faces: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )
    non_planar_faces: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )

    # Vertex data with normals and cache flag
    single_vertices: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )
    n_pole_vertices: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )
    e_pole_vertices: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )
    high_pole_vertices: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )
    non_manifold_vertices: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )

    # Edge data with normals and cache flag
    non_manifold_edges: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )
    sharp_edges: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )
    seam_edges: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )
    boundary_edges: Tuple[bool, List[Vector], List[Vector]] = field(
        default_factory=lambda: (False, [], [])
    )

    def update_from_analyzer(self, analyzer, props):
        """Update only the enabled analysis types"""
        # Face data
        for key in analyzer.face_data:
            if getattr(props, f"show_{key}_faces", False):
                verts, normals = analyzer.face_data[key]
                new_verts = verts.copy() if verts else []
                new_normals = normals.copy() if normals else []
                setattr(self, f"{key}_faces", (True, new_verts, new_normals))
                if debug_print:
                    print(f"Caching {key}_faces: {len(new_verts)} vertices")
            else:
                setattr(self, f"{key}_faces", (False, [], []))

        # Vertex data
        for key in analyzer.vertex_data:
            if getattr(props, f"show_{key}_vertices", False):
                verts, normals = analyzer.vertex_data[key]
                new_verts = verts.copy() if verts else []
                new_normals = normals.copy() if normals else []
                setattr(self, f"{key}_vertices", (True, new_verts, new_normals))
                if debug_print:
                    print(f"Caching {key}_vertices: {len(new_verts)} vertices")
            else:
                setattr(self, f"{key}_vertices", (False, [], []))

        # Edge data
        for key in analyzer.edge_data:
            if getattr(props, f"show_{key}_edges", False):
                verts, normals = analyzer.edge_data[key]
                new_verts = verts.copy() if verts else []
                new_normals = normals.copy() if normals else []
                setattr(self, f"{key}_edges", (True, new_verts, new_normals))
                if debug_print:
                    print(f"Caching {key}_edges: {len(new_verts)} vertices")
            else:
                setattr(self, f"{key}_edges", (False, [], []))

    def restore_to_analyzer(self, analyzer, props):
        """Restore ONLY the empty data types that are newly enabled"""
        # Face data
        for key in analyzer.face_data:
            if getattr(props, f"show_{key}_faces"):
                has_data, verts, normals = getattr(self, f"{key}_faces")
                if has_data:  # Only check the flag
                    analyzer.face_data[key] = (verts, normals)
                    if debug_print:
                        print(f"Restoring {key}_faces: {len(verts)} vertices")

        # Vertex data
        for key in analyzer.vertex_data:
            if getattr(props, f"show_{key}_vertices"):
                has_data, verts, normals = getattr(self, f"{key}_vertices")
                if has_data:  # Only check the flag
                    analyzer.vertex_data[key] = (verts, normals)
                    if debug_print:
                        print(f"Restoring {key}_vertices: {len(verts)} vertices")

        # Edge data
        for key in analyzer.edge_data:
            if getattr(props, f"show_{key}_edges"):
                has_data, verts, normals = getattr(self, f"{key}_edges")
                if has_data:  # Only check the flag
                    analyzer.edge_data[key] = (verts, normals)
                    if debug_print:
                        print(f"Restoring {key}_edges: {len(verts)} vertices")


class MeshAnalyzer:
    def __init__(self):
        self.clear_data()
        # LRU cache with max size 10
        self.cache = (
            OrderedDict()
        )  # Keys are object names, values are AnalysisCache objects
        self.MAX_CACHE_SIZE = 10
        # Add mesh revision tracking
        self.last_mesh_revision = {}

    def clear_data(self):
        # Initialize with tuples of (vertices, normals)
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
            "non_manifold": ([], []),
        }

        self.edge_data = {
            "non_manifold": ([], []),
            "sharp": ([], []),
            "seam": ([], []),
            "boundary": ([], []),
        }

    def _cache_analysis(self, obj_name: str, props):
        # Creates/updates cache entry for specific object
        cache_entry = AnalysisCache()
        cache_entry.update_from_analyzer(self, props)

        if obj_name in self.cache:
            # Update existing object's cache
            self.cache[obj_name] = cache_entry
        else:
            # Remove oldest object's cache if at capacity
            if len(self.cache) >= self.MAX_CACHE_SIZE:
                removed_key, _ = self.cache.popitem(last=False)
            # Add new object's cache
            self.cache[obj_name] = cache_entry

    def get_cached_analysis(self, obj_name: str, props) -> bool:
        if obj_name not in self.cache:
            if debug_print:
                print(f"Cache miss for {obj_name}")
            return False

        # Check if all enabled analysis types are present in the cache
        analyze_verts, analyze_edges, analyze_faces = self._should_analyze(props)
        cache_entry = self.cache[obj_name]

        # Force cache miss if any enabled type has no data
        if analyze_faces:
            for key in self.face_data:
                if (
                    getattr(props, f"show_{key}_faces")
                    and not getattr(cache_entry, f"{key}_faces")[0]
                ):
                    if debug_print:
                        print(f"Cache miss: missing {key}_faces data")
                    return False

        if analyze_verts:
            for key in self.vertex_data:
                if (
                    getattr(props, f"show_{key}_vertices")
                    and not getattr(cache_entry, f"{key}_vertices")[0]
                ):
                    if debug_print:
                        print(f"Cache miss: missing {key}_vertices data")
                    return False

        if analyze_edges:
            for key in self.edge_data:
                if (
                    getattr(props, f"show_{key}_edges")
                    and not getattr(cache_entry, f"{key}_edges")[0]
                ):
                    if debug_print:
                        print(f"Cache miss: missing {key}_edges data")
                    return False

        # Only restore if we have all required data
        cache_entry.restore_to_analyzer(self, props)
        self.cache.move_to_end(obj_name)  # Update LRU order
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

    def _process_face(self, face, matrix_world, props):
        """Process a single face for triangles, quads, ngons and planarity"""
        vert_count = len(face.verts)
        # Get per-vertex positions and normals
        vertices = [matrix_world @ v.co for v in face.verts]
        normals = [matrix_world.to_3x3() @ v.normal for v in face.verts]

        if vert_count == 3 and props.show_tri_faces:
            self.face_data["tri"][0].extend(vertices)
            self.face_data["tri"][1].extend(normals)
        elif vert_count == 4 and props.show_quad_faces:
            # For quads, maintain vertex order for triangulation
            quad_verts = [vertices[i] for i in (0, 1, 2, 0, 2, 3)]
            quad_norms = [normals[i] for i in (0, 1, 2, 0, 2, 3)]
            self.face_data["quad"][0].extend(quad_verts)
            self.face_data["quad"][1].extend(quad_norms)
        elif vert_count > 4 and props.show_ngon_faces:
            ngon_verts = []
            ngon_norms = []
            for i in range(1, vert_count - 1):
                ngon_verts.extend([vertices[0], vertices[i], vertices[i + 1]])
                ngon_norms.extend([normals[0], normals[i], normals[i + 1]])
            self.face_data["ngon"][0].extend(ngon_verts)
            self.face_data["ngon"][1].extend(ngon_norms)

        # Check planarity for faces with more than 3 vertices
        if vert_count > 3 and props.show_non_planar_faces:
            if not self.is_face_planar(face, props.non_planar_threshold):
                non_planar_verts = []
                non_planar_norms = []
                for i in range(1, vert_count - 1):
                    non_planar_verts.extend([vertices[0], vertices[i], vertices[i + 1]])
                    non_planar_norms.extend([normals[0], normals[i], normals[i + 1]])
                self.face_data["non_planar"][0].extend(non_planar_verts)
                self.face_data["non_planar"][1].extend(non_planar_norms)

    def _process_vertex(self, vert, matrix_world, props):
        """Process a single vertex for poles and manifold status"""
        pos = matrix_world @ vert.co
        normal = matrix_world.to_3x3() @ vert.normal
        edge_count = len(vert.link_edges)

        if edge_count == 0 and props.show_single_vertices:
            self.vertex_data["single"][0].append(pos)
            self.vertex_data["single"][1].append(normal)
        if edge_count == 3 and props.show_n_pole_vertices:
            self.vertex_data["n_pole"][0].append(pos)
            self.vertex_data["n_pole"][1].append(normal)
        if edge_count == 5 and props.show_e_pole_vertices:
            self.vertex_data["e_pole"][0].append(pos)
            self.vertex_data["e_pole"][1].append(normal)
        if edge_count >= 6 and props.show_high_pole_vertices:
            self.vertex_data["high_pole"][0].append(pos)
            self.vertex_data["high_pole"][1].append(normal)
        if not vert.is_manifold and props.show_non_manifold_vertices:
            self.vertex_data["non_manifold"][0].append(pos)
            self.vertex_data["non_manifold"][1].append(normal)

    def _process_edge(self, edge, matrix_world, props):
        """Process a single edge for manifold status, sharpness, seams and boundaries"""
        # Get positions and normals for both vertices of the edge
        v1 = matrix_world @ edge.verts[0].co
        v2 = matrix_world @ edge.verts[1].co
        n1 = matrix_world.to_3x3() @ edge.verts[0].normal
        n2 = matrix_world.to_3x3() @ edge.verts[1].normal

        if not edge.is_manifold and props.show_non_manifold_edges:
            self.edge_data["non_manifold"][0].extend([v1, v2])
            self.edge_data["non_manifold"][1].extend([n1, n2])
        if not edge.smooth and props.show_sharp_edges:
            self.edge_data["sharp"][0].extend([v1, v2])
            self.edge_data["sharp"][1].extend([n1, n2])
        if edge.seam and props.show_seam_edges:
            self.edge_data["seam"][0].extend([v1, v2])
            self.edge_data["seam"][1].extend([n1, n2])
        if len(edge.link_faces) == 1 and props.show_boundary_edges:
            self.edge_data["boundary"][0].extend([v1, v2])
            self.edge_data["boundary"][1].extend([n1, n2])

    def analyze_mesh(self, obj):
        """Main analysis method"""
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

        if not obj or obj.type != "MESH":
            return

        # Use mesh data's modification time instead
        current_revision = obj.data.update_tag
        if obj.name in self.last_mesh_revision:
            if self.last_mesh_revision[obj.name] == current_revision:
                # Mesh hasn't changed, try to use cached data
                if self.get_cached_analysis(obj.name, props):
                    return

        # Update revision tracking
        self.last_mesh_revision[obj.name] = current_revision

        # Clear cache if mesh has changed
        if (
            obj.name not in self.last_mesh_revision
            or self.last_mesh_revision[obj.name] != current_revision
        ):
            if obj.name in self.cache:
                del self.cache[obj.name]

        # Clear existing data before analysis
        self.clear_data()

        # Try to use cached data only if mesh hasn't changed
        if obj.name in self.cache:
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
