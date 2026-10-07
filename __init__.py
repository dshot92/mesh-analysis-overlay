# SPDX-License-Identifier: GPL-3.0-or-later

from . import operators, panels, properties, handlers, preferences
from .overlay_controller import overlay_controller

modules = [properties, operators, panels, handlers, preferences]


def register():
    # hot_reload()  # Temporarily disabled for debugging
    for module in modules:
        if hasattr(module, "register"):
            try:
                module.register()
            except Exception:
                # Idempotent: already registered (double-register in tests).
                pass


def unregister():
    # Stop overlay first so no handler fires mid-teardown.
    try:
        if overlay_controller.is_running:
            overlay_controller.stop()
    except Exception:
        pass

    for module in modules:
        if hasattr(module, "unregister"):
            try:
                module.unregister()
            except Exception:
                pass


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