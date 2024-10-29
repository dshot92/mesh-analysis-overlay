# Mesh Analysis Overlay

Mesh analysis visualization for Blender.

![image](https://i.imgur.com/1uex1bC.jpeg)

## Performance Note
Since the analysis can be a heavy process, it does not recalculate on every frame or while moving the object or editing the mesh in Edit Mode.

To refresh the cache overlays, toggle the overlay off and on again while in Object Mode.

## Overlays

### Vertex Overlays
- Single vertices
- Non-manifold vertices
- N-Poles (3 edges)
- E-Poles (5 edges)
- High Poles (6+ edges)

### Edge Overlays
- Non-manifold edges
- Sharp edges
- Seam edges
- Boundary edges

### Face Overlays
- Triangles
- Quads
- N-gons (>4 sides)
- Non-planar faces

### Display Settings
- Color customization
- Opacity control
- Offset distance
- Element size

