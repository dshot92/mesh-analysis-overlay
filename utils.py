# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh


def get_updated_bmesh_from_depsgraph(obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph) -> bmesh.types.BMesh:
    """Get the most updated mesh from depsgraph"""
    if obj.mode == "EDIT":
        # Check for Geometry Nodes in Edit Mode
        has_modifiers = len(obj.modifiers) > 0
        if has_modifiers:
            # For edit mode with modifiers, we need to get the live edit mesh
            # and apply modifiers to it for real-time updates
            try:
                # Get the live edit mesh first
                edit_bm = bmesh.from_edit_mesh(obj.data)
                edit_bm.edges.ensure_lookup_table()
                edit_bm.faces.ensure_lookup_table()
                edit_bm.verts.ensure_lookup_table()
                
                # Create a copy to work with
                bm = bmesh.new()
                bm.from_mesh(edit_bm)
                
                # Apply modifiers to the copy for real-time effect
                # Note: This is a simplified approach - for full modifier support,
                # we'd need to manually apply each modifier to the bmesh
                # For now, return the edit mesh which captures real-time changes
                
                return bm
            except:
                # If anything fails, fall back to edit mesh
                bm = bmesh.from_edit_mesh(obj.data)
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
                bm.verts.ensure_lookup_table()
                return bm
        else:
            # Direct BMesh extraction for real-time tracking
            bm = bmesh.from_edit_mesh(obj.data)
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            return bm
    else:
        # OBJECT mode - use evaluated mesh from depsgraph
        evaluated_obj = obj.evaluated_get(depsgraph)
        mesh = evaluated_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        
        try:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            return bm
        finally:
            evaluated_obj.to_mesh_clear()
