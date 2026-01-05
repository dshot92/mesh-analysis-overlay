# SPDX-License-Identifier: GPL-3.0-or-later

# Import modules
from . import operators, panels, properties, handlers
from .overlay_controller import overlay_controller


def register():
    # Register properties first (needed by other modules)
    properties.register()
    
    # Register operators
    operators.register()
    
    # Register panels
    panels.register()
    
    # Register handlers
    handlers.register()
    

def unregister():
    # Unregister in reverse order
    handlers.unregister()
    panels.unregister()
    operators.unregister()
    properties.unregister()
    
    # Stop overlay controller
    if overlay_controller.is_running:
        overlay_controller.stop()


if __name__ == "__main__":
    register()
