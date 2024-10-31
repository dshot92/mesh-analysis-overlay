# SPDX-License-Identifier: GPL-3.0-or-later

FEATURE_DATA = {
    "faces": [
        {
            "id": "tri_faces",
            "label": "Triangles",
            "description": "Show triangle overlays",
            "default_color": (1.0, 0.0, 0.0, 0.5),
        },
        {
            "id": "quad_faces",
            "label": "Quads",
            "description": "Show quad overlays",
            "default_color": (0.0, 1.0, 0.0, 0.5),
        },
        {
            "id": "ngon_faces",
            "label": "N-Gons",
            "description": "Show n-gon overlays",
            "default_color": (0.0, 0.0, 1.0, 0.5),
        },
        {
            "id": "non_planar_faces",
            "label": "Non-Planar Faces",
            "description": "Show faces that are not planar",
            "default_color": (1.0, 0.7, 0.0, 0.5),
        },
        {
            "id": "degenerate_faces",
            "label": "Degenerate Faces",
            "description": "Show faces with zero area or invalid geometry",
            "default_color": (1.0, 0.0, 0.5, 0.5),
        },
    ],
    "edges": [
        {
            "id": "non_manifold_e_edges",
            "label": "Non-Manifold Edges",
            "description": "Show non-manifold edges",
            "default_color": (1.0, 0.5, 0.0, 0.5),
        },
        {
            "id": "sharp_edges",
            "label": "Sharp Edges",
            "description": "Show sharp edges",
            "default_color": (1.0, 1.0, 1.0, 0.5),
        },
        {
            "id": "seam_edges",
            "label": "Seam Edges",
            "description": "Show UV seam edges",
            "default_color": (1.0, 0.0, 0.0, 0.5),
        },
        {
            "id": "boundary_edges",
            "label": "Boundary Edges",
            "description": "Display edges that are on mesh boundaries",
            "default_color": (0.0, 1.0, 1.0, 0.5),
        },
    ],
    "vertices": [
        {
            "id": "single_vertices",
            "label": "Single Vertices",
            "description": "Show single vertex indicators",
            "default_color": (1.0, 1.0, 0.0, 0.5),
        },
        {
            "id": "non_manifold_v_vertices",
            "label": "Non-Manifold Vertices",
            "description": "Show non-manifold vertices",
            "default_color": (1.0, 0.0, 0.5, 0.5),
        },
        {
            "id": "n_pole_vertices",
            "label": "N-Poles (3)",
            "description": "Show vertices with 3 edges",
            "default_color": (1.0, 0.5, 0.0, 0.5),
        },
        {
            "id": "e_pole_vertices",
            "label": "E-Poles (5)",
            "description": "Show vertices with 5 edges",
            "default_color": (0.0, 1.0, 1.0, 0.5),
        },
        {
            "id": "high_pole_vertices",
            "label": "High-Poles (6+)",
            "description": "Show vertices with 6 or more edges",
            "default_color": (1.0, 0.0, 1.0, 0.5),
        },
    ],
}
