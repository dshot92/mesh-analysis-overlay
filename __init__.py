# SPDX-License-Identifier: GPL-3.0-or-later

import importlib

from .mesh_analyzer import MeshAnalyzerCache

from . import operators, panels, properties, preferences

modules = (
    preferences,
    properties,
    operators,
    panels,
)


def register():
    for module in modules:
        importlib.reload(module)
        module.register()
    MeshAnalyzerCache.register()


def unregister():
    MeshAnalyzerCache.unregister()
    for module in reversed(modules):
        module.unregister()
