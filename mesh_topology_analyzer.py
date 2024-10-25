# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

import bpy
import bmesh


class MeshTopologyAnalyzer:
    def __init__(self):
        self.clear_data()

    def clear_data(self):
        self.tris_data = []
        self.tris_normals = []
        self.quads_data = []
        self.quads_normals = []
        self.ngons_data = []
        self.ngons_normals = []
        self.poles_data = []
        self.singles_data = []
        self.non_manifold_edges_data = []
        self.non_manifold_verts_data = []

    def analyze_mesh(self, obj, offset):
        mesh = obj.data
        matrix_world = obj.matrix_world

        # Create BMesh
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        # Clear previous data
        self.clear_data()

        # Analyze faces
        for face in bm.faces:  # Use BMesh faces instead of mesh polygons
            verts = [matrix_world @ v.co for v in face.verts]
            normal = matrix_world.to_3x3() @ face.normal

            if len(face.verts) == 3:  # Triangle
                self.tris_data.extend(verts)
                self.tris_normals.extend([normal] * 3)
            elif len(face.verts) == 4:  # Quad
                tri1 = [verts[0], verts[1], verts[2]]
                tri2 = [verts[2], verts[3], verts[0]]
                self.quads_data.extend(tri1 + tri2)
                self.quads_normals.extend([normal] * 6)
            else:  # N-gon
                for i in range(1, len(face.verts) - 1):
                    tri = [verts[0], verts[i], verts[i + 1]]
                    self.ngons_data.extend(tri)
                    self.ngons_normals.extend([normal] * 3)

        # Analyze vertices for poles and singles
        for v in bm.verts:
            world_pos = matrix_world @ v.co
            edge_count = len(v.link_edges)

            if edge_count == 0:
                self.singles_data.append(world_pos)
            elif edge_count > 4:
                self.poles_data.append(world_pos)

            if not v.is_manifold:
                self.non_manifold_verts_data.append(world_pos)

        # Analyze non-manifold edges
        for edge in bm.edges:
            if not edge.is_manifold:
                v1 = matrix_world @ edge.verts[0].co
                v2 = matrix_world @ edge.verts[1].co
                self.non_manifold_edges_data.extend([v1, v2])

        # Free BMesh
        bm.free()
