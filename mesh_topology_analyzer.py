import bpy
from mathutils import Vector


class MeshTopologyAnalyzer:
    def __init__(self):
        self.tris = []
        self.quads = []
        self.ngons = []

    def analyze_mesh(self, obj):
        if not obj or obj.type != "MESH":
            return

        props = bpy.context.scene.GPU_Topology_Overlay_Properties

        # Get offset from scene property
        offset_value = props.poly_offset

        # Clear previous data
        self.tris = []
        self.quads = []
        self.ngons = []

        # Process each type only if visible
        if props.show_tris:
            for face in obj.data.polygons:
                if len(face.vertices) == 3:
                    offset = face.normal * offset_value
                    face_verts = [
                        (obj.matrix_world @ Vector(obj.data.vertices[v].co)) + offset
                        for v in face.vertices
                    ]
                    for i in range(1, len(face_verts) - 1):
                        self.tris.extend(
                            [face_verts[0], face_verts[i], face_verts[i + 1]]
                        )

        if props.show_quads:
            for face in obj.data.polygons:
                if len(face.vertices) == 4:
                    offset = face.normal * offset_value
                    face_verts = [
                        (obj.matrix_world @ Vector(obj.data.vertices[v].co)) + offset
                        for v in face.vertices
                    ]
                    for i in range(1, len(face_verts) - 1):
                        self.quads.extend(
                            [face_verts[0], face_verts[i], face_verts[i + 1]]
                        )

        if props.show_ngons:
            for face in obj.data.polygons:
                if len(face.vertices) > 4:
                    offset = face.normal * offset_value
                    face_verts = [
                        (obj.matrix_world @ Vector(obj.data.vertices[v].co)) + offset
                        for v in face.vertices
                    ]
                    for i in range(1, len(face_verts) - 1):
                        self.ngons.extend(
                            [face_verts[0], face_verts[i], face_verts[i + 1]]
                        )
