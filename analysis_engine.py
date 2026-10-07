# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh
import math
import numpy as np
from typing import List, Dict, Optional, Tuple
from bpy.types import Object
from dataclasses import dataclass, field
from enum import Enum

from .config_manager import config_manager
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
    # Versioning for selective invalidation (defaults keep old call sites working).
    topo_sig: Tuple[int, int, int] = field(default_factory=tuple)
    pos_hash: int = 0


@dataclass
class GPUFormattedData:
    """GPU-ready formatted data for a feature"""
    vertices: np.ndarray
    normals: np.ndarray
    colors: np.ndarray
    primitive_type: PrimitiveType


# Geometry-dependent features: classification changes on vertex moves
# even when counts are identical. All others are topology-only.
_GEOM_FEATURES = frozenset({"non_planar_faces", "degenerate_faces"})

_EMPTY_3 = np.zeros((0, 3), dtype=np.float32)
_EMPTY_4 = np.zeros((0, 4), dtype=np.float32)


class MeshAnalysisEngine:
    """Pure analysis engine - no rendering logic"""

    def __init__(self):
        self.cache: Dict[str, AnalysisResult] = {}
        self.mesh_stats: Dict[str, Dict] = {}
        self.feature_types: Dict[str, FeatureType] = {}

        # Build feature type mapping from config manager metadata
        metadata = config_manager.get_metadata()
        for category, features in metadata.items():
            for feature in features:
                if category == "vertices":
                    self.feature_types[feature["id"]] = FeatureType.VERTEX
                elif category == "edges":
                    self.feature_types[feature["id"]] = FeatureType.EDGE
                elif category == "faces":
                    self.feature_types[feature["id"]] = FeatureType.FACE

    def _get_feature_parameters(self, feature: str, threshold_deg: Optional[float] = None) -> Dict:
        """Get current parameters that affect this feature's analysis"""
        params = {}

        # Only non-planar faces currently have a configurable parameter
        if feature == "non_planar_faces":
            try:
                if threshold_deg is None:
                    props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
                    params["threshold"] = float(props.non_planar_threshold)
                else:
                    params["threshold"] = float(threshold_deg)
            except Exception:
                if threshold_deg is not None:
                    params["threshold"] = float(threshold_deg)

        return params

    def _empty_gpu_data(self, primitive_type: PrimitiveType = PrimitiveType.POINTS) -> GPUFormattedData:
        """Shared empty GPU payload (avoids per-call allocations)."""
        return GPUFormattedData(
            vertices=_EMPTY_3,
            normals=_EMPTY_3,
            colors=_EMPTY_4,
            primitive_type=primitive_type,
        )

    def _get_mesh_data_from_bmesh(self, bm: bmesh.types.BMesh) -> Dict[str, np.ndarray]:
        """Extract mesh data from a bmesh (foreach_get fast path with fallback)."""
        # Local import to avoid cycles at module load time.
        from .utils import extract_vert_arrays, extract_edge_vert_indices

        verts, normals = extract_vert_arrays(bm)
        edge_v_indices = extract_edge_vert_indices(bm)
        return {
            "verts": verts,
            "normals": normals,
            "edge_v_indices": edge_v_indices,
        }

    def _get_triangulated_face_data(self, bm: bmesh.types.BMesh, face_indices: np.ndarray) -> np.ndarray:
        """Get triangulated vertex indices for faces directly from BMesh.

        Same fan triangulation as before (convex assumption), but with a single
        preallocated numpy fill instead of Python list.extend per triangle.
        """
        if face_indices is None or len(face_indices) == 0:
            return np.zeros((0,), dtype=np.int32)
        try:
            n_faces = len(bm.faces)
        except Exception:
            return np.zeros((0,), dtype=np.int32)

        # First pass: total triangle count for preallocation.
        # Filter out-of-range indices (stale cache safety).
        valid = []
        total_tris = 0
        for face_idx in face_indices:
            try:
                fi = int(face_idx)
            except Exception:
                continue
            if 0 <= fi < n_faces:
                try:
                    nv = len(bm.faces[fi].verts)
                except Exception:
                    continue
                if nv >= 3:
                    valid.append(fi)
                    total_tris += nv - 2
        if total_tris == 0:
            return np.zeros((0,), dtype=np.int32)

        out = np.empty(total_tris * 3, dtype=np.int32)
        pos = 0
        for fi in valid:
            try:
                verts = bm.faces[fi].verts
            except Exception:
                continue
            if len(verts) < 3:
                continue
            v0 = verts[0].index
            # Fan: (v0, vi, vi+1)
            for i in range(1, len(verts) - 1):
                out[pos] = v0
                out[pos + 1] = verts[i].index
                out[pos + 2] = verts[i + 1].index
                pos += 3
        if pos != len(out):
            out = out[:pos]
        return out

    def _format_gpu_data(
        self,
        result: AnalysisResult,
        color: tuple,
        mesh_data: Dict[str, np.ndarray],
        bm: Optional[bmesh.types.BMesh] = None
    ) -> GPUFormattedData:
        """Format analysis result into GPU-ready data."""
        verts = mesh_data["verts"]
        normals = mesh_data["normals"]

        if result.feature_type == FeatureType.VERTEX:
            if len(result.indices) == 0 or len(verts) == 0:
                return GPUFormattedData(_EMPTY_3, _EMPTY_3, _EMPTY_4, PrimitiveType.POINTS)
            safe_indices = result.indices[result.indices < len(verts)]
            if len(safe_indices) == 0:
                return GPUFormattedData(_EMPTY_3, _EMPTY_3, _EMPTY_4, PrimitiveType.POINTS)
            vertices = np.ascontiguousarray(verts[safe_indices], dtype=np.float32)
            normals_view = np.ascontiguousarray(normals[safe_indices], dtype=np.float32)
            colors = np.full((len(safe_indices), 4), color, dtype=np.float32)
            primitive_type = PrimitiveType.POINTS

        elif result.feature_type == FeatureType.EDGE:
            edge_v_indices = mesh_data["edge_v_indices"]
            if len(result.indices) == 0 or len(edge_v_indices) == 0 or len(verts) == 0:
                return GPUFormattedData(_EMPTY_3, _EMPTY_3, _EMPTY_4, PrimitiveType.LINES)
            # Guard against stale edge indices.
            safe_e = result.indices[result.indices < len(edge_v_indices)]
            if len(safe_e) == 0:
                return GPUFormattedData(_EMPTY_3, _EMPTY_3, _EMPTY_4, PrimitiveType.LINES)
            selected_v_indices = edge_v_indices[safe_e].reshape(-1)
            # Guard against stale vert indices (topology changed mid-frame).
            selected_v_indices = selected_v_indices[selected_v_indices < len(verts)]
            if len(selected_v_indices) == 0:
                return GPUFormattedData(_EMPTY_3, _EMPTY_3, _EMPTY_4, PrimitiveType.LINES)
            vertices = np.ascontiguousarray(verts[selected_v_indices], dtype=np.float32)
            normals_view = np.ascontiguousarray(normals[selected_v_indices], dtype=np.float32)
            colors = np.full((len(selected_v_indices), 4), color, dtype=np.float32)
            primitive_type = PrimitiveType.LINES

        elif result.feature_type == FeatureType.FACE:
            # For faces, use direct triangulation from BMesh
            if bm is not None:
                tri_v_indices = self._get_triangulated_face_data(bm, result.indices)

                if len(tri_v_indices) == 0:
                    vertices = np.array([], dtype=np.float32).reshape(0, 3)
                    normals_view = np.array([], dtype=np.float32).reshape(0, 3)
                    colors = np.array([], dtype=np.float32).reshape(0, 4)
                    primitive_type = PrimitiveType.TRIS
                else:
                    # Guard stale indices.
                    tri_v_indices = tri_v_indices[tri_v_indices < len(verts)]
                    if len(tri_v_indices) == 0:
                        vertices = np.array([], dtype=np.float32).reshape(0, 3)
                        normals_view = np.array([], dtype=np.float32).reshape(0, 3)
                        colors = np.array([], dtype=np.float32).reshape(0, 4)
                    else:
                        vertices = np.ascontiguousarray(verts[tri_v_indices], dtype=np.float32)
                        normals_view = np.ascontiguousarray(normals[tri_v_indices], dtype=np.float32)
                        colors = np.full((len(tri_v_indices), 4), color, dtype=np.float32)
                    primitive_type = PrimitiveType.TRIS
            else:
                # Fallback to empty data if no BMesh provided
                vertices = np.array([], dtype=np.float32).reshape(0, 3)
                normals_view = np.array([], dtype=np.float32).reshape(0, 3)
                colors = np.array([], dtype=np.float32).reshape(0, 4)
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

    @staticmethod
    def _current_topo_sig(bm) -> Tuple[int, int, int]:
        try:
            return (len(bm.verts), len(bm.edges), len(bm.faces))
        except Exception:
            return (0, 0, 0)

    def analyze_mesh(
        self, obj: Object, features: Optional[List[str]] = None, bm: Optional[bmesh.types.BMesh] = None,
        threshold_deg: Optional[float] = None
    ) -> Dict[str, AnalysisResult]:
        """Analyze mesh for specified features - requires BMesh to be provided.

        Cache is version-aware: entries are valid only if parameters match AND
        topology signature matches AND (for geometry features) position hash matches.
        threshold_deg overrides the scene non-planar threshold (degrees) when given.
        Empty results are cached and returned (as empty index arrays).
        """
        if not obj or obj.type != "MESH" or bm is None:
            return {}

        obj_name = obj.name

        # Determine which features to analyze
        if features is None:
            features = list(self.feature_types.keys())
        else:
            # Drop unknown ids gracefully (compat with stale prefs).
            features = [f for f in features if f in self.feature_types]
        if not features:
            return {}

        topo_sig = self._current_topo_sig(bm)

        results = {}
        uncached_features: List[str] = []
        current_params: Dict[str, Dict] = {}
        for feature in features:
            current_params[feature] = self._get_feature_parameters(feature, threshold_deg)

        # Decide whether a position hash is needed: only to validate cached
        # geometry-dependent entries whose topo + params already match.
        need_hash = False
        for feature in features:
            if feature not in _GEOM_FEATURES:
                continue
            cached_result = self.cache.get(f"{obj_name}:{feature}")
            if (
                cached_result is not None
                and cached_result.parameters == current_params[feature]
                and tuple(cached_result.topo_sig) == tuple(topo_sig)
            ):
                need_hash = True
                break

        pos_hash: Optional[int] = None
        if need_hash:
            from .utils import compute_bmesh_pos_hash
            try:
                pos_hash = compute_bmesh_pos_hash(bm)
            except Exception:
                pos_hash = 0

        for feature in features:
            cache_key = f"{obj_name}:{feature}"
            cached_result = self.cache.get(cache_key)
            if cached_result is None:
                uncached_features.append(feature)
                continue
            if cached_result.parameters != current_params[feature]:
                uncached_features.append(feature)
                continue
            if tuple(cached_result.topo_sig) != tuple(topo_sig):
                uncached_features.append(feature)
                continue
            if feature in _GEOM_FEATURES and cached_result.pos_hash != pos_hash:
                uncached_features.append(feature)
                continue
            results[feature] = cached_result

        # Analyze all uncached features with the provided BMesh (single pass)
        if uncached_features:
            # Compute pos hash once for storing with new geom results.
            if pos_hash is None and any(f in _GEOM_FEATURES for f in uncached_features):
                from .utils import compute_bmesh_pos_hash
                try:
                    pos_hash = compute_bmesh_pos_hash(bm)
                except Exception:
                    pos_hash = 0
            analysis_results = self._analyze_features_batch(bm, uncached_features, threshold_deg)

            for feature, indices in analysis_results.items():
                if indices is None:
                    continue
                try:
                    arr = np.ascontiguousarray(indices, dtype=np.int32).reshape(-1)
                except Exception:
                    arr = np.zeros((0,), dtype=np.int32)
                result = AnalysisResult(
                    feature=feature,
                    indices=arr,
                    feature_type=self.feature_types[feature],
                    parameters=current_params.get(feature, self._get_feature_parameters(feature, threshold_deg)),
                    topo_sig=topo_sig,
                    pos_hash=pos_hash if pos_hash is not None else 0,
                )
                results[feature] = result
                cache_key = f"{obj_name}:{feature}"
                self.cache[cache_key] = result

        return results

    def analyze_and_format_mesh_with_bmesh(
        self, obj: Object, features: Optional[List[str]] = None, feature_colors: Optional[Dict[str, tuple]] = None, bm: Optional[bmesh.types.BMesh] = None,
        threshold_deg: Optional[float] = None
    ) -> Dict[str, GPUFormattedData]:
        """Analyze mesh and return GPU-ready formatted data using provided bmesh"""
        if not obj or obj.type != "MESH" or bm is None:
            return {}
        if features is not None and len(features) == 0:
            return {}

        # Extract mesh data from the provided bmesh
        mesh_data = self._get_mesh_data_from_bmesh(bm)

        # Get analysis results using the provided bmesh
        analysis_results = self.analyze_mesh(obj, features, bm, threshold_deg)

        # Convert to GPU formatted data
        gpu_results = {}
        for feature_id, result in analysis_results.items():
            if feature_colors:
                color = feature_colors.get(feature_id, (1.0, 0.0, 0.0, 1.0))
            else:
                color = (1.0, 0.0, 0.0, 1.0)  # Default red

            gpu_data = self._format_gpu_data(result, color, mesh_data, bm)
            gpu_results[feature_id] = gpu_data

        return gpu_results

    def _analyze_features_batch(self, bm: bmesh.types.BMesh, features: List[str], threshold_deg: Optional[float] = None) -> Dict[str, Optional[np.ndarray]]:
        """Analyze multiple features in a single pass per element type.

        Verts scanned at most once, edges once, faces once — instead of once
        per feature. Predicates are identical to the old per-feature loops.
        threshold_deg is in degrees (matches scene property); None reads it
        from the current scene for compat.
        """
        results: Dict[str, Optional[np.ndarray]] = {}
        try:
            vert_feats = [f for f in features if self.feature_types.get(f) == FeatureType.VERTEX]
            edge_feats = [f for f in features if self.feature_types.get(f) == FeatureType.EDGE]
            face_feats = [f for f in features if self.feature_types.get(f) == FeatureType.FACE]

            buffers: Dict[str, list] = {f: [] for f in features}

            if vert_feats:
                want_single = "single_vertices" in vert_feats
                want_nmanv = "non_manifold_v_vertices" in vert_feats
                want_n = "n_pole_vertices" in vert_feats
                want_e = "e_pole_vertices" in vert_feats
                want_h = "high_pole_vertices" in vert_feats
                for v in bm.verts:
                    try:
                        n_edges = len(v.link_edges)
                    except Exception:
                        continue
                    idx = v.index
                    if want_single and n_edges == 0:
                        buffers["single_vertices"].append(idx)
                    if want_nmanv:
                        try:
                            if not v.is_manifold:
                                buffers["non_manifold_v_vertices"].append(idx)
                        except Exception:
                            pass
                    if want_n and n_edges == 3:
                        buffers["n_pole_vertices"].append(idx)
                    if want_e and n_edges == 5:
                        buffers["e_pole_vertices"].append(idx)
                    if want_h and n_edges >= 6:
                        buffers["high_pole_vertices"].append(idx)

            if edge_feats:
                want_nman = "non_manifold_e_edges" in edge_feats
                want_sharp = "sharp_edges" in edge_feats
                want_seam = "seam_edges" in edge_feats
                want_bnd = "boundary_edges" in edge_feats
                for e in bm.edges:
                    idx = e.index
                    if want_nman:
                        try:
                            if not e.is_manifold:
                                buffers["non_manifold_e_edges"].append(idx)
                        except Exception:
                            pass
                    if want_sharp:
                        try:
                            if not e.smooth:
                                buffers["sharp_edges"].append(idx)
                        except Exception:
                            pass
                    if want_seam:
                        try:
                            if e.seam:
                                buffers["seam_edges"].append(idx)
                        except Exception:
                            pass
                    if want_bnd:
                        try:
                            if e.is_boundary:
                                buffers["boundary_edges"].append(idx)
                        except Exception:
                            pass

            if face_feats:
                want_tri = "tri_faces" in face_feats
                want_quad = "quad_faces" in face_feats
                want_ngon = "ngon_faces" in face_feats
                want_nonplanar = "non_planar_faces" in face_feats
                want_degen = "degenerate_faces" in face_feats
                threshold_rad = 0.0
                if want_nonplanar:
                    if threshold_deg is not None:
                        try:
                            threshold_rad = float(np.radians(float(threshold_deg)))
                        except Exception:
                            threshold_rad = 0.0
                    else:
                        try:
                            props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
                            threshold_rad = float(np.radians(props.non_planar_threshold))
                        except Exception:
                            threshold_rad = 0.0
                for f in bm.faces:
                    try:
                        nv = len(f.verts)
                    except Exception:
                        continue
                    idx = f.index
                    if want_tri and nv == 3:
                        buffers["tri_faces"].append(idx)
                    if want_quad and nv == 4:
                        buffers["quad_faces"].append(idx)
                    if want_ngon and nv > 4:
                        buffers["ngon_faces"].append(idx)
                    if want_nonplanar:
                        try:
                            if not self._is_planar_fast(f, threshold_rad):
                                buffers["non_planar_faces"].append(idx)
                        except Exception:
                            pass
                    if want_degen:
                        try:
                            if self._is_degenerate(f):
                                buffers["degenerate_faces"].append(idx)
                        except Exception:
                            pass

            for feature in features:
                buf = buffers.get(feature, [])
                # Always return an array (possibly empty) so empty results are
                # cacheable; None is reserved for hard errors below.
                results[feature] = np.array(buf, dtype=np.int32) if buf else np.zeros((0,), dtype=np.int32)

        except Exception as e:
            print(f"Error analyzing features batch: {e}")
            # Return None for all features on error
            for feature in features:
                results[feature] = None

        return results

    def _analyze_vertex_features(
        self, bm: bmesh.types.BMesh, feature: str
    ) -> List[int]:
        """Analyze vertex-based features (kept for compat; batch path preferred)."""
        batch = self._analyze_features_batch(bm, [feature])
        arr = batch.get(feature)
        return arr.tolist() if arr is not None else []

    def _analyze_edge_features(self, bm: bmesh.types.BMesh, feature: str) -> List[int]:
        """Analyze edge-based features (kept for compat; batch path preferred)."""
        batch = self._analyze_features_batch(bm, [feature])
        arr = batch.get(feature)
        return arr.tolist() if arr is not None else []

    def _analyze_face_features(self, bm: bmesh.types.BMesh, feature: str) -> List[int]:
        """Analyze face-based features (kept for compat; batch path preferred)."""
        batch = self._analyze_features_batch(bm, [feature])
        arr = batch.get(feature)
        return arr.tolist() if arr is not None else []

    def _is_planar_fast(self, face: bmesh.types.BMFace, threshold_rad: float) -> bool:
        """Check if face is planar using pre-calculated threshold.

        Identical semantics to previous version; scalar math.acos is faster
        than np.arccos for per-vertex scalars.
        """
        try:
            if len(face.verts) <= 3:
                return True
        except Exception:
            return True

        try:
            normal = face.normal
            center = face.calc_center_median()
        except Exception:
            return True

        nx, ny, nz = normal.x, normal.y, normal.z
        cx, cy, cz = center.x, center.y, center.z
        half_pi = math.pi / 2.0
        for v in face.verts:
            try:
                vx = v.co.x - cx
                vy = v.co.y - cy
                vz = v.co.z - cz
            except Exception:
                continue
            lsq = vx * vx + vy * vy + vz * vz
            if lsq < 1e-12:
                continue
            inv = 1.0 / math.sqrt(lsq)
            dot = (nx * vx + ny * vy + nz * vz) * inv
            if dot > 1.0:
                dot = 1.0
            elif dot < -1.0:
                dot = -1.0
            angle = math.acos(dot)
            if abs(angle - half_pi) > threshold_rad:
                return False

        return True

    def _is_degenerate(self, face: bmesh.types.BMFace) -> bool:
        """Check if face is degenerate"""
        try:
            if face.calc_area() < 1e-8:
                return True
        except Exception:
            return True

        try:
            verts = face.verts
            if len(verts) < 3:
                return True
            unique_verts = set(vert.co.to_tuple() for vert in verts)
            if len(unique_verts) < len(verts):
                return True
        except Exception:
            return False

        return False

    def _analyze_with_bmesh(self, bm: bmesh.types.BMesh, feature: str) -> List[int]:
        """Analyze features using a BMesh (kept for compat)."""
        batch = self._analyze_features_batch(bm, [feature])
        arr = batch.get(feature)
        return arr.tolist() if arr is not None else []

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
        """Get mesh statistics (O(1) fast path, no BMesh alloc)."""
        obj_name = obj.name

        if obj_name not in self.mesh_stats:
            try:
                data = getattr(obj, "data", None)
                if data is not None and hasattr(data, "vertices") and hasattr(data, "polygons"):
                    self.mesh_stats[obj_name] = {
                        "verts": len(data.vertices),
                        "edges": len(data.edges),
                        "faces": len(data.polygons),
                    }
                else:
                    bm = bmesh.new()
                    try:
                        bm.from_mesh(obj.data)
                        self.mesh_stats[obj_name] = {
                            "verts": len(bm.verts),
                            "edges": len(bm.edges),
                            "faces": len(bm.faces),
                        }
                    finally:
                        bm.free()
            except Exception:
                self.mesh_stats[obj_name] = {"verts": 0, "edges": 0, "faces": 0}

        return self.mesh_stats[obj_name]

    def clear_all_cache(self):
        """Clear all analysis cache"""
        self.cache.clear()
        self.mesh_stats.clear()
