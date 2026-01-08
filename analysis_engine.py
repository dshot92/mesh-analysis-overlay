# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh
import numpy as np
from typing import List, Dict, Optional
from bpy.types import Object
from dataclasses import dataclass
from enum import Enum

from .feature_data import FEATURE_DATA
from .render_pipeline import PrimitiveType


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
    parameters: Dict  # Store parameters used for generation


@dataclass
class GPUFormattedData:
    """GPU-ready formatted data for a feature"""
    vertices: np.ndarray
    normals: np.ndarray
    colors: np.ndarray
    primitive_type: PrimitiveType


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

    def _get_feature_parameters(self, feature: str) -> Dict:
        """Get current parameters that affect this feature's analysis"""
        params = {}
        
        # Only non-planar faces currently have a configurable parameter
        if feature == "non_planar_faces":
            props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
            params["threshold"] = props.non_planar_threshold
            
        return params

    def _get_updated_bmesh(self, obj: Object) -> bmesh.types.BMesh:
        """Get the most updated bmesh for an object based on its state"""
        # Detect object state
        if obj.mode == "EDIT":
            # Check for Geometry Nodes in Edit Mode
            has_geometry_nodes = any(mod.type == "NODES" for mod in obj.modifiers)
            analysis_mode = "EDIT_GEOMETRY_NODES" if has_geometry_nodes else "EDIT"
        else:
            analysis_mode = "OBJECT"
        
        # Get bmesh based on state
        if analysis_mode in ["EDIT", "EDIT_GEOMETRY_NODES"]:
            # Direct BMesh extraction for real-time tracking
            bm = bmesh.from_edit_mesh(obj.data)
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            return bm
        else:
            # OBJECT mode - use evaluated mesh from depsgraph
            depsgraph = bpy.context.evaluated_depsgraph_get()
            evaluated_obj = obj.evaluated_get(depsgraph)
            mesh = evaluated_obj.to_mesh()
            
            try:
                bm = bmesh.new()
                bm.from_mesh(mesh)
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
                bm.verts.ensure_lookup_table()
                return bm
            finally:
                evaluated_obj.to_mesh_clear()

    def _get_mesh_data_from_bmesh(self, bm: bmesh.types.BMesh) -> Dict[str, np.ndarray]:
        """Extract mesh data from a bmesh"""
        v_count = len(bm.verts)
        
        # Use BMesh iteration for vertex data extraction
        verts = np.empty(v_count * 3, dtype=np.float32)
        normals = np.empty(v_count * 3, dtype=np.float32)
        
        for i, vert in enumerate(bm.verts):
            verts[i*3:i*3+3] = vert.co
            normals[i*3:i*3+3] = vert.normal

        edge_v_indices = np.empty(len(bm.edges) * 2, dtype=np.int32)
        for i, edge in enumerate(bm.edges):
            edge_v_indices[i*2:i*2+2] = edge.verts[0].index, edge.verts[1].index

        return {
            "verts": verts.reshape((-1, 3)),
            "normals": normals.reshape((-1, 3)),
            "edge_v_indices": edge_v_indices.reshape((-1, 2)),
        }

    def _get_mesh_for_triangulation(self, bm: bmesh.types.BMesh) -> bpy.types.Mesh:
        """Get mesh for triangulation from the bmesh"""
        # Create a temporary mesh from the bmesh
        temp_mesh = bpy.data.meshes.new(name="_temp_triangulation")
        bm.to_mesh(temp_mesh)
        return temp_mesh

    def _format_gpu_data(
        self,
        result: AnalysisResult,
        color: tuple,
        mesh_data: Dict[str, np.ndarray],
        mesh: Optional[bpy.types.Mesh] = None
    ) -> GPUFormattedData:
        """Format analysis result into GPU-ready data using views"""
        verts = mesh_data["verts"]
        normals = mesh_data["normals"]

        if result.feature_type == FeatureType.VERTEX:
            # Use views to avoid copying data
            safe_indices = result.indices[result.indices < len(verts)]
            vertices = verts[safe_indices]
            normals_view = normals[safe_indices]
            colors = np.full((len(safe_indices), 4), color, dtype=np.float32)
            primitive_type = PrimitiveType.POINTS

        elif result.feature_type == FeatureType.EDGE:
            edge_v_indices = mesh_data["edge_v_indices"]
            selected_v_indices = edge_v_indices[result.indices].flatten()
            vertices = verts[selected_v_indices]
            normals_view = normals[selected_v_indices]
            colors = np.full((len(selected_v_indices), 4), color, dtype=np.float32)
            primitive_type = PrimitiveType.LINES

        elif result.feature_type == FeatureType.FACE:
            # For faces, we need loop triangles from the provided mesh
            # Use the mesh that was passed in by the caller
            
            mesh.calc_loop_triangles()

            poly_indices = np.empty(len(mesh.loop_triangles), dtype=np.int32)
            mesh.loop_triangles.foreach_get("polygon_index", poly_indices)
            mask = np.isin(poly_indices, result.indices)

            all_tri_v_indices = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
            mesh.loop_triangles.foreach_get("vertices", all_tri_v_indices)
            all_tri_v_indices = all_tri_v_indices.reshape((-1, 3))

            selected_v_indices = all_tri_v_indices[mask].flatten()

            if len(selected_v_indices) == 0:
                vertices = np.array([], dtype=np.float32).reshape(0, 3)
                normals_view = np.array([], dtype=np.float32).reshape(0, 3)
                colors = np.array([], dtype=np.float32).reshape(0, 4)
                primitive_type = PrimitiveType.TRIS
            else:
                vertices = verts[selected_v_indices]
                normals_view = normals[selected_v_indices]
                colors = np.full((len(selected_v_indices), 4), color, dtype=np.float32)
                primitive_type = PrimitiveType.TRIS

        else:
            vertices = np.array([], dtype=np.float32).reshape(0, 3)
            normals_view = np.array([], dtype=np.float32).reshape(0, 3)
            colors = np.array([], dtype=np.float32).reshape(0, 4)
            primitive_type = PrimitiveType.POINTS

        return GPUFormattedData(
            vertices=vertices,
            normals=normals_view,
            colors=colors,
            primitive_type=primitive_type
        )

    def analyze_mesh(
        self, obj: Object, features: Optional[List[str]] = None, bm: Optional[bmesh.types.BMesh] = None
    ) -> Dict[str, AnalysisResult]:
        """Analyze mesh for specified features"""
        if not obj or obj.type != "MESH":
            return {}

        obj_name = obj.name
        # current_time removed - we use event-based invalidation

        # Determine which features to analyze
        if features is None:
            features = list(self.feature_types.keys())

        results = {}
        uncached_features = []

        # Check cache first with PARAMETER validation
        for feature in features:
            cache_key = f"{obj_name}:{feature}"
            
            # Get current parameters for this feature
            current_params = self._get_feature_parameters(feature)
            
            cached_result = self.cache.get(cache_key)
            
            # Valid if exists AND parameters match
            if cached_result and cached_result.parameters == current_params:
                results[feature] = cached_result
            else:
                uncached_features.append(feature)

        # Analyze all uncached features with a single BMesh, using mode optimization
        if uncached_features:
            # If bmesh not provided, get the most updated one
            if bm is None:
                bm = self._get_updated_bmesh(obj)
                should_free_bm = True
            else:
                should_free_bm = False
                
            # Use the provided bmesh directly - no more extraction!
            analysis_results = self._analyze_features_batch(bm, uncached_features)
            
            for feature, indices in analysis_results.items():
                if indices is not None and len(indices) > 0:
                    result = AnalysisResult(
                        feature=feature,
                        indices=indices,
                        feature_type=self.feature_types[feature],
                        parameters=self._get_feature_parameters(feature),
                    )
                    results[feature] = result
                    cache_key = f"{obj_name}:{feature}"
                    self.cache[cache_key] = result

            # Clean up bmesh if we created it (edit mode bmesh is managed by Blender)
            if should_free_bm and obj.mode != "EDIT":
                bm.free()

        return results

    def analyze_and_format_mesh(
        self, obj: Object, features: Optional[List[str]] = None, feature_colors: Optional[Dict[str, tuple]] = None, analysis_mode: str = "OBJECT"
    ) -> Dict[str, GPUFormattedData]:
        """Analyze mesh and return GPU-ready formatted data"""
        if not obj or obj.type != "MESH":
            return {}

        # Get the most updated bmesh for this object
        bm = self._get_updated_bmesh(obj)
        
        # Extract mesh data from the bmesh
        mesh_data = self._get_mesh_data_from_bmesh(bm)
        
        # Get analysis results using the bmesh
        analysis_results = self.analyze_mesh(obj, features, bm)
        
        # Get mesh for triangulation from the bmesh
        mesh = self._get_mesh_for_triangulation(bm)

        # Convert to GPU formatted data
        gpu_results = {}
        for feature_id, result in analysis_results.items():
            if feature_colors and feature_colors:
                color = feature_colors[feature_id]
            else:
                color = (1.0, 0.0, 0.0, 1.0)  # Default red
            
            gpu_data = self._format_gpu_data(result, color, mesh_data, mesh)
            gpu_results[feature_id] = gpu_data
            
        # Clean up bmesh if we created it (edit mode bmesh is managed by Blender)
        if obj.mode != "EDIT":
            bm.free()
        
        # Clean up temporary mesh
        bpy.data.meshes.remove(mesh)
            
        return gpu_results

    def _analyze_features_batch(self, bm: bmesh.types.BMesh, features: List[str]) -> Dict[str, Optional[np.ndarray]]:
        """Analyze multiple features using a provided BMesh for efficiency"""
        results = {}
        
        try:
            # Analyze all features on the same BMesh
            for feature in features:
                indices = self._analyze_with_bmesh(bm, feature)
                results[feature] = np.array(indices, dtype=np.int32) if indices else None
                
        except Exception as e:
            print(f"Error analyzing features batch: {e}")
            # Return None for all features on error
            for feature in features:
                results[feature] = None
                
        return results

    def _analyze_vertex_features(
        self, bm: bmesh.types.BMesh, feature: str
    ) -> List[int]:
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
        """Analyze face-based features with optimized property access"""
        indices = []

        # Pull threshold once for loop optimization
        threshold_rad = 0.0
        if feature == "non_planar_faces":
            props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
            threshold_rad = np.radians(props.non_planar_threshold)

        for f in bm.faces:
            if feature == "tri_faces":
                if len(f.verts) == 3:
                    indices.append(f.index)
            elif feature == "quad_faces":
                if len(f.verts) == 4:
                    indices.append(f.index)
            elif feature == "ngon_faces":
                if len(f.verts) > 4:
                    indices.append(f.index)
            elif feature == "non_planar_faces":
                if not self._is_planar_fast(f, threshold_rad):
                    indices.append(f.index)
            elif feature == "degenerate_faces":
                if self._is_degenerate(f):
                    indices.append(f.index)

        return indices

    def _is_planar_fast(self, face: bmesh.types.BMFace, threshold_rad: float) -> bool:
        """Check if face is planar using pre-calculated threshold"""
        if len(face.verts) <= 3:
            return True

        normal = face.normal
        center = face.calc_center_median()

        for v in face.verts:
            v_pos = v.co - center
            if v_pos.length_squared < 1e-12:
                continue

            # Dot product of normalized vectors
            dot = normal.dot(v_pos.normalized())
            angle = np.arccos(np.clip(dot, -1.0, 1.0))
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

    def _analyze_with_bmesh(self, bm: bmesh.types.BMesh, feature: str) -> List[int]:
        """Analyze features using a BMesh"""
        indices = []
        feature_type = self.feature_types[feature]

        if feature_type == FeatureType.VERTEX:
            indices = self._analyze_vertex_features(bm, feature)
        elif feature_type == FeatureType.EDGE:
            indices = self._analyze_edge_features(bm, feature)
        elif feature_type == FeatureType.FACE:
            indices = self._analyze_face_features(bm, feature)

        return indices

    def invalidate_cache(self, obj_name: str, features: Optional[List[str]] = None):
        """Invalidate cache for specific object and features"""
        if obj_name in self.mesh_stats:
            del self.mesh_stats[obj_name]

        if features is None:
            # Clear all features for this object
            keys_to_remove = [
                key for key in self.cache.keys() if key.startswith(f"{obj_name}:")
            ]
            for key in keys_to_remove:
                del self.cache[key]
        else:
            # Clear specific features
            for feature in features:
                cache_key = f"{obj_name}:{feature}"
                if cache_key in self.cache:
                    del self.cache[cache_key]

    def get_cached_result(
        self, obj_name: str, feature: str
    ) -> Optional[AnalysisResult]:
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
                    "faces": len(bm.faces),
                }

                bm.free()
            except Exception as e:
                self.mesh_stats[obj_name] = {"verts": 0, "edges": 0, "faces": 0}

        return self.mesh_stats[obj_name]

    def clear_all_cache(self):
        """Clear all analysis cache"""
        self.cache.clear()
        self.mesh_stats.clear()
