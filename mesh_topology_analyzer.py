import bpy
from mathutils import Vector
import bmesh


class MeshTopologyAnalyzer:
    def __init__(self):
        self.tris = []
        self.quads = []
        self.ngons = []
        self.poles = []
        self.singles = []
        self.non_manifold_edges = []
        self.non_manifold_verts = []

    def analyze_tris(self, obj, offset_value):
        self.tris = []
        for face in obj.data.polygons:
            if len(face.vertices) == 3:
                offset = face.normal * offset_value
                face_verts = [
                    (obj.matrix_world @ Vector(obj.data.vertices[v].co)) + offset
                    for v in face.vertices
                ]
                for i in range(1, len(face_verts) - 1):
                    self.tris.extend([face_verts[0], face_verts[i], face_verts[i + 1]])

    def analyze_quads(self, obj, offset_value):
        self.quads = []
        for face in obj.data.polygons:
            if len(face.vertices) == 4:
                offset = face.normal * offset_value
                face_verts = [
                    (obj.matrix_world @ Vector(obj.data.vertices[v].co)) + offset
                    for v in face.vertices
                ]
                for i in range(1, len(face_verts) - 1):
                    self.quads.extend([face_verts[0], face_verts[i], face_verts[i + 1]])

    def analyze_ngons(self, obj, offset_value):
        self.ngons = []
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

        # Get only ngon faces and their normals
        ngon_faces = [f for f in bm.faces if len(f.verts) > 4]

        # Triangulate only ngons
        result = bmesh.ops.triangulate(bm, faces=ngon_faces, ngon_method="EAR_CLIP")

        # Get the new triangulated faces from the result
        for new_face in result["faces"]:
            offset = new_face.normal * offset_value
            for v in new_face.verts:
                vert_pos = (obj.matrix_world @ Vector(v.co)) + offset
                self.ngons.append(vert_pos)

        bm.free()

    def analyze_poles(self, obj):
        self.poles = []
        for vert in obj.data.vertices:
            # Get connected edges
            connected_edges = [
                e
                for e in obj.data.edges
                if vert.index in (e.vertices[0], e.vertices[1])
            ]

            # Check if vertex is a pole (not 4 edges)
            if len(connected_edges) > 4:
                vert_pos = obj.matrix_world @ vert.co
                self.poles.append(vert_pos)

    def analyze_singles(self, obj):
        self.singles = []
        for vert in obj.data.vertices:
            # Get connected edges
            connected_edges = [
                e
                for e in obj.data.edges
                if vert.index in (e.vertices[0], e.vertices[1])
            ]

            # Check if vertex has no connected edges
            if len(connected_edges) == 0:
                vert_pos = obj.matrix_world @ vert.co
                self.singles.append(vert_pos)

    def analyze_non_manifold_edges(self, obj):
        self.non_manifold_edges = []
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        
        for e in bm.edges:
            if not e.is_manifold:
                # Store both vertices of the edge for line drawing
                v1 = obj.matrix_world @ e.verts[0].co
                v2 = obj.matrix_world @ e.verts[1].co
                self.non_manifold_edges.extend([v1, v2])  # Store as pairs for LINE primitive
        
        bm.free()

    def analyze_non_manifold_verts(self, obj):
        self.non_manifold_verts = []
        bm = bmesh.new()
        bm.from_mesh(obj.data)

        for v in bm.verts:
            if not v.is_manifold:
                vert_pos = obj.matrix_world @ v.co
                self.non_manifold_verts.append(vert_pos)

        bm.free()
