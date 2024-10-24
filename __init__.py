# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------


import importlib

from . import panels, simple_triangle_gpu

#
modules = (
    simple_triangle_gpu,
    panels,
)

if "bpy" in locals():
    importlib.reload(panels)
    importlib.reload(simple_triangle_gpu)


def register():
    for module in modules:
        importlib.reload(module)
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()
