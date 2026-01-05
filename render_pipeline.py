# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import gpu
import numpy as np
from typing import Dict, Optional, Set
from gpu_extras.batch import batch_for_shader
from bpy.types import Object
import logging

from .render_system import PrimitiveType, RenderData

logger = logging.getLogger(__name__)


class RenderPipeline:
    """High-performance rendering pipeline using built-in shaders and single-pass transforms"""
    
    def __init__(self):
        self.shader = None
        self.render_data: Dict[str, RenderData] = {}
        self.gpu_batches: Dict[str, any] = {}
        self.is_running = False
        self._handle = None
        self._data_object_name: Optional[str] = None
        self._is_dirty = False
    
    def _ensure_shader(self):
        """Initialize shader when GPU context is available"""
        if self.shader is None:
            # Blender 4.0+ uses 'SMOOTH_COLOR' instead of '3D_SMOOTH_COLOR'
            self.shader = gpu.shader.from_builtin("SMOOTH_COLOR")
    
    def start(self):
        """Start the render pipeline"""
        if self.is_running:
            return
            
        self.is_running = True
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw, (), "WINDOW", "POST_VIEW"
        )
        logger.debug("Render pipeline started")
    
    def stop(self):
        """Stop the render pipeline"""
        if not self.is_running:
            return
            
        self.is_running = False
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        
        self.clear_all()
        logger.debug("Render pipeline stopped")
    
    def clear_all(self):
        """Clear all render data"""
        self.render_data.clear()
        self.gpu_batches.clear()
        self._data_object_name = None
    
    def set_data_object(self, obj_name: str):
        """Set which object the current render data belongs to"""
        if self._data_object_name != obj_name:
            self.clear_all()
            self._data_object_name = obj_name
    
    def update_feature_data(self, feature: str, vertices: np.ndarray, 
                          normals: np.ndarray, colors: np.ndarray, primitive_type: PrimitiveType):
        """Update render data for a feature"""
        if len(vertices) == 0:
            if feature in self.render_data:
                del self.render_data[feature]
            if feature in self.gpu_batches:
                del self.gpu_batches[feature]
            return
        
        self.render_data[feature] = RenderData(
            vertices=vertices.astype(np.float32),
            normals=normals.astype(np.float32),
            colors=colors.astype(np.float32),
            primitive_type=primitive_type
        )
        self._is_dirty = True
    
    def _update_batches(self):
        """Rebuild GPU batches from render data with current offset applied locally"""
        if not self.render_data:
            return
            
        self._ensure_shader()
        if not self.shader:
            return
            
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        offset = props.overlay_offset
        
        for feature, data in self.render_data.items():
            # Apply offset in local space once
            # world_pos = matrix @ (pos + normal * offset)
            # This is correct if normal is in same space as pos.
            offset_verts = data.vertices + data.normals * offset
            
            try:
                batch = batch_for_shader(
                    self.shader,
                    data.primitive_type.value,
                    {
                        "pos": offset_verts,
                        "color": data.colors
                    }
                )
                self.gpu_batches[feature] = batch
            except Exception as e:
                logger.error(f"Failed to create batch for {feature}: {e}")
        
        self._is_dirty = False

    def _draw(self):
        """Main draw callback - uses GPU for world transform"""
        if not self.is_running:
            return
        
        obj = bpy.context.active_object
        if not obj or obj.type != "MESH":
            return
        
        if self._data_object_name != obj.name:
            return
            
        if not self.render_data:
            return
            
        # Rebuild batches if data changed or offset changed
        # Note: In a real implementation we'd check if offset changed specifically,
        # but here we can just rebuild if dirty.
        if self._is_dirty:
            self._update_batches()
            
        if not self.gpu_batches:
            return
            
        self._ensure_shader()
        if not self.shader:
            return
            
        # Calculate ModelViewProjectionMatrix
        region = bpy.context.region
        region_3d = bpy.context.region_data
        
        view_matrix = region_3d.view_matrix
        proj_matrix = region_3d.window_matrix
        model_matrix = obj.matrix_world
        
        # MVP = Project * View * Model
        mvp_matrix = proj_matrix @ view_matrix @ model_matrix
        
        self.shader.bind()
        try:
            self.shader.uniform_float("u_ModelViewProjectionMatrix", mvp_matrix)
        except ValueError:
            # Fallback for older versions or slightly different names
            try:
                self.shader.uniform_float("ModelViewProjectionMatrix", mvp_matrix)
            except ValueError as e:
                logger.error(f"Could not set MVP uniform: {e}")

        # Set GPU state
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.face_culling_set("BACK")
        gpu.state.point_size_set(props.overlay_vertex_radius)
        gpu.state.line_width_set(props.overlay_edge_width)
        
        # Draw all pre-calculated batches (fast!)
        for batch in self.gpu_batches.values():
            if batch:
                batch.draw(self.shader)
        
        # Reset GPU state
        gpu.state.blend_set("NONE")
        gpu.state.face_culling_set("NONE")
    
    def mark_geometry_dirty(self, feature: str = None):
        """Signal that batches need rebuilding"""
        self._is_dirty = True
    
    def mark_properties_dirty(self, feature: str = None):
        """Signal that batches need rebuilding (e.g. offset changed)"""
        self._is_dirty = True
