# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------


import importlib

from . import gpu_drawer, panels, properties

modules = (
    properties,
    gpu_drawer,
    panels,
)

if "bpy" in locals():
    importlib.reload(panels)
    importlib.reload(gpu_drawer)


def register():
    for module in modules:
        importlib.reload(module)
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()
