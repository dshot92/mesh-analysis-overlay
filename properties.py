# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
from bpy.props import BoolProperty, FloatVectorProperty, FloatProperty
from bpy.types import PropertyGroup
from . import handlers


class Mesh_Analysis_Overlay_Props(PropertyGroup):
    # FACES
    show_tri_faces: BoolProperty(
        name="Show Triangles",
        description="Show triangle overlays",
        default=False,
        update=handlers.property_update,
    )
    tri_faces_color: FloatVectorProperty(
        name="Triangles Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    show_quad_faces: BoolProperty(
        name="Show Quads",
        description="Show quad overlays",
        default=False,
        update=handlers.property_update,
    )
    quad_faces_color: FloatVectorProperty(
        name="Quads Color",
        subtype="COLOR",
        default=(0.0, 1.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    show_ngon_faces: BoolProperty(
        name="Show N-gons",
        description="Show n-gon overlays",
        default=False,
        update=handlers.property_update,
    )
    ngon_faces_color: FloatVectorProperty(
        name="N-gons Color",
        subtype="COLOR",
        default=(0.0, 0.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    show_non_planar_faces: BoolProperty(
        name="Show Non-Planar Faces",
        description="Show faces that are not planar",
        default=False,
        update=handlers.property_update,
    )
    non_planar_faces_color: FloatVectorProperty(
        name="Non-Planar Faces Color",
        subtype="COLOR",
        default=(1.0, 0.7, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    # EDGES
    show_non_manifold_e_edges: BoolProperty(
        name="Show Non-Manifold Edges",
        description="Show non-manifold edges",
        default=False,
        update=handlers.property_update,
    )
    non_manifold_e_edges_color: FloatVectorProperty(
        name="Non-Manifold Edges Color",
        subtype="COLOR",
        default=(1.0, 0.5, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    show_sharp_edges: BoolProperty(
        name="Show Sharp Edges",
        description="Show sharp edges",
        default=False,
        update=handlers.property_update,
    )
    sharp_edges_color: FloatVectorProperty(
        name="Sharp Edges Color",
        subtype="COLOR",
        default=(1.0, 1.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    show_seam_edges: BoolProperty(
        name="Show Seam Edges",
        description="Show UV seam edges",
        default=False,
        update=handlers.property_update,
    )
    seam_edges_color: FloatVectorProperty(
        name="Seam Edges Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    show_boundary_edges: BoolProperty(
        name="Show Boundary Edges",
        description="Display edges that are on mesh boundaries",
        default=False,
        update=handlers.property_update,
    )
    boundary_edges_color: FloatVectorProperty(
        name="Boundary Edges Color",
        subtype="COLOR",
        default=(0.0, 1.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    # VERTICES
    show_single_vertices: BoolProperty(
        name="Show Singles",
        description="Show single vertex indicators",
        default=False,
        update=handlers.property_update,
    )
    single_vertices_color: FloatVectorProperty(
        name="Singles Color",
        subtype="COLOR",
        default=(1.0, 1.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    show_non_manifold_v_vertices: BoolProperty(
        name="Show Non-Manifold Vertices",
        description="Show non-manifold vertices",
        default=False,
        update=handlers.property_update,
    )
    non_manifold_v_vertices_color: FloatVectorProperty(
        name="Non-Manifold Vertices Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.5, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    show_n_pole_vertices: BoolProperty(
        name="Show N-Poles (3 edges)",
        description="Show vertices with 3 edges",
        default=False,
        update=handlers.property_update,
    )
    n_pole_vertices_color: FloatVectorProperty(
        name="N-Poles Color",
        subtype="COLOR",
        default=(1.0, 0.5, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    show_e_pole_vertices: BoolProperty(
        name="Show E-Poles (5 edges)",
        description="Show vertices with 5 edges",
        default=False,
        update=handlers.property_update,
    )
    e_pole_vertices_color: FloatVectorProperty(
        name="E-Poles Color",
        subtype="COLOR",
        default=(0.0, 1.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    show_high_pole_vertices: BoolProperty(
        name="Show High-Poles (6+ edges)",
        description="Show vertices with 6 or more edges",
        default=False,
        update=handlers.property_update,
    )
    high_pole_vertices_color: FloatVectorProperty(
        name="High-Poles Color",
        subtype="COLOR",
        default=(1.0, 0.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    # SETTINGS VALUES
    overlay_offset: FloatProperty(
        name="Overlay Face Offset",
        description="Distance to offset the overlay faces",
        default=0.001,
        precision=4,
        update=handlers.offset_update,
    )
    overlay_vertex_radius: FloatProperty(
        name="Overlay Vertex Radius",
        description="Size of the overlay vertex indicators",
        default=5.0,
        min=1.0,
        max=50.0,
    )
    overlay_edge_width: FloatProperty(
        name="Overlay Edge Width",
        description="Width of the overlay edge indicators",
        default=5.0,
        min=1.0,
        max=10.0,
    )

    non_planar_threshold: FloatProperty(
        name="Non-Planar Threshold",
        description="Maximum angle deviation (in degrees) from face plane before considering it non-planar",
        default=0.0,
        min=0.0001,
        max=90.0,
        precision=4,
        update=handlers.non_planar_threshold_update,
    )


classes = (Mesh_Analysis_Overlay_Props,)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)
    bpy.types.Scene.Mesh_Analysis_Overlay_Properties = bpy.props.PointerProperty(
        type=Mesh_Analysis_Overlay_Props
    )


def unregister():
    bpy.utils.unregister_class(Mesh_Analysis_Overlay_Props)
    del bpy.types.Scene.Mesh_Analysis_Overlay_Properties
