![image](https://i.imgur.com/GGGHARb.jpeg)
# Mesh Analysis Overlay

> ## Performance Note
> Since the analysis can be a heavy process, it does not recalculate on every frame.
>
> Cached data per object allows editing the mesh in object/edit mode with no problems.
>
> **The overlay will be refreshed by disabling and re-enabling it or toggling EDIT mode on/off.**

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
- Degenerate faces

### Display Settings
- Color customization
- Opacity control
- Offset distance
- Element size
- Non-planar threshold control

### Selection Tools
- Quick selection buttons for each overlay type
  - Shift-click to add to selection
  - Ctrl-click to subtract from selection

### Analysis Information
- Statistics display for active overlays