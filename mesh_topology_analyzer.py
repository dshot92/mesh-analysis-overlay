# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

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

        # recalculate bm normals
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

        # Clear previous data
        self.clear_data()

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

        # Analyze faces
        tris_to_process = []
        quads_to_process = []
        ngons_to_process = []

        for face in bm.faces:
            if len(face.verts) == 3:  # Triangle
                tris_to_process.append(face)
            elif len(face.verts) == 4:  # Quad
                quads_to_process.append(face)
            elif len(face.verts) > 4:  # N-gon
                ngons_to_process.append(face)

        # Process triangles
        for face in tris_to_process:
            verts = [matrix_world @ v.co for v in face.verts]
            normal = matrix_world.to_3x3() @ face.normal
            self.tris_data.extend(verts)
            self.tris_normals.extend([normal] * 3)

        # Process quads: triangulate
        for face in quads_to_process:
            face_copy = face.copy()
            result = bmesh.ops.triangulate(bm, faces=[face_copy], quad_method="BEAUTY")
            for new_face in result["faces"]:
                normal = matrix_world.to_3x3() @ face.normal
                new_verts = [matrix_world @ v.co for v in new_face.verts]
                self.quads_data.extend(new_verts)
                self.quads_normals.extend([normal] * 3)

        # Process ngons: triangulate
        for face in ngons_to_process:
            face_copy = face.copy()
            result = bmesh.ops.triangulate(
                bm, faces=[face_copy], ngon_method="EAR_CLIP"
            )
            for new_face in result["faces"]:
                normal = matrix_world.to_3x3() @ face.normal
                new_verts = [matrix_world @ v.co for v in new_face.verts]
                self.ngons_data.extend(new_verts)
                self.ngons_normals.extend([normal] * 3)

        # Free BMesh
        bm.free()
