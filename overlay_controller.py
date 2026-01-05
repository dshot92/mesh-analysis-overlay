# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from bpy.types import Object
from dataclasses import dataclass
import logging

from .analysis_engine import MeshAnalysisEngine, AnalysisResult, FeatureType
from .render_pipeline import RenderPipeline, PrimitiveType
from .feature_data import FEATURE_DATA

logger = logging.getLogger(__name__)


@dataclass
class GeometryProcessor:
    """Convert analysis results to GPU-ready geometry using fast NumPy operations"""
    
    @staticmethod
    def _get_mesh_data(mesh: bpy.types.Mesh) -> Dict[str, np.ndarray]:
        """Extract all necessary mesh data as NumPy arrays once"""
        v_count = len(mesh.vertices)
        verts = np.empty(v_count * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", verts)
        normals = np.empty(v_count * 3, dtype=np.float32)
        mesh.vertices.foreach_get("normal", normals)
        
        edge_v_indices = np.empty(len(mesh.edges) * 2, dtype=np.int32)
        mesh.edges.foreach_get("vertices", edge_v_indices)
        
        face_normals = np.empty(len(mesh.polygons) * 3, dtype=np.float32)
        mesh.polygons.foreach_get("normal", face_normals)
        
        return {
            "verts": verts.reshape((-1, 3)),
            "normals": normals.reshape((-1, 3)),
            "edge_v_indices": edge_v_indices.reshape((-1, 2)),
            "face_normals": face_normals.reshape((-1, 3))
        }

    @staticmethod
    def process_vertices(indices: np.ndarray, color: Tuple[float, float, float, float], 
                        mesh_data: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Process vertex indices to GPU-ready data"""
        if len(indices) == 0:
            return np.array([]), np.array([]), np.array([])
        
        verts = mesh_data["verts"]
        normals = mesh_data["normals"]
        
        feature_verts = verts[indices]
        feature_normals = normals[indices]
        feature_colors = np.full((len(indices), 4), color, dtype=np.float32)
        
        return feature_verts, feature_normals, feature_colors
    
    @staticmethod
    def process_edges(indices: np.ndarray, color: Tuple[float, float, float, float], 
                     mesh_data: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Process edge indices to GPU-ready line data"""
        if len(indices) == 0:
            return np.array([]), np.array([]), np.array([])
        
        verts = mesh_data["verts"]
        normals = mesh_data["normals"]
        edge_v_indices = mesh_data["edge_v_indices"]
        
        # Select indices for the requested edges
        selected_v_indices = edge_v_indices[indices].flatten()
        
        feature_verts = verts[selected_v_indices]
        feature_normals = normals[selected_v_indices]
        feature_colors = np.full((len(feature_verts), 4), color, dtype=np.float32)
        
        return feature_verts, feature_normals, feature_colors
    
    @staticmethod
    def process_faces(obj: Object, indices: np.ndarray, color: Tuple[float, float, float, float], 
                     mesh_data: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Process face indices to GPU-ready triangle data using loop_triangles"""
        if len(indices) == 0:
            return np.array([]), np.array([]), np.array([])
        
        mesh = obj.data
        verts = mesh_data["verts"]
        normals = mesh_data["normals"]
        
        # Ensure loop triangles are calculated
        mesh.calc_loop_triangles()
        
        # Get polygon index for each loop triangle
        poly_indices = np.empty(len(mesh.loop_triangles), dtype=np.int32)
        mesh.loop_triangles.foreach_get("polygon_index", poly_indices)
        
        # Create mask for triangles belonging to selected faces
        mask = np.isin(poly_indices, indices)
        
        # Get vertex indices for the selected triangles
        # foreach_get returns a flat array of all 3 vertices for all loop_triangles
        all_tri_v_indices = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get("vertices", all_tri_v_indices)
        all_tri_v_indices = all_tri_v_indices.reshape((-1, 3))
        
        # Select triangles and flatten to get vertex stream
        selected_v_indices = all_tri_v_indices[mask].flatten()
        
        if len(selected_v_indices) == 0:
            return np.array([]), np.array([]), np.array([])
            
        feature_verts = verts[selected_v_indices]
        
        # Use vertex normals instead of face normals to keep faces connected (a "shell" look)
        feature_normals = normals[selected_v_indices]
        
        feature_colors = np.full((len(feature_verts), 4), color, dtype=np.float32)
        
        return feature_verts, feature_normals, feature_colors


class OverlayController:
    """Main controller coordinating analysis and rendering"""
    
    def __init__(self):
        self.analysis_engine = MeshAnalysisEngine()
        self.render_pipeline = RenderPipeline()
        self.geometry_processor = GeometryProcessor()
        
        self.current_object: Optional[Object] = None
        self.enabled_features: Set[str] = set()
        self.feature_colors: Dict[str, Tuple[float, float, float, float]] = {}
        
        self.is_running = False
    
    def start(self):
        """Start the overlay system"""
        if self.is_running:
            return
        
        self.is_running = True
        self.render_pipeline.start()
        logger.debug("Overlay controller started")
    
    def stop(self):
        """Stop the overlay system"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.render_pipeline.stop()
        self.current_object = None
        logger.debug("Overlay controller stopped")
    
    def update_overlay(self, obj: Optional[Object] = None):
        """Update overlay for current or specified object"""
        if not self.is_running:
            return
        
        if obj is None:
            obj = bpy.context.active_object
        
        if not obj or obj.type != "MESH":
            return
        
        logger.debug(f"update_overlay called: obj={obj.name}")
        
        # Check if object changed - clear old data
        if self.current_object != obj:
            self.current_object = obj
            self.analysis_engine.invalidate_cache(obj.name)
            self.render_pipeline.clear_all()
        
        # Tell render pipeline which object this data is for
        self.render_pipeline.set_data_object(obj.name)

        # Get enabled features and colors
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        enabled_features = []
        feature_colors = {}
        
        for category, features in FEATURE_DATA.items():
            for feature in features:
                feature_id = feature["id"]
                if getattr(props, f"{feature_id}_enabled", False):
                    enabled_features.append(feature_id)
                    feature_colors[feature_id] = tuple(getattr(props, f"{feature_id}_color"))
        
        logger.debug(f"Enabled features: {enabled_features}")
        
        # Analyze mesh for geometry changes
        analysis_results = self.analysis_engine.analyze_mesh(obj, enabled_features)
        
        logger.debug(f"Analysis results: {list(analysis_results.keys())}")
        
        # Optimization: Fetch base mesh data once
        mesh_data = self.geometry_processor._get_mesh_data(obj.data)
        
        for feature_id, result in analysis_results.items():
            if feature_id not in feature_colors:
                continue
            
            color = feature_colors[feature_id]
            vertices, normals, colors = [], [], []
            
            if result.feature_type == FeatureType.VERTEX:
                vertices, normals, colors = self.geometry_processor.process_vertices(
                    result.indices, color, mesh_data
                )
                primitive_type = PrimitiveType.POINTS
                
            elif result.feature_type == FeatureType.EDGE:
                vertices, normals, colors = self.geometry_processor.process_edges(
                    result.indices, color, mesh_data
                )
                primitive_type = PrimitiveType.LINES
                
            elif result.feature_type == FeatureType.FACE:
                vertices, normals, colors = self.geometry_processor.process_faces(
                    obj, result.indices, color, mesh_data
                )
                primitive_type = PrimitiveType.TRIS
            
            logger.debug(f"Processed {feature_id}: {len(vertices)} vertices")
            
            # Update render pipeline
            if len(vertices) > 0:
                self.render_pipeline.update_feature_data(
                    feature_id, vertices, normals, colors, primitive_type
                )
    
    def mark_dirty(self, feature: Optional[str] = None, dirty_type: str = "geometry"):
        """Mark features as dirty"""
        if feature:
            self.render_pipeline.mark_geometry_dirty(feature)
        else:
            self.render_pipeline.mark_geometry_dirty()
    
    def handle_geometry_change(self, obj: Object):
        """Handle geometry changes"""
        if not self.is_running:
            return
        
        self.analysis_engine.invalidate_cache(obj.name)
        self.mark_dirty()
        
        if obj == self.current_object:
            self.update_overlay(obj)
    
    def handle_property_change(self, feature: Optional[str] = None):
        """Handle property changes"""
        if not self.is_running:
            return
        
        self.mark_dirty(feature, "properties")
        
        if self.current_object:
            self.update_overlay(self.current_object)
    
    def get_mesh_stats(self, obj: Object) -> Dict[str, int]:
        """Get mesh statistics"""
        return self.analysis_engine.get_mesh_stats(obj)
    
    def clear_all_cache(self):
        """Clear all caches"""
        self.analysis_engine.clear_all_cache()
        self.render_pipeline.clear_all()


# Global instance
overlay_controller = OverlayController()
