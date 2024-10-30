# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import gpu
import logging

from gpu_extras.batch import batch_for_shader
from typing import List, Tuple
from mathutils import Vector
from bpy.types import Object

from .mesh_analyzer import MeshAnalyzer


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class GPUDrawer:
    def __init__(self):
        logger.debug("=== GPUDrawer Initialization ===")
        self.shader = gpu.shader.from_builtin("FLAT_COLOR")
        self.batches = {}
        self.next_batches = {}
        self.pending_updates = {}  # Store vertex/color data before creating batch
        self.is_running = False
        self._handle = None
        self._current_analyzer = None
        logger.debug(f"Initial state:")
        logger.debug(f"- Is running: {self.is_running}")
        logger.debug(f"- Handle: {self._handle}")
        logger.debug(f"- Current analyzer: {self._current_analyzer}")

    def _get_analyzer(self, obj: Object) -> MeshAnalyzer:
        self._current_analyzer = MeshAnalyzer.get_analyzer(obj)
        return self._current_analyzer

    def update_feature_batch(
        self,
        feature: str,
        indices: List[int],
        color: Tuple[float, float, float, float],
        primitive_type: str,
    ):
        if not indices:
            return

        obj = self._current_analyzer.obj
        mesh = obj.data
        world_matrix = obj.matrix_world
        world_normal_matrix = world_matrix.inverted().transposed().to_3x3()

        # Calculate vertex positions and normals
        verts = []
        normals = []

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        offset = props.overlay_offset

        def process_vertex(v_idx):
            v = mesh.vertices[v_idx]
            pos = world_matrix @ v.co
            normal = (world_normal_matrix @ v.normal).normalized()
            offset_pos = pos + (normal * offset)
            verts.append(offset_pos)
            normals.append(normal)

        if primitive_type == "POINTS":
            # Handle vertices
            for idx in indices:
                process_vertex(idx)

        elif primitive_type == "LINES":
            # Handle edges
            for idx in indices:
                e = mesh.edges[idx]
                for v_idx in e.vertices:
                    process_vertex(v_idx)

        elif primitive_type == "TRIS":
            # Handle faces
            for idx in indices:
                f = mesh.polygons[idx]
                verts_count = len(f.vertices)

                if verts_count == 3:
                    # Regular triangle
                    for v_idx in f.vertices:
                        process_vertex(v_idx)
                else:
                    # Fan triangulation for quads and n-gons
                    v0 = f.vertices[0]  # First vertex is the fan center
                    for i in range(1, verts_count - 1):
                        # Create triangle: v0, vi, vi+1
                        process_vertex(v0)
                        process_vertex(f.vertices[i])
                        process_vertex(f.vertices[i + 1])

        # Append to pending updates
        if feature not in self.pending_updates:
            self.pending_updates[feature] = {
                "verts": [],
                "colors": [],
                "primitive_type": primitive_type,
            }

        self.pending_updates[feature]["verts"].extend(verts)
        self.pending_updates[feature]["colors"].extend([color] * len(verts))

    def draw(self):
        if not self.is_running:
            return

        # Create batches from pending updates
        for feature, data in self.pending_updates.items():
            try:
                batch = batch_for_shader(
                    self.shader,
                    data["primitive_type"],
                    {
                        "pos": data["verts"],
                        "color": data["colors"],
                    },
                )
                self.next_batches[feature] = {"batch": batch}
            except Exception as e:
                logger.debug(f"[ERROR] Failed to create batch: {str(e)}")

        self.pending_updates.clear()

        # Swap buffers if we have pending updates
        if self.next_batches:
            self.batches = self.next_batches
            self.next_batches = {}

        obj = bpy.context.active_object
        if not obj or obj.type != "MESH":
            return

        # Set GPU state
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.face_culling_set("BACK")
        gpu.state.point_size_set(
            bpy.context.scene.Mesh_Analysis_Overlay_Properties.overlay_vertex_radius
        )
        gpu.state.line_width_set(
            bpy.context.scene.Mesh_Analysis_Overlay_Properties.overlay_edge_width
        )

        # logger.debug("\n=== Draw Call ===")
        # logger.debug(f"Object: {obj.name}")
        # logger.debug(f"Batch count: {len(self.batches)}")

        if (
            not self.batches
            or self._current_analyzer is None
            or self._current_analyzer.obj != obj
        ):
            # logger.debug("Forcing batch update...")
            self.update_batches(obj)

        # logger.debug("Drawing batches...")
        self.shader.bind()
        for feature, batch_data in self.batches.items():
            # logger.debug(f"- Drawing {feature}")
            batch_data["batch"].draw(self.shader)

        # Reset GPU state
        gpu.state.blend_set("NONE")
        gpu.state.face_culling_set("NONE")

    def _update_all_batches(self, obj):
        if not obj or not self.is_running:
            return

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        analyzer = self._get_analyzer(obj)
        self.batches.clear()

        feature_configs = [
            (analyzer.face_features, "TRIS"),
            (analyzer.edge_features, "LINES"),
            (analyzer.vertex_features, "POINTS"),
        ]

        for feature_set, primitive_type in feature_configs:
            self._update_feature_set(feature_set, primitive_type, props, analyzer)

    def _update_feature_set(self, feature_set, primitive_type, props, analyzer):
        for feature in feature_set:
            if not getattr(props, f"show_{feature}", False):
                continue

            (verts,) = analyzer.analyze_feature(feature)
            if verts:
                color = tuple(getattr(props, f"{feature}_color"))
                self.update_feature_batch(feature, verts, color, primitive_type)

    def _handle_mode_change(self, obj):
        if not obj or not self.is_running:
            return False

        # Force update when:
        # 1. Exiting edit mode
        # 2. Entering object mode
        # 3. Switching between edit/object modes
        if obj.mode in {"OBJECT", "EDIT"}:
            logger.debug(f"[DEBUG] Mode change detected: {obj.mode}")
            self._update_all_batches(obj)
            return True
        return False

    def start(self):
        logger.debug("\n=== Starting GPUDrawer ===")
        self.is_running = True
        if not self._handle:
            logger.debug("Adding draw handler...")
            self._handle = bpy.types.SpaceView3D.draw_handler_add(
                self.draw, (), "WINDOW", "POST_VIEW"
            )
            logger.debug(f"Draw handler added: {self._handle}")

        obj = bpy.context.active_object
        if obj and obj.type == "MESH":
            logger.debug(f"Initial update for {obj.name}")
            self.update_batches(obj)

    def stop(self):
        logger.debug("\n=== Stopping GPUDrawer ===")
        logger.debug(f"Current state:")
        logger.debug(f"- Is running: {self.is_running}")
        logger.debug(f"- Handle: {self._handle}")
        logger.debug(f"- Batch count: {len(self.batches)}")

        if not self.is_running:
            logger.debug("Already stopped")
            return

        self.is_running = False
        if self._handle:
            logger.debug("Removing draw handler...")
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None

        logger.debug("Cleaning up...")
        self.batches.clear()
        self._current_analyzer = None
        MeshAnalyzer._cache.clear()
        MeshAnalyzer.clear_analyzer_cache()
        logger.debug("Cleanup complete")

    def update_batches(self, obj, features=None):
        logger.debug("\n=== Update Batches ===")
        logger.debug(f"Object: {obj.name if obj else 'None'}")
        logger.debug(f"Updating features: {features if features else 'all'}")

        if not obj or not self.is_running:
            logger.debug("× Skipping update - invalid state")
            return

        analyzer = self._get_analyzer(obj)
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

        if features:
            # Clear only specified features
            for feature in features:
                if feature in self.batches:
                    del self.batches[feature]
                if feature in self.next_batches:
                    del self.next_batches[feature]
        else:
            # Clear all batches for full update
            self.batches.clear()
            self.next_batches.clear()
            features = (
                list(analyzer.face_features)
                + list(analyzer.edge_features)
                + list(analyzer.vertex_features)
            )

        # Update face overlays
        for feature in analyzer.face_features:
            if feature in features and getattr(props, f"show_{feature}", False):
                indices = analyzer.analyze_feature(feature)
                if indices:
                    color = tuple(getattr(props, f"{feature}_color"))
                    self.update_feature_batch(feature, indices, color, "TRIS")

        # Update edge overlays
        for feature in analyzer.edge_features:
            if feature in features and getattr(props, f"show_{feature}", False):
                indices = analyzer.analyze_feature(feature)
                if indices:
                    color = tuple(getattr(props, f"{feature}_color"))
                    self.update_feature_batch(feature, indices, color, "LINES")

        # Update vertex overlays
        for feature in analyzer.vertex_features:
            if feature in features and getattr(props, f"show_{feature}", False):
                indices = analyzer.analyze_feature(feature)
                if indices:
                    color = tuple(getattr(props, f"{feature}_color"))
                    self.update_feature_batch(feature, indices, color, "POINTS")
