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

    def get_visible_data(
        self, show_tris=True, show_quads=True, show_ngons=True, colors=None
    ):
        vertices = []
        vert_colors = []

        if colors is None:
            colors = {
                "tris": (1, 0, 0, 0.5),
                "quads": (0, 0, 1, 0.5),
                "ngons": (0, 1, 0, 0.5),
            }

        if show_tris:
            vertices.extend(self.tris)
            vert_colors.extend([colors["tris"]] * len(self.tris))
        if show_quads:
            vertices.extend(self.quads)
            vert_colors.extend([colors["quads"]] * len(self.quads))
        if show_ngons:
            vertices.extend(self.ngons)
            vert_colors.extend([colors["ngons"]] * len(self.ngons))

        return {"vertices": vertices, "colors": vert_colors}
