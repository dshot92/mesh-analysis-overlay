# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh
import numpy as np
import os
import time
import threading
from contextlib import contextmanager
from typing import Dict, List, Tuple

# ---- Lightweight profiling (env-gated, zero-cost when off) ----
_prof_lock = threading.Lock()
_prof_totals: Dict[str, float] = {}
_prof_counts: Dict[str, int] = {}
_profile_manual: object = None
_profile_autoprint: bool = False
_scope_stack: list = []
_overlay_start_wall: str = ""
_overlay_start_mono: float = 0.0
_prof_last_features: str = ""
_AUTOPRINT_LABELS = frozenset({
    "ctrl.update_overlay", "ctrl.update_all",
    "handlers.depsgraph", "handlers.toggle",
    "analyze.mesh", "analyze.format", "analyze.batch",
})
_AUTOPRINT_PREFIXES = ("analyze.", "format.", "feature.", "ctrl.", "handlers.", "snap.", "cache.", "render.")

def _timestamp() -> str:
    try:
        t = time.time()
        ms = int((t - int(t)) * 1000.0)
        return time.strftime("%H:%M:%S", time.localtime(t)) + f".{ms:03d}"
    except Exception:
        return "--:--:--"

def note_overlay_start():
    """Stamp overlay start (wall + monotonic). Prints when auto-print is on."""
    global _overlay_start_wall, _overlay_start_mono
    try:
        _overlay_start_wall = _timestamp()
        _overlay_start_mono = time.perf_counter()
        if _profile_enabled() and _profile_autoprint:
            print(f"[{_overlay_start_wall}] [Profile] overlay started")
    except Exception:
        pass

def note_overlay_stop():
    global _overlay_start_wall, _overlay_start_mono
    try:
        _overlay_start_wall = ""
        _overlay_start_mono = 0.0
    except Exception:
        pass

def prof_event(msg: str) -> None:
    """One-off event line. Folds into the open scope, else prints directly."""
    try:
        if not (_profile_enabled() and _profile_autoprint):
            return
        with _prof_lock:
            if _scope_stack:
                if len(_scope_stack[-1]["notes"]) < 10:
                    _scope_stack[-1]["notes"].append(str(msg)[:200])
                return
        print(f"[{_timestamp()}] [Profile] {msg}")
    except Exception:
        pass

def prof_features(features, obj_name=None, mode=None, counts=None) -> None:
    """Log object + mode + size + which toggles are on for this analysis."""
    global _prof_last_features
    try:
        names = sorted(str(f) for f in (features or []))
    except Exception:
        names = []
    try:
        obj = str(obj_name) if obj_name else "?"
        m = str(mode) if mode else "?"
        size = ""
        try:
            if counts is not None:
                size = f" V={counts[0]} E={counts[1]} F={counts[2]}"
        except Exception:
            pass
        _prof_last_features = f"{obj}[{m}]{size}: " + (", ".join(names) if names else "(none)")
        if not (_profile_enabled() and _profile_autoprint):
            return
        with _prof_lock:
            scoped = bool(_scope_stack)
            if scoped:
                _scope_stack[-1]["detail"] = f"{obj}[{m}]{size} n={len(names)}"[:200]
                if len(_scope_stack[-1]["notes"]) < 10:
                    _scope_stack[-1]["notes"].append(
                        f"features: {', '.join(names) if names else '(none)'}")
                return
        print(f"[{_timestamp()}] [Profile] {obj}[{m}]{size} features(n={len(names)}): {', '.join(names) if names else '(none)'}")
    except Exception:
        pass

def _should_autoprint(label: str) -> bool:
    try:
        if not _profile_autoprint:
            return False
        if label in _AUTOPRINT_LABELS:
            return True
        return str(label).startswith(_AUTOPRINT_PREFIXES)
    except Exception:
        return False

def set_profile_autoprint(enabled: bool):
    global _profile_autoprint
    try:
        _profile_autoprint = bool(enabled)
    except Exception:
        pass

def set_profile_enabled(enabled: bool):
    global _profile_manual
    try:
        _profile_manual = bool(enabled)
        try:
            os.environ["MESH_ANALYSIS_PROFILE"] = "1" if enabled else "0"
        except Exception:
            pass
    except Exception:
        pass

def _profile_enabled() -> bool:
    try:
        if _profile_manual is not None:
            return bool(_profile_manual)
    except Exception:
        pass
    try:
        return os.getenv("MESH_ANALYSIS_PROFILE", "0") == "1"
    except Exception:
        return False

@contextmanager
def prof(label: str):
    if not _profile_enabled():
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        try:
            dt = time.perf_counter() - t0
            with _prof_lock:
                _prof_totals[label] = _prof_totals.get(label, 0.0) + dt
                _prof_counts[label] = _prof_counts.get(label, 0) + 1
                n = _prof_counts.get(label, 0)
                scoped = bool(_scope_stack)
                if scoped and len(_scope_stack[-1]["rows"]) < 1000:
                    _scope_stack[-1]["rows"].append((label, dt * 1000.0))
            if not scoped:
                try:
                    if _should_autoprint(label):
                        print(f"[{_timestamp()}] [Profile] {label}: {dt*1000.0:.1f}ms (n={n})")
                except Exception:
                    pass
        except Exception:
            pass


def _render_tree_lines(rows):
    """Aggregate rows into indented tree lines via label-prefix nesting.

    A label nested under the longest other recorded label it extends with
    ".". Returns list of (depth, short_label, ms, n). Never raises.
    """
    try:
        totals = {}
        counts = {}
        order = []
        for k, v in rows:
            try:
                ms = float(v)
            except Exception:
                continue
            if k not in totals:
                totals[k] = 0.0
                counts[k] = 0
                order.append(k)
            totals[k] += ms
            counts[k] += 1
    except Exception:
        return []
    try:
        def _parent(k):
            best = None
            for c in totals:
                if c != k and k.startswith(c + ".") and (best is None or len(c) > len(best)):
                    best = c
            if best is None and k.startswith("format.") and len(k.split(".")) == 2 \
                    and "analyze.format" in totals:
                best = "analyze.format"
            return best
        kids = {k: [] for k in totals}
        roots = []
        for k in order:
            par = _parent(k)
            if par is None:
                roots.append(k)
            else:
                kids[par].append(k)
        roots.sort(key=lambda k: -totals[k])
        for k in kids:
            kids[k].sort(key=lambda k: -totals[k])
        lines = []
        def _walk(key, depth, prefix_last):
            kids_here = [c for c in kids.get(key, []) if totals[c] >= 1.0]
            shown = key.split(".")[-1] if depth else key
            tag = f" (n={counts[key]})" if counts[key] > 1 else ""
            lines.append((depth, prefix_last, f"{shown}{tag}", totals[key]))
            for i, c in enumerate(kids_here):
                _walk(c, depth + 1, i == len(kids_here) - 1)
        for k in roots:
            if totals[k] >= 1.0:
                _walk(k, 0, True)
        return lines
    except Exception:
        return []


def _format_tree_lines(tree):
    """Render tree tuples into aligned strings."""
    out = []
    for depth, last, name, ms in tree:
        if depth == 0:
            left = f"  {name}"
        else:
            branch = "`- " if last else "|- "
            left = f"  {'|  ' * (depth - 1)}{branch}{name}"
        out.append(f"{left:<46} {ms:8.1f}ms")
    return out


def _print_scope_tree(scope, label: str, dt: float) -> None:
    """Pre/post timer block: BEGIN line, tree, notes, END line."""
    det = f" {scope['detail']}" if scope.get("detail") else ""
    print(f"[{scope.get('wall0', _timestamp())}] [Profile] {label}{det} BEGIN")
    try:
        tree = _render_tree_lines(scope.get("rows", []))
    except Exception:
        tree = []
    for line in _format_tree_lines(tree):
        print(line)
    try:
        for n in (scope.get("notes") or [])[:4]:
            print(f"  .. {str(n)[:180]}")
    except Exception:
        pass
    print(f"[{_timestamp()}] [Profile] {label} END total={dt:.1f}ms")


@contextmanager
def prof_scope(label: str, min_ms: float = 5.0):
    """One console line per event: nested prof rows collapse into a summary.

    Nested scopes merge into the outermost. Prints only when wall time
    reaches min_ms (silences no-op ticks). Never raises.
    """
    if not _profile_enabled():
        yield None
        return
    scope = {"label": label, "detail": "", "rows": [], "notes": [],
             "t0": time.perf_counter(), "wall0": _timestamp(),
             "min_ms": float(min_ms)}
    with _prof_lock:
        _scope_stack.append(scope)
    try:
        yield scope
    finally:
        try:
            dt = (time.perf_counter() - scope["t0"]) * 1000.0
            with _prof_lock:
                try:
                    if _scope_stack and _scope_stack[-1] is scope:
                        _scope_stack.pop()
                    else:
                        _scope_stack.remove(scope)
                except Exception:
                    pass
                parent = _scope_stack[-1] if _scope_stack else None
            if parent is not None:
                try:
                    parent["rows"].extend(scope["rows"])
                    parent["notes"].extend(scope["notes"][-3:])
                    if scope["detail"]:
                        parent["detail"] = ((parent["detail"] + " " + scope["detail"]).strip())[:200]
                except Exception:
                    pass
            elif dt >= scope["min_ms"]:
                try:
                    _print_scope_tree(scope, label, dt)
                except Exception:
                    pass
        except Exception:
            pass


def prof_report(reset: bool = False) -> str:
    try:
        with _prof_lock:
            items = [(k, _prof_counts.get(k, 0), _prof_totals.get(k, 0.0)) for k in _prof_totals]
        items.sort(key=lambda x: -x[2])
        started = _overlay_start_wall or "n/a"
        try:
            age = f" (+{time.perf_counter() - _overlay_start_mono:.1f}s)" if _overlay_start_mono else ""
        except Exception:
            age = ""
        lines = [
            f"[MeshAnalysisProfile] {_timestamp()}",
            f"  overlay started: {started}{age}",
            f"  last features: {_prof_last_features or 'n/a'}",
        ]
        for k, c, t in items:
            avg = (t / c * 1000.0) if c else 0.0
            lines.append(f"  {k}: total={t*1000.0:.1f}ms n={c} avg={avg:.2f}ms")
        out = "\n".join(lines)
    except Exception as e:
        out = f"[MeshAnalysisProfile] error {e}"
    if reset:
        try:
            with _prof_lock:
                _prof_totals.clear()
                _prof_counts.clear()
        except Exception:
            pass
    return out

# ---- Shared small helpers (single source for former duplicates) ----

def arrays_equal(a, b) -> bool:
    """True when two numpy arrays have identical shape + content.

    Empty arrays compare equal regardless of dtype. Never raises.
    Replaces former handlers._arrays_equal / overlay_controller._same_arrays.
    """
    try:
        if a is b:
            return True
        if getattr(a, "shape", None) != getattr(b, "shape", None):
            return False
        if getattr(a, "size", 0) == 0:
            return True
        return bool(np.array_equal(a, b))
    except Exception:
        return False


def empty_f32() -> np.ndarray:
    """Fresh empty float32 1-D array for clearing pipeline features."""
    return np.zeros((0,), dtype=np.float32)


def copy_rgba4(dst, src) -> None:
    """Copy 4 float color channels with indexed assignment (Blender-safe)."""
    try:
        for i in range(4):
            try:
                dst[i] = float(src[i])
            except Exception:
                pass
    except Exception:
        pass


def register_classes(classes) -> None:
    """Teardown-first register shared by operators / panels / preferences."""
    for _cls in classes:
        try:
            try:
                bpy.utils.unregister_class(_cls)
            except Exception:
                pass
            bpy.utils.register_class(_cls)
        except Exception as e:
            print(f"[Mesh Analysis Overlay] register failed {_cls}: {e}")


def unregister_classes(classes) -> None:
    """Unregister in reverse order. Never raises."""
    for _cls in reversed(classes):
        try:
            bpy.utils.unregister_class(_cls)
        except Exception:
            pass


# Features whose classification depends on vertex positions (not just topology).
# All other features depend only on counts / connectivity / flags.
GEOM_FEATURES = frozenset({"non_planar_faces", "degenerate_faces"})


def get_updated_bmesh_from_depsgraph(obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph) -> bmesh.types.BMesh:
    """Get the most updated mesh from depsgraph.

    Lifetime contract (must be honoured by callers):
    - EDIT mode without modifiers: returns Blender-owned edit bmesh, do NOT free.
    - EDIT mode with modifiers / OBJECT mode: returns owned copy, caller must free.
    """
    if obj.mode == "EDIT":
        # Check for Geometry Nodes in Edit Mode
        has_modifiers = len(obj.modifiers) > 0
        if has_modifiers:
            # For edit mode with modifiers, we need to get the live edit mesh
            # and apply modifiers to it for real-time updates
            try:
                # Get the live edit mesh first
                edit_bm = bmesh.from_edit_mesh(obj.data)
                edit_bm.verts.ensure_lookup_table()
                edit_bm.edges.ensure_lookup_table()
                edit_bm.faces.ensure_lookup_table()

                # Owned copy so caller can free it (from_edit_mesh is Blender-owned).
                return edit_bm.copy()
            except Exception:
                # If anything fails, fall back to edit mesh
                bm = bmesh.from_edit_mesh(obj.data)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
                return bm
        else:
            # Direct BMesh extraction for real-time tracking
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            return bm
    else:
        # OBJECT mode - use evaluated mesh from depsgraph
        evaluated_obj = obj.evaluated_get(depsgraph)
        mesh = evaluated_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)

        try:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            return bm
        finally:
            evaluated_obj.to_mesh_clear()


def free_bmesh_if_owned(obj: bpy.types.Object, bm) -> None:
    """Free a bmesh obtained from get_updated_bmesh_from_depsgraph if owned."""
    if bm is None:
        return
    try:
        if obj.mode == "EDIT" and len(obj.modifiers) == 0:
            # Blender-owned edit bmesh, do not free.
            return
        bm.free()
    except Exception:
        pass


def compute_bmesh_pos_hash(bm) -> int:
    """Cheap position hash to detect vertex moves without topology change.

    Uses numpy reductions (sum / sumsq / min / max) over a foreach_get buffer
    when available. Falls back to sampled Python iteration.
    Collisions are theoretically possible but practically negligible for
    single-stroke edits; topology changes are caught separately by counts.
    """
    try:
        n = len(bm.verts)
    except Exception:
        return 0
    if n == 0:
        return 0
    try:
        foreach_get = getattr(bm.verts, "foreach_get", None)
        if foreach_get is not None:
            arr = np.empty(n * 3, dtype=np.float32)
            foreach_get("co", arr)
            # Use float64 accumulation to avoid overflow / precision drift.
            s1 = float(np.sum(arr, dtype=np.float64))
            # arr * arr creates one temp; acceptable vs full reclassify cost.
            s2 = float(np.sum(arr * arr, dtype=np.float64))
            mn = float(np.min(arr))
            mx = float(np.max(arr))
            # Quantize to 1e-4 to ignore float noise, keep drag detection.
            return hash((n, round(s1, 4), round(s2, 3), round(mn, 5), round(mx, 5)))
    except Exception:
        pass
    # Fallback: sampled Python read (slower, but only on old API).
    try:
        stride = max(1, n // 4096)
        s1 = 0.0
        s2 = 0.0
        mn = float("inf")
        mx = float("-inf")
        for i in range(0, n, stride):
            co = bm.verts[i].co
            for c in (co.x, co.y, co.z):
                s1 += c
                s2 += c * c
                if c < mn:
                    mn = c
                if c > mx:
                    mx = c
        return hash((n, stride, round(s1, 4), round(s2, 3)))
    except Exception:
        return hash((n,))


def extract_vert_arrays(bm) -> Tuple[np.ndarray, np.ndarray]:
    """Extract (verts, normals) as (N,3) float32 using foreach_get when possible."""
    n = len(bm.verts)
    if n == 0:
        empty = np.zeros((0, 3), dtype=np.float32)
        return empty, empty.copy()
    try:
        if hasattr(bm.verts, "foreach_get"):
            flat_co = np.empty(n * 3, dtype=np.float32)
            flat_no = np.empty(n * 3, dtype=np.float32)
            bm.verts.foreach_get("co", flat_co)
            try:
                bm.verts.foreach_get("normal", flat_no)
            except Exception:
                # Default up-vector when normals unavailable.
                flat_no.fill(0.0)
                flat_no[2::3] = 1.0
            return flat_co.reshape((-1, 3)), flat_no.reshape((-1, 3))
    except Exception:
        pass
    # Fallback Python loop (compat only).
    verts = np.empty((n, 3), dtype=np.float32)
    normals = np.empty((n, 3), dtype=np.float32)
    for i, v in enumerate(bm.verts):
        verts[i, 0], verts[i, 1], verts[i, 2] = v.co.x, v.co.y, v.co.z
        normals[i, 0], normals[i, 1], normals[i, 2] = v.normal.x, v.normal.y, v.normal.z
    return verts, normals


def extract_edge_vert_indices(bm) -> np.ndarray:
    """Extract (M,2) int32 edge -> vert indices using foreach_get when possible."""
    m = len(bm.edges)
    if m == 0:
        return np.zeros((0, 2), dtype=np.int32)
    try:
        if hasattr(bm.edges, "foreach_get"):
            flat = np.empty(m * 2, dtype=np.int32)
            bm.edges.foreach_get("vertices", flat)
            return flat.reshape((-1, 2))
    except Exception:
        pass
    arr = np.empty((m, 2), dtype=np.int32)
    for i, e in enumerate(bm.edges):
        arr[i, 0] = e.verts[0].index
        arr[i, 1] = e.verts[1].index
    return arr


def collect_enabled_by_category(props, metadata) -> Tuple[Dict[str, list], List[str]]:
    """Active features grouped by category + flat id list. Single source for panels."""
    active_by_category: Dict[str, list] = {}
    all_active: List[str] = []
    for _category, features in metadata.items():
        try:
            active = [f for f in features if getattr(props, f"{f['id']}_enabled", False)]
        except Exception:
            continue
        if active:
            active_by_category[_category] = active
            all_active.extend(f["id"] for f in active)
    return active_by_category, all_active


def collect_enabled_features(props, metadata) -> Tuple[List[str], Dict[str, tuple], List[str]]:
    """Single place building (enabled_features, feature_colors, all_ids)."""
    enabled: List[str] = []
    colors: Dict[str, tuple] = {}
    all_ids: List[str] = []
    for _category, features in metadata.items():
        for feature in features:
            f_id = feature["id"]
            all_ids.append(f_id)
            try:
                if getattr(props, f"{f_id}_enabled", False):
                    enabled.append(f_id)
                    colors[f_id] = tuple(getattr(props, f"{f_id}_color"))
            except Exception:
                continue
    return enabled, colors, all_ids


@contextmanager
def managed_bmesh(obj, depsgraph):
    """Yield bmesh from get_updated_bmesh_from_depsgraph, freeing if owned.

    Yields None when depsgraph is None or acquisition fails (caller decides).
    Never raises from the free path.
    """
    if depsgraph is None:
        yield None
        return
    bm = get_updated_bmesh_from_depsgraph(obj, depsgraph)
    try:
        yield bm
    finally:
        free_bmesh_if_owned(obj, bm)
