# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import gpu
import numpy as np
from typing import Dict, Optional, Set, List
from gpu_extras.batch import batch_for_shader
from bpy.types import Object
import logging

from .render_system import PrimitiveType, RenderData

logger = logging.getLogger(__name__)


class RenderPipeline:
    """High-performance rendering pipeline supporting multiple selected objects"""
    
    def __init__(self):
        self.shader = None
        # Nested dict: obj_name -> feature_id -> RenderData
        self.render_data: Dict[str, Dict[str, RenderData]] = {}
        # Nested dict: obj_name -> feature_id -> GPU Batch
        self.gpu_batches: Dict[str, Dict[str, any]] = {}
        self.is_running = False
        self._handle = None
        # Track objects that need batch rebuilding
        self._dirty_objects: Set[str] = set()
    
    def _ensure_shader(self):
        """Initialize shader when GPU context is available"""
        if self.shader is None:
            # Blender 4.0+
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
        self._dirty_objects.clear()

    def clear_object_data(self, obj_name: str):
        """Remove data for a specific object"""
        if obj_name in self.render_data:
            del self.render_data[obj_name]
        if obj_name in self.gpu_batches:
            del self.gpu_batches[obj_name]
        if obj_name in self._dirty_objects:
            self._dirty_objects.remove(obj_name)
    
    def update_feature_data(self, obj_name: str, feature: str, vertices: np.ndarray, 
                          normals: np.ndarray, colors: np.ndarray, primitive_type: PrimitiveType):
        """Update render data for a specific object and feature"""
        if obj_name not in self.render_data:
            self.render_data[obj_name] = {}
        
        if len(vertices) == 0:
            if feature in self.render_data[obj_name]:
                del self.render_data[obj_name][feature]
            if obj_name in self.gpu_batches and feature in self.gpu_batches[obj_name]:
                del self.gpu_batches[obj_name][feature]
            return
        
        self.render_data[obj_name][feature] = RenderData(
            vertices=vertices.astype(np.float32),
            normals=normals.astype(np.float32),
            colors=colors.astype(np.float32),
            primitive_type=primitive_type
        )
        self._dirty_objects.add(obj_name)
    
    def _update_batches(self):
        """Rebuild GPU batches for all dirty objects"""
        if not self._dirty_objects:
            return
            
        self._ensure_shader()
        if not self.shader:
            return
            
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        offset = props.overlay_offset
        
        for obj_name in list(self._dirty_objects):
            if obj_name not in self.render_data:
                continue
            
            if obj_name not in self.gpu_batches:
                self.gpu_batches[obj_name] = {}
            
            for feature, data in self.render_data[obj_name].items():
                # Apply offset in local space
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
                    self.gpu_batches[obj_name][feature] = batch
                except Exception as e:
                    logger.error(f"Failed to create batch for {obj_name}:{feature}: {e}")
        
        self._dirty_objects.clear()

    def _draw(self):
        """Main draw callback - iterates over all selected mesh objects"""
        if not self.is_running:
            return
        
        selected_objs = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
        if not selected_objs:
            return
            
        # Ensure batches are built for everything that needs it
        if self._dirty_objects:
            self._update_batches()
            
        self._ensure_shader()
        if not self.shader:
            return
        
        region_3d = bpy.context.region_data
        view_matrix = region_3d.view_matrix
        proj_matrix = region_3d.window_matrix
        
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        
        # Shader bind once
        self.shader.bind()

        # Set GPU state
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.face_culling_set("BACK")
        gpu.state.point_size_set(props.overlay_vertex_radius)
        gpu.state.line_width_set(props.overlay_edge_width)
        
        # Set uniform and draw for each selected object
        for obj in selected_objs:
            if obj.name not in self.gpu_batches:
                continue
                
            # MVP = Project * View * Model
            mvp_matrix = proj_matrix @ view_matrix @ obj.matrix_world
            
            # Set MVP uniform
            try:
                self.shader.uniform_float("u_ModelViewProjectionMatrix", mvp_matrix)
            except ValueError:
                try:
                    self.shader.uniform_float("ModelViewProjectionMatrix", mvp_matrix)
                except ValueError:
                    pass
            
            # Draw all batches for this object
            for batch in self.gpu_batches[obj.name].values():
                if batch:
                    batch.draw(self.shader)
        
        # Reset GPU state
        gpu.state.blend_set("NONE")
        gpu.state.face_culling_set("NONE")
    
    def mark_geometry_dirty(self, feature: str = None):
        """Signal that batches need rebuilding for all objects"""
        for obj_name in self.render_data:
            self._dirty_objects.add(obj_name)
    
    def mark_properties_dirty(self, feature: str = None):
        """Signal that batches need rebuilding for all objects"""
        for obj_name in self.render_data:
            self._dirty_objects.add(obj_name)
