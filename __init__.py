# SPDX-License-Identifier: GPL-3.0-or-later

from . import operators, panels, properties, handlers, preferences
from .overlay_controller import overlay_controller

modules = [properties, operators, panels, handlers, preferences]


def register():
    # hot_reload()  # Temporarily disabled for debugging
    for module in modules:
        if hasattr(module, "register"):
            module.register()


def unregister():
    for module in modules:
        if hasattr(module, "unregister"):
            module.unregister()
    
    if overlay_controller.is_running:
        overlay_controller.stop()


def hot_reload():
    # Refresh submodules during development
    import importlib
    import sys
    
    # Reload modules
    for module in modules:
        importlib.reload(module)
    
    # Reload the overlay_controller module, not the instance
    if __package__ in sys.modules:
        importlib.reload(sys.modules[__package__])