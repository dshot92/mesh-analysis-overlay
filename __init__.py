# SPDX-License-Identifier: GPL-3.0-or-later

from . import operators, panels, properties, handlers, preferences
from .overlay_controller import overlay_controller

modules = [properties, operators, panels, handlers, preferences]

# Submodules in dependency order (dependencies first so `from .x import y`
# bindings rebind to fresh objects on reload).
_submodules = (
    "config_manager",
    "utils",
    "render_pipeline",
    "analysis_engine",
    "overlay_controller",
    "handlers",
    "operators",
    "properties",
    "panels",
    "preferences",
)


def _reload_submodules():
    """Re-execute submodule code from disk (re-enable without restart).

    Python caches imports in sys.modules, so re-enabling the addon without
    this keeps running the previous build. importlib.reload runs each
    module in place; dependents reload after their dependencies so imported
    objects (e.g. the overlay_controller instance) rebind. Never raises.
    """
    import importlib
    import sys
    pkg = __package__
    for _name in _submodules:
        _modname = f"{pkg}.{_name}"
        try:
            if _modname in sys.modules:
                importlib.reload(sys.modules[_modname])
        except Exception as e:
            print(f"[Mesh Analysis Overlay] reload {_name} failed: {e}")
    # Rebind package-level names to the reloaded objects.
    try:
        global operators, panels, properties, handlers, preferences
        global overlay_controller, modules
        from . import operators, panels, properties, handlers, preferences
        from .overlay_controller import overlay_controller
        modules = [properties, operators, panels, handlers, preferences]
    except Exception as e:
        print(f"[Mesh Analysis Overlay] rebind after reload failed: {e}")


def register():
    _reload_submodules()
    for module in modules:
        if hasattr(module, "register"):
            try:
                module.register()
            except Exception as e:
                # Idempotent: already registered (double-register in tests).
                print(f"[Mesh Analysis Overlay] register {module.__name__} failed: {e}")


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
    _reload_submodules()