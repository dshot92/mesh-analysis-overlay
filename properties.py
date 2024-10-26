# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

import bpy

from bpy.props import BoolProperty, FloatVectorProperty, FloatProperty
from bpy.types import PropertyGroup


class Mesh_Analysis_Overlay_Props(PropertyGroup):

    # FACES
    show_tris: BoolProperty(
        name="Show Triangles",
        description="Show triangle overlays",
        default=True,
    )
    tris_color: FloatVectorProperty(
        name="Triangles Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    show_quads: BoolProperty(
        name="Show Quads",
        description="Show quad overlays",
        default=True,
    )
    quads_color: FloatVectorProperty(
        name="Quads Color",
        subtype="COLOR",
        default=(0.0, 1.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    show_ngons: BoolProperty(
        name="Show N-gons",
        description="Show n-gon overlays",
        default=True,
    )
    ngons_color: FloatVectorProperty(
        name="N-gons Color",
        subtype="COLOR",
        default=(0.0, 0.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )

    # EDGES
    show_non_manifold_edges: BoolProperty(
        name="Show Non-Manifold Edges",
        description="Show non-manifold edges",
        default=True,
    )
    non_manifold_edges_color: FloatVectorProperty(
        name="Non-Manifold Edges Color",
        subtype="COLOR",
        default=(1.0, 0.5, 0.0, 0.5),  # Orange with 0.5 alpha
        size=4,
        min=0.0,
        max=1.0,
    )

    show_sharp_edges: BoolProperty(
        name="Show Sharp Edges",
        description="Show sharp edges",
        default=True,
    )
    sharp_edges_color: FloatVectorProperty(
        name="Sharp Edges Color",
        subtype="COLOR",
        default=(1.0, 1.0, 1.0, 0.5),  # White with 0.5 alpha
        size=4,
        min=0.0,
        max=1.0,
    )

    show_seam_edges: BoolProperty(
        name="Show Seam Edges",
        description="Show UV seam edges",
        default=True,
    )
    seam_edges_color: FloatVectorProperty(
        name="Seam Edges Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.0, 0.5),  # Red with 0.5 alpha
        size=4,
        min=0.0,
        max=1.0,
    )

    ### VERTICES
    show_singles: BoolProperty(
        name="Show Singles",
        description="Show single vertex indicators",
        default=True,
    )
    singles_color: FloatVectorProperty(
        name="Singles Color",
        subtype="COLOR",
        default=(1.0, 1.0, 0.0, 0.5),  # Yellow with 0.5 alpha
        size=4,
        min=0.0,
        max=1.0,
    )

    show_non_manifold_verts: BoolProperty(
        name="Show Non-Manifold Vertices",
        description="Show non-manifold vertices",
        default=True,
    )
    non_manifold_verts_color: FloatVectorProperty(
        name="Non-Manifold Vertices Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.5, 0.5),  # Pink with 0.5 alpha
        size=4,
        min=0.0,
        max=1.0,
    )

    show_n_poles: BoolProperty(
        name="Show N-Poles (3 edges)",
        description="Show vertices with 3 edges",
        default=True,
    )
    n_poles_color: FloatVectorProperty(
        name="N-Poles Color",
        subtype="COLOR",
        default=(1.0, 0.5, 0.0, 0.5),  # Orange
        size=4,
        min=0.0,
        max=1.0,
    )

    show_e_poles: BoolProperty(
        name="Show E-Poles (5 edges)",
        description="Show vertices with 5 edges",
        default=True,
    )
    e_poles_color: FloatVectorProperty(
        name="E-Poles Color",
        subtype="COLOR",
        default=(0.0, 1.0, 1.0, 0.5),  # Cyan
        size=4,
        min=0.0,
        max=1.0,
    )

    show_high_poles: BoolProperty(
        name="Show High-Poles (6+ edges)",
        description="Show vertices with 6 or more edges",
        default=True,
    )
    high_poles_color: FloatVectorProperty(
        name="High-Poles Color",
        subtype="COLOR",
        default=(1.0, 0.0, 1.0, 0.5),  # Magenta
        size=4,
        min=0.0,
        max=1.0,
    )


    # SETTINGS VALUES
    overlay_face_offset: FloatProperty(
        name="Overlay Face Offset",
        description="Distance to offset the overlay faces",
        default=0.001,
        precision=4,
    )
    overlay_vertex_radius: FloatProperty(
        name="Overlay Vertex Radius",
        description="Size of the overlay vertex indicators",
        default=10.0,
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
