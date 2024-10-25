import bpy
from mathutils import Vector


class MeshTopologyAnalyzer:
    def __init__(self):
        self.tris = []
        self.quads = []
        self.ngons = []
        self.poles = []

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
        for face in obj.data.polygons:
            if len(face.vertices) > 4:
                offset = face.normal * offset_value
                face_verts = [
                    (obj.matrix_world @ Vector(obj.data.vertices[v].co)) + offset
                    for v in face.vertices
                ]
                for i in range(1, len(face_verts) - 1):
                    self.ngons.extend([face_verts[0], face_verts[i], face_verts[i + 1]])
