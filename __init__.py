# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------


import importlib

from . import operators, panels, properties

modules = (
    properties,
    operators,
    panels,
)

if "bpy" in locals():
    importlib.reload(properties)
    importlib.reload(operators)
    importlib.reload(panels)


def register():
    for module in modules:
        importlib.reload(module)
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()
