# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

import bpy
from .gpu_drawer import GPUDrawer


class GPU_Topology_Overlay_Props(bpy.types.PropertyGroup):

    # VISIBILITY TOGGLES
    show_tris: bpy.props.BoolProperty(
        name="Show Triangles",
        description="Show triangle overlays",
        default=True,
    )
    show_quads: bpy.props.BoolProperty(
        name="Show Quads",
        description="Show quad overlays",
        default=True,
    )
    show_ngons: bpy.props.BoolProperty(
        name="Show N-gons",
        description="Show n-gon overlays",
        default=True,
    )
    show_poles: bpy.props.BoolProperty(
        name="Show Poles",
        description="Show pole indicators",
        default=True,
    )
    show_singles: bpy.props.BoolProperty(
        name="Show Singles",
        description="Show single vertex indicators",
        default=True,
    )
    show_non_manifold_verts: bpy.props.BoolProperty(
        name="Show Non-Manifold Vertices",
        description="Show non-manifold vertices",
        default=True,
    )
    show_non_manifold_edges: bpy.props.BoolProperty(
        name="Show Non-Manifold Edges",
        description="Show non-manifold edges",
        default=True,
    )

    # COLORS
    tris_color: bpy.props.FloatVectorProperty(
        name="Triangles Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )
    quads_color: bpy.props.FloatVectorProperty(
        name="Quads Color",
        subtype="COLOR",
        default=(0.0, 1.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )
    ngons_color: bpy.props.FloatVectorProperty(
        name="N-gons Color",
        subtype="COLOR",
        default=(0.0, 0.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
    )
    poles_color: bpy.props.FloatVectorProperty(
        name="Poles Color",
        subtype="COLOR",
        default=(1.0, 0.0, 1.0, 0.5),  # Magenta with 0.5 alpha
        size=4,
        min=0.0,
        max=1.0,
    )
    singles_color: bpy.props.FloatVectorProperty(
        name="Singles Color",
        subtype="COLOR",
        default=(1.0, 1.0, 0.0, 0.5),  # Yellow with 0.5 alpha
        size=4,
        min=0.0,
        max=1.0,
    )
    non_manifold_verts_color: bpy.props.FloatVectorProperty(
        name="Non-Manifold Vertices Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.5, 0.5),  # Pink with 0.5 alpha
        size=4,
        min=0.0,
        max=1.0,
    )
    non_manifold_edges_color: bpy.props.FloatVectorProperty(
        name="Non-Manifold Edges Color",
        subtype="COLOR",
        default=(1.0, 0.5, 0.0, 0.5),  # Orange with 0.5 alpha
        size=4,
        min=0.0,
        max=1.0,
    )

    # SETTINGS VALUES
    overlay_face_offset: bpy.props.FloatProperty(
        name="Overlay Face Offset",
        description="Distance to offset the overlay faces",
        default=0.001,
        # min=0.0,
        # max=1.0,
        precision=4,
        # update=lambda self, context: GPUDrawer.update_visibility(),  # Fix the callback
    )
    overlay_vertex_radius: bpy.props.FloatProperty(
        name="Overlay Vertex Radius",
        description="Size of the overlay vertex indicators",
        default=10.0,
        min=1.0,
        max=50.0,
    )

    overlay_edge_width: bpy.props.FloatProperty(
        name="Overlay Edge Width",
        description="Width of the overlay edge indicators",
        default=5.0,
        min=1.0,
        max=10.0,
    )


classes = (GPU_Topology_Overlay_Props,)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)
    bpy.types.Scene.GPU_Topology_Overlay_Properties = bpy.props.PointerProperty(
        type=GPU_Topology_Overlay_Props
    )


def unregister():
    bpy.utils.unregister_class(GPU_Topology_Overlay_Props)
    del bpy.types.Scene.GPU_Topology_Overlay_Properties
