# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh
import numpy as np
from typing import List, Dict, Set, Optional, Tuple
from bpy.types import Object
from dataclasses import dataclass
from enum import Enum
import logging

from .feature_data import FEATURE_DATA

logger = logging.getLogger(__name__)


class FeatureType(Enum):
    VERTEX = "VERTEX"
    EDGE = "EDGE"
    FACE = "FACE"


@dataclass
class AnalysisResult:
    """Result of mesh feature analysis"""
    feature: str
    indices: np.ndarray
    feature_type: FeatureType
    timestamp: float


class MeshAnalysisEngine:
    """Pure analysis engine - no rendering logic"""
    
    def __init__(self):
        self.cache: Dict[str, AnalysisResult] = {}
        self.mesh_stats: Dict[str, Dict] = {}
        self.feature_types: Dict[str, FeatureType] = {}
        
        # Build feature type mapping
        for category, features in FEATURE_DATA.items():
            for feature in features:
                if category == "vertices":
                    self.feature_types[feature["id"]] = FeatureType.VERTEX
                elif category == "edges":
                    self.feature_types[feature["id"]] = FeatureType.EDGE
                elif category == "faces":
                    self.feature_types[feature["id"]] = FeatureType.FACE
    
    def analyze_mesh(self, obj: Object, features: Optional[List[str]] = None) -> Dict[str, AnalysisResult]:
        """Analyze mesh for specified features"""
        if not obj or obj.type != "MESH":
            return {}
        
        obj_name = obj.name
        current_time = bpy.context.scene.frame_current_final
        
        # Determine which features to analyze
        if features is None:
            features = list(self.feature_types.keys())
        
        results = {}
        
        # Check cache first
        for feature in features:
            cache_key = f"{obj_name}:{feature}"
            if cache_key in self.cache:
                result = self.cache[cache_key]
                results[feature] = result
                continue
            
            # Analyze feature
            indices = self._analyze_feature_impl(obj, feature)
            if indices is not None and len(indices) > 0:
                result = AnalysisResult(
                    feature=feature,
                    indices=indices,
                    feature_type=self.feature_types[feature],
                    timestamp=current_time
                )
                results[feature] = result
                self.cache[cache_key] = result
        
        return results
    
    def _analyze_feature_impl(self, obj: Object, feature: str) -> Optional[np.ndarray]:
        """Implement feature analysis with Edit Mode awareness"""
        try:
            # Determine if we should use the live Edit Mode buffer
            is_edit_mode = obj.mode == 'EDIT' and obj.data.is_editmode
            
            if is_edit_mode:
                # Use the fast, live pointer to the edit mesh
                bm = bmesh.from_edit_mesh(obj.data)
            else:
                # Standard path: create a copy from mesh data
                bm = bmesh.new()
                bm.from_mesh(obj.data)
            
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            
            indices = []
            feature_type = self.feature_types[feature]
            
            if feature_type == FeatureType.VERTEX:
                indices = self._analyze_vertex_features(bm, feature)
            elif feature_type == FeatureType.EDGE:
                indices = self._analyze_edge_features(bm, feature)
            elif feature_type == FeatureType.FACE:
                indices = self._analyze_face_features(bm, feature)
            
            # Only free if we created a temporary BMesh (Object Mode)
            if not is_edit_mode:
                bm.free()
            
            if indices:
                return np.array(indices, dtype=np.int32)
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing feature {feature}: {e}")
            return None
    
    def _analyze_vertex_features(self, bm: bmesh.types.BMesh, feature: str) -> List[int]:
        """Analyze vertex-based features"""
        indices = []
        
        for v in bm.verts:
            if feature == "single_vertices" and len(v.link_edges) == 0:
                indices.append(v.index)
            elif feature == "non_manifold_v_vertices" and not v.is_manifold:
                indices.append(v.index)
            elif feature == "n_pole_vertices" and len(v.link_edges) == 3:
                indices.append(v.index)
            elif feature == "e_pole_vertices" and len(v.link_edges) == 5:
                indices.append(v.index)
            elif feature == "high_pole_vertices" and len(v.link_edges) >= 6:
                indices.append(v.index)
        
        return indices
    
    def _analyze_edge_features(self, bm: bmesh.types.BMesh, feature: str) -> List[int]:
        """Analyze edge-based features"""
        indices = []
        
        for e in bm.edges:
            if feature == "non_manifold_e_edges" and not e.is_manifold:
                indices.append(e.index)
            elif feature == "sharp_edges" and not e.smooth:
                indices.append(e.index)
            elif feature == "seam_edges" and e.seam:
                indices.append(e.index)
            elif feature == "boundary_edges" and e.is_boundary:
                indices.append(e.index)
        
        return indices
    
    def _analyze_face_features(self, bm: bmesh.types.BMesh, feature: str) -> List[int]:
        """Analyze face-based features"""
        indices = []
        
        for f in bm.faces:
            if feature == "tri_faces" and len(f.verts) == 3:
                indices.append(f.index)
            elif feature == "quad_faces" and len(f.verts) == 4:
                indices.append(f.index)
            elif feature == "ngon_faces" and len(f.verts) > 4:
                indices.append(f.index)
            elif feature == "non_planar_faces" and not self._is_planar(f):
                indices.append(f.index)
            elif feature == "degenerate_faces" and self._is_degenerate(f):
                indices.append(f.index)
        
        return indices
    
    def _is_planar(self, face: bmesh.types.BMFace) -> bool:
        """Check if face is planar"""
        if len(face.verts) <= 3:
            return True
        
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        threshold_rad = np.radians(props.non_planar_threshold)
        
        normal = face.normal.normalized()
        center = face.calc_center_median()
        
        for v in face.verts:
            v_pos = v.co - center
            if v_pos.length < 1e-6:
                continue
            
            angle = np.arccos(np.clip(normal.dot(v_pos.normalized()), -1.0, 1.0))
            if abs(angle - np.pi / 2) > threshold_rad:
                return False
        
        return True
    
    def _is_degenerate(self, face: bmesh.types.BMFace) -> bool:
        """Check if face is degenerate"""
        if face.calc_area() < 1e-8:
            return True
        
        if len(face.verts) < 3:
            return True
        
        unique_verts = set(vert.co.to_tuple() for vert in face.verts)
        if len(unique_verts) < len(face.verts):
            return True
        
        return False
    
    def invalidate_cache(self, obj_name: str, features: Optional[List[str]] = None):
        """Invalidate cache for specific object and features"""
        if features is None:
            # Clear all features for this object
            keys_to_remove = [key for key in self.cache.keys() if key.startswith(f"{obj_name}:")]
            for key in keys_to_remove:
                del self.cache[key]
        else:
            # Clear specific features
            for feature in features:
                cache_key = f"{obj_name}:{feature}"
                if cache_key in self.cache:
                    del self.cache[cache_key]
    
    def get_cached_result(self, obj_name: str, feature: str) -> Optional[AnalysisResult]:
        """Get cached analysis result for a specific feature"""
        cache_key = f"{obj_name}:{feature}"
        return self.cache.get(cache_key)
    
    def get_mesh_stats(self, obj: Object) -> Dict[str, int]:
        """Get mesh statistics"""
        obj_name = obj.name
        
        if obj_name not in self.mesh_stats:
            try:
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                
                self.mesh_stats[obj_name] = {
                    "verts": len(bm.verts),
                    "edges": len(bm.edges),
                    "faces": len(bm.faces)
                }
                
                bm.free()
            except Exception as e:
                logger.error(f"Error getting mesh stats: {e}")
                self.mesh_stats[obj_name] = {"verts": 0, "edges": 0, "faces": 0}
        
        return self.mesh_stats[obj_name]
    
    def clear_all_cache(self):
        """Clear all analysis cache"""
        self.cache.clear()
        self.mesh_stats.clear()
