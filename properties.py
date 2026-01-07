# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
from bpy.props import (
    BoolProperty,
    FloatVectorProperty,
    FloatProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup

from . import handlers


class Mesh_Analysis_Overlay_Props(PropertyGroup):
    # FACE PROPERTIES
    tri_faces_enabled: BoolProperty(
        name="Show Triangles",
        description="Show triangle overlays",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    tri_faces_color: FloatVectorProperty(
        name="Triangles Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    quad_faces_enabled: BoolProperty(
        name="Show Quads",
        description="Show quad overlays",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    quad_faces_color: FloatVectorProperty(
        name="Quads Color",
        subtype="COLOR",
        default=(0.0, 1.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    ngon_faces_enabled: BoolProperty(
        name="Show N-Gons",
        description="Show n-gon overlays",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    ngon_faces_color: FloatVectorProperty(
        name="N-Gons Color",
        subtype="COLOR",
        default=(0.0, 0.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    non_planar_faces_enabled: BoolProperty(
        name="Show Non-Planar Faces",
        description="Show faces that are not planar",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    non_planar_faces_color: FloatVectorProperty(
        name="Non-Planar Faces Color",
        subtype="COLOR",
        default=(1.0, 0.7, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    degenerate_faces_enabled: BoolProperty(
        name="Show Degenerate Faces",
        description="Show faces with zero area or invalid geometry",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    degenerate_faces_color: FloatVectorProperty(
        name="Degenerate Faces Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.5, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    # EDGE PROPERTIES
    non_manifold_e_edges_enabled: BoolProperty(
        name="Show Non-Manifold Edges",
        description="Show non-manifold edges",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    non_manifold_e_edges_color: FloatVectorProperty(
        name="Non-Manifold Edges Color",
        subtype="COLOR",
        default=(1.0, 0.5, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    sharp_edges_enabled: BoolProperty(
        name="Show Sharp Edges",
        description="Show sharp edges",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    sharp_edges_color: FloatVectorProperty(
        name="Sharp Edges Color",
        subtype="COLOR",
        default=(1.0, 1.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    seam_edges_enabled: BoolProperty(
        name="Show Seam Edges",
        description="Show UV seam edges",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    seam_edges_color: FloatVectorProperty(
        name="Seam Edges Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    boundary_edges_enabled: BoolProperty(
        name="Show Boundary Edges",
        description="Display edges that are on mesh boundaries",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    boundary_edges_color: FloatVectorProperty(
        name="Boundary Edges Color",
        subtype="COLOR",
        default=(0.0, 1.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    # VERTEX PROPERTIES
    single_vertices_enabled: BoolProperty(
        name="Show Single Vertices",
        description="Show single vertex indicators",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    single_vertices_color: FloatVectorProperty(
        name="Single Vertices Color",
        subtype="COLOR",
        default=(1.0, 1.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    non_manifold_v_vertices_enabled: BoolProperty(
        name="Show Non-Manifold Vertices",
        description="Show non-manifold vertices",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    non_manifold_v_vertices_color: FloatVectorProperty(
        name="Non-Manifold Vertices Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.5, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    n_pole_vertices_enabled: BoolProperty(
        name="Show N-Poles (3)",
        description="Show vertices with 3 edges",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    n_pole_vertices_color: FloatVectorProperty(
        name="N-Poles (3) Color",
        subtype="COLOR",
        default=(1.0, 0.5, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    e_pole_vertices_enabled: BoolProperty(
        name="Show E-Poles (5)",
        description="Show vertices with 5 edges",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    e_pole_vertices_color: FloatVectorProperty(
        name="E-Poles (5) Color",
        subtype="COLOR",
        default=(0.0, 1.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )
    
    high_pole_vertices_enabled: BoolProperty(
        name="Show High-Poles (6+)",
        description="Show vertices with 6 or more edges",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    high_pole_vertices_color: FloatVectorProperty(
        name="High-Poles (6+) Color",
        subtype="COLOR",
        default=(1.0, 0.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_offset,
    )

    # SETTINGS VALUES
    overlay_offset: FloatProperty(
        name="Overlay Face Offset",
        description="Distance to offset the overlay faces",
        default=0.01,
        precision=4,
        update=handlers.update_overlay_offset,
    )
    overlay_vertex_radius: FloatProperty(
        name="Overlay Vertex Radius",
        description="Size of the overlay vertex indicators",
        default=5.0,
        min=1.0,
        max=50.0,
        update=handlers.update_overlay_offset,
    )
    overlay_edge_width: FloatProperty(
        name="Overlay Edge Width",
        description="Width of the overlay edge indicators",
        default=5.0,
        min=1.0,
        max=10.0,
        update=handlers.update_overlay_offset,
    )

    non_planar_threshold: FloatProperty(
        name="Non-Planar Threshold",
        description="Maximum angle deviation (in degrees) from face plane before considering it non-planar",
        default=0.0,
        min=0.0001,
        max=90.0,
        precision=4,
        update=handlers.update_non_planar_threshold,
    )


def register():
    bpy.utils.register_class(Mesh_Analysis_Overlay_Props)
    bpy.types.Scene.Mesh_Analysis_Overlay_Properties = PointerProperty(
        type=Mesh_Analysis_Overlay_Props
    )


def unregister():
    del bpy.types.Scene.Mesh_Analysis_Overlay_Properties
    bpy.utils.unregister_class(Mesh_Analysis_Overlay_Props)
