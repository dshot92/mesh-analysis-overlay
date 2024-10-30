# SPDX-License-Identifier: GPL-3.0-or-later

from . import operators, panels, properties, preferences, handlers

modules = (
    preferences,
    properties,
    operators,
    panels,
    handlers,
)


def register():
    for module in modules:
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()
