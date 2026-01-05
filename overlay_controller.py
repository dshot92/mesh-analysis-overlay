# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from bpy.types import Object
from dataclasses import dataclass
import logging
import bmesh

from .analysis_engine import MeshAnalysisEngine, AnalysisResult, FeatureType
from .render_pipeline import RenderPipeline, PrimitiveType
from .feature_data import FEATURE_DATA

logger = logging.getLogger(__name__)


@dataclass
class GeometryProcessor:
    """Convert analysis results to GPU-ready geometry using high-performance NumPy extraction"""
    
    @staticmethod
    def _get_mesh_data(obj: Object) -> Dict[str, np.ndarray]:
        """Extract live mesh data, handling Edit Mode specifically to ensure zero-lag following"""
        is_edit_mode = obj.mode == 'EDIT' and obj.data.is_editmode
        
        if is_edit_mode:
            # Direct BMesh extraction is the only way to track 'G' (Grab) transforms in real-time
            bm = bmesh.from_edit_mesh(obj.data)
            v_count = len(bm.verts)
            
            # Efficiently extract positions and normals from BMesh
            # Note: We must use float32 for GPU compatibility
            verts = np.array([v.co for v in bm.verts], dtype=np.float32)
            normals = np.array([v.normal for v in bm.verts], dtype=np.float32)
            
            # Extract edge indices
            edge_v_indices = np.array([[v.index for v in e.verts] for e in bm.edges], dtype=np.int32)
            
            return {
                "verts": verts.reshape((-1, 3)),
                "normals": normals.reshape((-1, 3)),
                "edge_v_indices": edge_v_indices.reshape((-1, 2)),
                "is_edit": True
            }
        else:
            # Faster foreach_get path for Object Mode
            mesh = obj.data
            v_count = len(mesh.vertices)
            verts = np.empty(v_count * 3, dtype=np.float32)
            mesh.vertices.foreach_get("co", verts)
            normals = np.empty(v_count * 3, dtype=np.float32)
            mesh.vertices.foreach_get("normal", normals)
            
            edge_v_indices = np.empty(len(mesh.edges) * 2, dtype=np.int32)
            mesh.edges.foreach_get("vertices", edge_v_indices)
            
            return {
                "verts": verts.reshape((-1, 3)),
                "normals": normals.reshape((-1, 3)),
                "edge_v_indices": edge_v_indices.reshape((-1, 2)),
                "is_edit": False
            }

    @staticmethod
    def process_vertices(indices: np.ndarray, color: Tuple[float, float, float, float], 
                        mesh_data: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Process vertex indices to GPU-ready data"""
        if len(indices) == 0:
            return np.array([]), np.array([]), np.array([])
        
        verts = mesh_data["verts"]
        normals = mesh_data["normals"]
        
        # Guard against index mismatch during rapid edits
        safe_indices = indices[indices < len(verts)]
        
        feature_verts = verts[safe_indices]
        feature_normals = normals[safe_indices]
        feature_colors = np.full((len(safe_indices), 4), color, dtype=np.float32)
        
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
        """Process face indices to GPU-ready triangle data"""
        if len(indices) == 0:
            return np.array([]), np.array([]), np.array([])
        
        # For faces in Edit Mode, we fall back to Object Data for loop triangles 
        # but use the synchronized vertex positions from the live mesh data.
        mesh = obj.data
        verts = mesh_data["verts"]
        normals = mesh_data["normals"]
        
        if mesh_data["is_edit"]:
            # Sync needed for loop triangles to match topology
            obj.update_from_editmode()
            
        mesh.calc_loop_triangles()
        
        poly_indices = np.empty(len(mesh.loop_triangles), dtype=np.int32)
        mesh.loop_triangles.foreach_get("polygon_index", poly_indices)
        mask = np.isin(poly_indices, indices)
        
        all_tri_v_indices = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get("vertices", all_tri_v_indices)
        all_tri_v_indices = all_tri_v_indices.reshape((-1, 3))
        
        selected_v_indices = all_tri_v_indices[mask].flatten()
        
        if len(selected_v_indices) == 0:
            return np.array([]), np.array([]), np.array([])
            
        feature_verts = verts[selected_v_indices]
        feature_normals = normals[selected_v_indices]
        feature_colors = np.full((len(feature_verts), 4), color, dtype=np.float32)
        
        return feature_verts, feature_normals, feature_colors


class OverlayController:
    """Main controller coordinating analysis and rendering for multiple objects"""
    
    def __init__(self):
        self.analysis_engine = MeshAnalysisEngine()
        self.render_pipeline = RenderPipeline()
        self.geometry_processor = GeometryProcessor()
        self.displayed_objects: Set[str] = set()
        self.is_running = False
    
    def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        self.analysis_engine.clear_all_cache()
        self.render_pipeline.start()
        self.update_all_selected()
        logger.debug("Overlay controller started")
    
    def stop(self):
        if not self.is_running:
            return
        
        self.is_running = False
        self.render_pipeline.stop()
        self.displayed_objects.clear()
        logger.debug("Overlay controller stopped")
    
    def update_all_selected(self):
        if not self.is_running:
            return
            
        selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
        current_names = {obj.name for obj in selected_meshes}
        to_remove = self.displayed_objects - current_names
        for name in to_remove:
            self.render_pipeline.clear_object_data(name)
        self.displayed_objects = current_names
        
        for obj in selected_meshes:
            self.update_overlay(obj)

    def update_overlay(self, obj: Object):
        if not self.is_running or not obj or obj.type != "MESH":
            return
        
        self.displayed_objects.add(obj.name)

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        enabled_features = []
        feature_colors = {}
        
        for category, features in FEATURE_DATA.items():
            for feature in features:
                f_id = feature["id"]
                if getattr(props, f"{f_id}_enabled", False):
                    enabled_features.append(f_id)
                    feature_colors[f_id] = tuple(getattr(props, f"{f_id}_color"))
        
        # Analyze using Mode-Aware engine
        analysis_results = self.analysis_engine.analyze_mesh(obj, enabled_features)
        
        # Fetch LIVE mesh data (BMesh if in Edit Mode)
        mesh_data = self.geometry_processor._get_mesh_data(obj)
        
        for category, features in FEATURE_DATA.items():
            for feature in features:
                f_id = feature["id"]
                
                if f_id in enabled_features and f_id in analysis_results:
                    result = analysis_results[f_id]
                    color = feature_colors[f_id]
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
                    
                    # Update render pipeline immediately
                    self.render_pipeline.update_feature_data(
                        obj.name, f_id, vertices, normals, colors, primitive_type
                    )
                else:
                    self.render_pipeline.update_feature_data(
                        obj.name, f_id, np.array([]), np.array([]), np.array([]), PrimitiveType.POINTS
                    )
    
    def handle_geometry_change(self, obj: Object):
        """Standard entry point for geometry updates"""
        if not self.is_running:
            return
        self.analysis_engine.invalidate_cache(obj.name)
        self.update_overlay(obj)
    
    def handle_property_change(self, feature: Optional[str] = None):
        if not self.is_running:
            return
        self.render_pipeline.mark_geometry_dirty()
        self.update_all_selected()
    
    def get_mesh_stats(self, obj: Object) -> Dict[str, int]:
        return self.analysis_engine.get_mesh_stats(obj)
    
    def clear_all_cache(self):
        self.analysis_engine.clear_all_cache()
        self.render_pipeline.clear_all()
        self.displayed_objects.clear()


# Global instance
overlay_controller = OverlayController()
