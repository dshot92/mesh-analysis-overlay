# SPDX-License-Identifier: GPL-3.0-or-later

import importlib

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


def unregister():
    for module in reversed(modules):
        module.unregister()
