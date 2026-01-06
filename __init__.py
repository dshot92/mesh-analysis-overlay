# SPDX-License-Identifier: GPL-3.0-or-later

from . import operators, panels, properties, handlers
from .overlay_controller import overlay_controller

modules = (properties, operators, panels, handlers)


def register():
    for module in modules:
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()

    if overlay_controller.is_running:
        overlay_controller.stop()
