# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from bpy.types import AddonPreferences
from bpy.props import FloatProperty, BoolProperty


class MeshAnalysisOverlayPreferences(AddonPreferences):
    bl_idname = __package__

    non_planar_threshold: FloatProperty(
        name="Non-Planar Threshold",
        description="Threshold angle for non-planar face detection",
        default=0.0001,
        min=0.0,
        max=1.0,
        precision=5,
    )

    debug_print: BoolProperty(
        name="Debug Print", description="Enable debug print statements", default=False
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "non_planar_threshold")
        layout.prop(self, "debug_print")


classes = (MeshAnalysisOverlayPreferences,)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)


def unregister():
    for bl_class in reversed(classes):
        bpy.utils.unregister_class(bl_class)
