#!/usr/bin/env python3
"""
Test script to verify color property changes work without triggering reanalysis.
This script can be run in Blender's scripting workspace to test the implementation.
"""

import bpy
import time

def test_color_changes():
    """Test that color changes update in real-time without reanalysis"""
    
    # Get the mesh analysis overlay properties
    props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
    
    print("Testing color property changes...")
    
    # Test 1: Change triangle face color
    print("\n1. Testing triangle face color change...")
    original_color = props.tri_faces_color.copy()
    test_color = (1.0, 0.0, 1.0, 0.8)  # Bright magenta
    
    props.tri_faces_color = test_color
    print(f"   Changed tri_faces_color to {test_color}")
    
    # Wait a moment for the update to process
    time.sleep(0.1)
    
    # Test 2: Change edge color
    print("\n2. Testing edge color change...")
    original_edge_color = props.non_manifold_e_edges_color.copy()
    test_edge_color = (0.0, 1.0, 1.0, 0.9)  # Cyan
    
    props.non_manifold_e_edges_color = test_edge_color
    print(f"   Changed non_manifold_e_edges_color to {test_edge_color}")
    
    # Wait a moment for the update to process
    time.sleep(0.1)
    
    # Test 3: Change vertex color
    print("\n3. Testing vertex color change...")
    original_vertex_color = props.single_vertices_color.copy()
    test_vertex_color = (1.0, 1.0, 0.0, 1.0)  # Yellow
    
    props.single_vertices_color = test_vertex_color
    print(f"   Changed single_vertices_color to {test_vertex_color}")
    
    # Test 4: Verify non-planar threshold still triggers reanalysis
    print("\n4. Testing non-planar threshold change (should trigger reanalysis)...")
    original_threshold = props.non_planar_threshold
    test_threshold = 5.0
    
    props.non_planar_threshold = test_threshold
    print(f"   Changed non_planar_threshold to {test_threshold}")
    print("   This should trigger cache invalidation and reanalysis")
    
    # Restore original values
    print("\n5. Restoring original values...")
    props.tri_faces_color = original_color
    props.non_manifold_e_edges_color = original_edge_color
    props.single_vertices_color = original_vertex_color
    props.non_planar_threshold = original_threshold
    
    print("\n✅ Color property test completed!")
    print("   - Color changes should update immediately without reanalysis")
    print("   - Threshold changes should trigger reanalysis")
    print("   - All changes should be visible in the 3D viewport")

if __name__ == "__main__":
    # Check if we're in Blender and have a mesh selected
    if bpy.context.selected_objects and any(obj.type == "MESH" for obj in bpy.context.selected_objects):
        test_color_changes()
    else:
        print("❌ Please select at least one mesh object before running this test.")
        print("   Also ensure the Mesh Analysis Overlay is enabled and some features are active.")
