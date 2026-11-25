#!/usr/bin/env python3
"""
FigCraft CLI & Automation Toolkit
Provides live control over FigCraft.app (via JSON-RPC TCP socket)
and offline programmatic manipulation of .figcraft design files.
Designed for Antigravity, Claude Code, Muse Code, and OMP.
"""

import sys
import os
import json
import zipfile
import socket
import subprocess
import time
import argparse
import re
import copy
from typing import Callable, Dict, List, Optional, Any, Union, Tuple

# Make sibling modules (e.g. build_artistic_flow) importable from any cwd.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from design_manifest import (  # noqa: E402
    DesignManifestError,
    contrast_ratio,
    describe_overrides,
    load_design,
    resolve,
    to_builder_tokens,
)

# ---------------------------------------------------------------------------
# DESIGN TOKENS — sourced from DESIGN.md (design-contract/v1)
# ---------------------------------------------------------------------------
# No frozen colour/size dictionary lives here. Every value is resolved from
# the project manifest; a missing or invalid manifest raises an actionable
# error at import time rather than silently using a built-in preset.
DESIGN_DOC = load_design()
DESIGN_THEME = DESIGN_DOC.get("default_theme", "dark")
TOKENS = to_builder_tokens(DESIGN_DOC, DESIGN_THEME)
FONTS = TOKENS["typography"]
CONTENT = TOKENS["content"]
LINT_CONFIG = DESIGN_DOC.get("lint", {})
SPACE = resolve(DESIGN_DOC["tokens"]["semantic"]["space"], DESIGN_DOC, DESIGN_THEME)
TYPE = resolve(DESIGN_DOC["tokens"]["semantic"]["type"], DESIGN_DOC, DESIGN_THEME)
COMPONENT = resolve(DESIGN_DOC["tokens"]["component"], DESIGN_DOC, DESIGN_THEME)
GEOMETRY = DESIGN_DOC.get("geometry", {})

# Hard ceiling for the unique-id probe and for board/component searches. These
# cut-loop guards keep a malformed or cyclic document from hanging a build.
MAX_ID_PROBE = 100000
MAX_SEARCH_NODES = 100000


def get_tokens(theme: Optional[str] = None) -> Dict[str, Any]:
    """Return builder tokens resolved for an explicit theme."""
    return to_builder_tokens(DESIGN_DOC, theme or DESIGN_THEME)

def hex_to_rgba(hex_str: str, alpha: float = 1.0) -> Dict[str, float]:
    """Convert hex color (#RRGGBB or #RRGGBBAA) to FigCraft RGBA float dict (0.0 - 1.0)."""
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 8:
        r = int(hex_str[0:2], 16) / 255.0
        g = int(hex_str[2:4], 16) / 255.0
        b = int(hex_str[4:6], 16) / 255.0
        a = (int(hex_str[6:8], 16) / 255.0) * alpha
    elif len(hex_str) == 6:
        r = int(hex_str[0:2], 16) / 255.0
        g = int(hex_str[2:4], 16) / 255.0
        b = int(hex_str[4:6], 16) / 255.0
        a = alpha
    elif len(hex_str) == 3:
        r = int(hex_str[0]*2, 16) / 255.0
        g = int(hex_str[1]*2, 16) / 255.0
        b = int(hex_str[2]*2, 16) / 255.0
        a = alpha
    else:
        r, g, b, a = 1.0, 1.0, 1.0, alpha
    return {"r": round(r, 4), "g": round(g, 4), "b": round(b, 4), "a": round(a, 4)}

def make_solid_fill(hex_str: str, opacity: float = 1.0) -> List[Dict[str, Any]]:
    return [{
        "type": "solid",
        "color": hex_to_rgba(hex_str),
        "opacity": opacity,
        "visible": True,
        "blend": "normal"
    }]

def make_solid_stroke(hex_str: str, opacity: float = 1.0) -> List[Dict[str, Any]]:
    return [{
        "type": "solid",
        "color": hex_to_rgba(hex_str),
        "opacity": opacity,
        "visible": True,
        "blend": "normal"
    }]

# ---------------------------------------------------------------------------
# TEXT & ICONS (measurement + Lucide; used by create_text/build_button)
# ---------------------------------------------------------------------------
def estimate_text_width(text: str, font_size: float, font_family: str = "Inter") -> float:
    """Estimate text width in px (same formula as test_layout_engine.py).

    Mono ~0.62*size, Space Grotesk ~0.58*size, others ~0.52*size, +2 padding.
    Used by create_text/build_button so headless output does not overflow.
    Calibration 2026-11-08: engine/app median = 0.94x the older estimate
    (0.55) for Latin text; CJK ~0.98 (unchanged). The estimate is deliberately
    slightly conservative (box >= glyph) so text is never clipped.
    """
    if "Mono" in font_family:
        return len(text) * font_size * 0.62 + 2
    if "Space" in font_family or "Grotesk" in font_family:
        return len(text) * font_size * 0.58 + 2
    return len(text) * font_size * 0.52 + 2


# Lucide icon paths v0.469.0 (grid 24, round stroke) for buttons.
# Scale = icon_dim/24. Never draw an icon as a rectangle outline.
ICON_PATHS = {
    "x": ["M18 6 6 18", "m6 6 12 12"],
    "check": ["M20 6 9 17l-5-5"],
    "chevron-down": ["m6 9 6 6 6-6"],
    "chevron-right": ["m9 18 6-6-6-6"],
    "chevron-left": ["m15 18-6-6 6-6"],
    "plus": ["M5 12h14", "M12 5v14"],
    "minus": ["M5 12h14"],
    "arrow-right": ["M5 12h14", "m12 5 7 7-7 7"],
    "arrow-left": ["M19 12H5", "m12 19-7-7 7-7"],
}


# ---------------------------------------------------------------------------
# FIGCRAFT DOCUMENT OBJECT (OFFLINE FILE BUILDER)
# ---------------------------------------------------------------------------
class FigcraftDocument:
    """Represents a .figcraft design document (ZIP archive containing document.json)."""

    def __init__(self, name: str = "Untitled"):
        self.name = name
        self.doc: Dict[str, Any] = {
            "format": "figcraft",
            "version": 1,
            "imageIndex": [],
            "name": name,
            "pages": [1],
            "current_page": 1,
            "next_id": 10,
            "styles": [],
            "variables": {"collections": [], "variables": []},
            "document_colors": [],
            "comments": [],
            "nodes": {}
        }
        # Create default Page 1
        self.doc["nodes"]["1"] = {
            "id": 1,
            "name": "Page 1",
            "type": "page",
            "background": hex_to_rgba(TOKENS["colors"]["bg_app"]),
            "children": [],
            "flows": [],
            "guides": [],
            "prototype": {
                "device": "None",
                "background": hex_to_rgba(TOKENS["colors"]["bg_app"]),
                "rotation": "portrait"
            },
            "width": 0.0,
            "height": 0.0
        }
        self.file_path: Optional[str] = None

    def page_ids(self) -> List[int]:
        """Return every page id in document order (``pages[0..N]``)."""
        return [int(pid) for pid in (self.doc.get("pages") or [])]

    def resolve_page(self, page_index: Optional[int] = None,
                     page_name: Optional[str] = None) -> int:
        """Resolve a page by index or name; index 0 is the default."""
        ids = self.page_ids()
        if page_name is not None:
            for pid in ids:
                page = self.doc["nodes"].get(str(pid), {})
                if isinstance(page, dict) and str(page.get("name")) == page_name:
                    return pid
            available = [str(self.doc["nodes"].get(str(pid), {}).get("name"))
                         for pid in ids]
            raise ValueError("page %r not found; available pages: %s"
                             % (page_name, ", ".join(available)))
        index = 0 if page_index is None else int(page_index)
        if index < 0 or index >= len(ids):
            raise ValueError("page_index %d is out of range for %d page(s)"
                             % (index, len(ids)))
        return ids[index]

    def add_page(self, name: str, background: Optional[str] = None) -> int:
        """Append a new page so multi-page documents can be built offline."""
        existing = [str(self.doc["nodes"].get(str(pid), {}).get("name"))
                    for pid in self.page_ids()]
        if name in existing:
            raise ValueError("page %r already exists" % name)
        nid = self.alloc_id()
        base = hex_to_rgba(background or TOKENS["colors"]["bg_app"])
        self.doc["nodes"][str(nid)] = {
            "id": nid,
            "name": name,
            "type": "page",
            "background": base,
            "children": [],
            "flows": [],
            "guides": [],
            "prototype": {
                "device": "None",
                "background": base,
                "rotation": "portrait",
            },
            "width": 0.0,
            "height": 0.0,
        }
        self.doc.setdefault("pages", []).append(nid)
        return nid

    def ensure_named_pages(self, names: List[str]) -> List[int]:
        """Return one existing-or-new page id per name, in that order.

        The document's first page is renamed in place, so a fresh document has
        exactly the requested named pages and no empty leading page. Repeated
        calls are idempotent and never drop or duplicate later pages.
        """
        if not names:
            return self.page_ids()
        ids = self.page_ids()
        if not ids:
            ids = [self.add_page(names[0])]
        first = self.doc["nodes"].get(str(ids[0]), {})
        if isinstance(first, dict):
            first["name"] = names[0]
        result = [ids[0]]
        for name in names[1:]:
            match = None
            for pid in self.page_ids():
                page = self.doc["nodes"].get(str(pid), {})
                if isinstance(page, dict) and str(page.get("name")) == name:
                    match = pid
                    break
            if match is None:
                match = self.add_page(name)
            result.append(match)
        self.doc["current_page"] = result[0]
        return result

    @classmethod
    def load(cls, file_path: str) -> "FigcraftDocument":
        """Load an existing .figcraft file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        inst = cls()
        inst.file_path = file_path
        with zipfile.ZipFile(file_path, "r") as z:
            with z.open("document.json") as f:
                inst.doc = json.load(f)
        inst.name = inst.doc.get("name", os.path.splitext(os.path.basename(file_path))[0])
        return inst

    def resolve_layout(self):
        """Resolve two-pass AutoLayout on every page, ``pages[0..N]``."""
        try:
            from build_artistic_flow import resolve_tree_layout
        except ImportError as exc:
            raise RuntimeError(
                "build_artistic_flow.py must be in the same scripts/ directory as "
                "figcraft_tool.py (resolve_tree_layout)"
            ) from exc
        for pid in self.doc.get("pages", [1]):
            page = self.doc["nodes"].get(str(pid))
            if page:
                for sid in page.get("children", []):
                    resolve_tree_layout(self.doc["nodes"], sid)

    def save(self, output_path: Optional[str] = None):
        """Save the document to .figcraft file."""
        try:
            self.resolve_layout()
        except Exception as e:
            # Previously a silent except-pass hid reflow mistakes. Now it is
            # warn-only on stderr (the build still proceeds, SKILL §2).
            print(f"figcraft_tool: resolve_layout failed ({e}) — saving without reflow.",
                  file=sys.stderr)

        # All pages are reflowed above and saved verbatim below. The live canvas
        # may display pages[0] by default, but no page is dropped here; use the
        # page selector in the terminal/auditor to inspect later pages.
        page_count = len(self.doc.get("pages") or [])
        if page_count > 1:
            print("figcraft_tool: multi-page document with %d pages; all pages "
                  "were reflowed and preserved. The live canvas may show only "
                  "pages[0] by default." % page_count, file=sys.stderr)

        path = output_path or self.file_path
        if not path:
            raise ValueError("No file path specified for save.")
        
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        
        # 1x1 transparent PNG thumbnail placeholder if not already there
        png_1x1 = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        
        existing_thumb = None
        if self.file_path and os.path.exists(self.file_path):
            try:
                with zipfile.ZipFile(self.file_path, "r") as z:
                    if "thumbnail.png" in z.namelist():
                        existing_thumb = z.read("thumbnail.png")
            except Exception:
                pass

        temp_path = path + ".tmp"
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            # Compact like the engine (SKILL §7.3: schema from live save):
            # indent=2 doubles document.json size without benefit.
            z.writestr("document.json", json.dumps(self.doc, separators=(",", ":")))
            z.writestr("thumbnail.png", existing_thumb or png_1x1)
        
        os.replace(temp_path, path)
        self.file_path = path

    def alloc_id(self) -> int:
        """Allocate a node id that is provably unused in this document.

        A loaded file can carry a stale ``next_id``. Probing against the real
        node map with a bounded scan guarantees fresh ids for duplicated
        subtrees, so a rebuilt board can never collide with an existing node.
        """
        cur = int(self.doc.get("next_id", 10))
        used = self.doc.get("nodes", {})
        for _ in range(MAX_ID_PROBE):  # cut-loop guard
            if str(cur) not in used:
                self.doc["next_id"] = cur + 1
                return cur
            cur += 1
        raise RuntimeError("could not allocate a unique node id after %d probes"
                           % MAX_ID_PROBE)

    def add_node(self, node: Dict[str, Any], parent_id: int = 1) -> int:
        nid = node.get("id")
        if not nid:
            nid = self.alloc_id()
            node["id"] = nid
        
        node["parent"] = parent_id
        self.doc["nodes"][str(nid)] = node

        # Append to parent's children list
        parent = self.doc["nodes"].get(str(parent_id))
        if parent:
            if "children" not in parent:
                parent["children"] = []
            if nid not in parent["children"]:
                parent["children"].append(nid)

        return nid

    @staticmethod
    def _sanitize_node(value: Any, depth: int = 0) -> Any:
        """Drop any literal ``overrides`` key from a node payload.

        ``overrides`` is a builder-input concept, never a node property. A
        bounded recursive strip also removes residual keys left by older files
        so a duplicated subtree can never reintroduce one into document.json.
        """
        if depth > 32:  # cut-loop guard for malformed/cyclic payloads
            return value
        if isinstance(value, dict):
            return {
                key: FigcraftDocument._sanitize_node(item, depth + 1)
                for key, item in value.items() if key != "overrides"
            }
        if isinstance(value, list):
            return [FigcraftDocument._sanitize_node(item, depth + 1) for item in value]
        return value

    def duplicate_node(
        self,
        node_id: int,
        parent_id: Optional[int] = None,
        name: Optional[str] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        overrides: Optional[Dict[str, Any]] = None,
        page_index: Optional[int] = None,
        page_name: Optional[str] = None,
    ) -> Optional[int]:
        """Duplicate a component subtree for component-first reuse.

        Every descendant gets a fresh id, its ``parent`` link is remapped, and
        fills, strokes, radius, padding, and layout are preserved verbatim.
        ``overrides`` are applied directly onto the duplicated node's real
        properties (deep-copied so the source template is never mutated); the
        builder-only ``overrides`` key is never written into node JSON.
        A visited set and a hard ceiling keep the traversal bounded even if a
        malformed document contains a parent cycle. ``page_index`` /
        ``page_name`` select the destination page when no explicit parent is
        given, so a component can be copied across ``pages[0..N]``.
        """
        root = self.doc["nodes"].get(str(node_id))
        if not isinstance(root, dict):
            return None
        if parent_id is not None:
            explicit_parent = parent_id
        elif page_index is not None or page_name is not None:
            # An explicit target page moves the copy onto that page.
            explicit_parent = self.resolve_page(page_index, page_name)
        else:
            explicit_parent = None
        target_parent = (explicit_parent if explicit_parent is not None
                         else root.get("parent", 1))
        clean_overrides = self._sanitize_node(overrides or {})
        if not isinstance(clean_overrides, dict):
            clean_overrides = {}
        id_map: Dict[int, int] = {}
        todo = [node_id]
        visited: set = set()
        while todo and len(visited) < 100000:  # cut-loop guard
            old_id = str(todo.pop())
            if old_id in visited:
                continue
            visited.add(old_id)
            source = self.doc["nodes"].get(old_id)
            if not isinstance(source, dict):
                continue
            for child in source.get("children", []) or []:
                todo.append(child)

        # Allocate the root first so the duplicate root id is deterministic.
        ordered = [str(node_id)] + sorted(visited - {str(node_id)})
        for old_id in ordered:
            source = self.doc["nodes"][old_id]
            new_id = self.alloc_id()
            id_map[int(old_id)] = new_id
            clone = self._sanitize_node(copy.deepcopy(source))
            clone["id"] = new_id
            if old_id == str(node_id):
                if explicit_parent is not None:
                    clone["parent"] = explicit_parent
                if name is not None:
                    clone["name"] = name
                if x is not None or y is not None:
                    transform = list(clone.get("transform", [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]))
                    if x is not None:
                        transform[4] = float(x)
                    if y is not None:
                        transform[5] = float(y)
                    clone["transform"] = transform
                if clean_overrides:
                    clone.update(copy.deepcopy(clean_overrides))
                clone.pop("overrides", None)  # belt-and-braces: never a node key
            self.doc["nodes"][str(new_id)] = clone

        # Remap links only after every id is allocated, so a child processed
        # before its parent still points at the duplicated parent.
        for old_id, new_id in id_map.items():
            clone = self.doc["nodes"][str(new_id)]
            if old_id != int(node_id):
                old_parent = self.doc["nodes"][str(old_id)].get("parent")
                clone["parent"] = (id_map.get(int(old_parent), target_parent)
                                   if old_parent is not None else target_parent)
            clone["children"] = [id_map[int(child)] for child in clone.get("children", []) or []
                                 if int(child) in id_map]
        parent = self.doc["nodes"].get(str(target_parent))
        if isinstance(parent, dict):
            new_root = id_map.get(int(node_id))
            if new_root is not None:
                children = parent.setdefault("children", [])
                if new_root not in children:
                    children.append(new_root)
        return id_map.get(int(node_id))

    def component_first(self, component_id: int, parent_id: int,
                        **overrides: Any) -> Optional[int]:
        """Duplicate an existing component (the component-first workflow).

        Accepts real node properties as keyword arguments and also flattens an
        explicit ``overrides={...}`` mapping, so callers can express either
        ``name=..., overrides={"fills": ...}`` or direct ``fills=...``. The
        builder-only ``overrides`` key is never forwarded as a node property.
        """
        clean: Dict[str, Any] = {}
        for key, value in overrides.items():
            if key == "overrides" and isinstance(value, dict):
                clean.update(value)
            else:
                clean[key] = value
        clean.pop("overrides", None)
        return self.duplicate_node(component_id, parent_id=parent_id,
                                   overrides=clean or None)

    def ensure_board(self, name: str, x: float = 0.0, y: float = 0.0,
                     width: Optional[float] = None, height: Optional[float] = None,
                     fill: Optional[str] = None, corner_radius: float = 0.0,
                     clip: bool = True, page_index: Optional[int] = None,
                     page_name: Optional[str] = None) -> int:
        """Reuse an existing board on the selected page or create it once.

        The default target is ``pages[0]`` because the live canvas shows that
        page first, but any page in ``pages[0..N]`` can be selected by index or
        name. Repeated calls with the same name return the same frame.
        """
        page_id = self.resolve_page(page_index, page_name)
        page = self.doc["nodes"].get(str(page_id), {})
        for child_id in page.get("children", []) or []:
            child = self.doc["nodes"].get(str(child_id))
            if isinstance(child, dict) and child.get("name") == name:
                return int(child_id)
        screen = GEOMETRY.get("screen", {})
        return self.create_frame(
            name, page_id,
            width=float(width) if width is not None else float(screen.get("width", 1280)),
            height=float(height) if height is not None else float(screen.get("height", 960)),
            x=x, y=y, fill=fill, corner_radius=corner_radius, clip=clip,
        )

    def find_or_reuse_component(
        self,
        name: str,
        parent_id: Optional[int] = None,
        builder: Optional[Callable[[], int]] = None,
        page_index: Optional[int] = None,
        page_name: Optional[str] = None,
    ) -> Optional[int]:
        """Return a named component, building it only when it is absent.

        With no parent or page selector the search covers every page, so reuse
        works across ``pages[0..N]``. A parent scopes the search to its subtree;
        ``page_index`` / ``page_name`` scope it to one page. An existing node
        is returned untouched for :meth:`duplicate_node` to copy.
        """
        if parent_id is not None:
            roots = [parent_id]
        elif page_index is not None or page_name is not None:
            roots = [self.resolve_page(page_index, page_name)]
        else:
            roots = self.page_ids()
        stack = [int(root) for root in roots]
        seen = set()
        while stack and len(seen) < MAX_SEARCH_NODES:  # cut-loop guard
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            node = self.doc["nodes"].get(str(current))
            if not isinstance(node, dict):
                continue
            if node.get("name") == name and node.get("type") != "page":
                return current
            stack.extend(int(child) for child in node.get("children", []) or []
                         if str(child) in self.doc["nodes"])
        if builder is None:
            return None
        built = builder()
        return int(built) if built is not None else None

    def prevent_clipping(self, node_id: int) -> bool:
        """Enable clipping on a screen-level frame to contain child content."""
        node = self.doc["nodes"].get(str(node_id))
        if not isinstance(node, dict) or node.get("type") != "frame":
            return False
        threshold = GEOMETRY.get("screen", {}).get("width", 1000)
        if (node.get("width") or 0) >= threshold:
            node["clip"] = True
            return True
        return False

    # --- Node Creation Helpers ---

    def create_frame(
        self,
        name: str,
        parent_id: int = 1,
        width: float = 100.0,
        height: float = 100.0,
        x: float = 0.0,
        y: float = 0.0,
        fill: Optional[str] = None,
        stroke: Optional[str] = None,
        stroke_width: float = 1.0,
        corner_radius: float = 0.0,
        layout_mode: str = "none",  # "none" | "horizontal" | "vertical" | "grid"
        gap: float = 0.0,
        padding: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
        main_align: str = "min",    # "min" | "center" | "max" | "spaceBetween"
        cross_align: str = "min",   # "min" | "center" | "max"
        sizing_h: str = "fixed",    # "fixed" | "hug" | "fill"
        sizing_v: str = "fixed",    # "fixed" | "hug" | "fill"
        clip: bool = False
    ) -> int:
        nid = self.alloc_id()
        frame_node = {
            "id": nid,
            "name": name,
            "type": "frame",
            "parent": parent_id,
            "children": [],
            "transform": [1.0, 0.0, 0.0, 1.0, float(x), float(y)],
            "width": float(width),
            "height": float(height),
            "clip": clip,
        }
        if fill:
            frame_node["fills"] = make_solid_fill(fill)
        else:
            frame_node["fills"] = []

        if stroke:
            frame_node["strokes"] = make_solid_stroke(stroke)
            frame_node["stroke_weight"] = float(stroke_width)

        if corner_radius > 0:
            frame_node["corners"] = {
                "radii": [corner_radius, corner_radius, corner_radius, corner_radius],
                "smoothing": 0.0
            }

        if layout_mode != "none":
            t, r, b, l = padding
            frame_node["layout"] = {
                "mode": layout_mode,
                "wrap": False,
                "gap": float(gap),
                "cross_gap": float(gap),
                "padding": [float(t), float(r), float(b), float(l)],
                "main_align": main_align,
                "cross_align": cross_align,
                "content_align": "auto",
                "grid_columns": 2,
                "grid_rows": 2,
                "column_tracks": [],
                "row_tracks": [],
                "strokes_included": True,
                "reverse_z": False
            }

        # Child sizing inside parent layout
        if parent_id != 1:
            frame_node["child_layout"] = {
                "sizing_h": sizing_h,
                "sizing_v": sizing_v,
                "absolute": False,
                "min_w": None, "max_w": None,
                "min_h": None, "max_h": None,
                "grid_column": None, "grid_row": None,
                "grid_column_span": 0, "grid_row_span": 0
            }

        return self.add_node(frame_node, parent_id)

    def create_text(
        self,
        name: str,
        text: str,
        parent_id: int,
        font_size: float = 13.0,
        font_weight: str = "Regular", # "Regular" | "Medium" | "SemiBold" | "Bold"
        font_family: str = "Inter",
        color: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        width: Optional[float] = None,
        height: Optional[float] = None,
        sizing_h: str = "hug",
        sizing_v: str = "hug",
        max_w: Optional[float] = None,
    ) -> int:
        # R1: prevent text overflow (node 1020 was 279px inside a 233.6px card).
        # Engine parity 2026-11-08: reflow NEVER overwrites an already-measured
        # text size (the app save uses real font metrics). Therefore create
        # stores 0 (empty) when the caller gives no explicit width; reflow
        # fills it via estimation ONLY when empty. S-08 stays green because
        # lint inspects the post-save result, not the birth value.
        # Visual truncation is the renderer's job; the stored width stays honest.
        color = color or CONTENT.get("sheet") or TOKENS["colors"]["ink_primary"]
        estimated = estimate_text_width(text, font_size, font_family)
        if width is None:
            width = 0.0
        elif estimated > width:
            width = min(estimated, max_w) if max_w else estimated
        if height is None:
            height = 0.0
        nid = self.alloc_id()
        text_node = {
            "id": nid,
            "name": name,
            "type": "text",
            "parent": parent_id,
            "characters": text,
            "transform": [1.0, 0.0, 0.0, 1.0, float(x), float(y)],
            "width": float(width),
            "height": float(height),
            "fills": make_solid_fill(color),
            "style": {
                "font_family": font_family,
                "font_style": font_weight,
                "font_size": float(font_size),
                "line_height": {"unit": "auto"},
                "letter_spacing": {"unit": "pixels", "value": 0.0},
                "decoration": "none",
                "case": "original",
                "fills": None,
                "link": None
            },
            "child_layout": {
                "sizing_h": sizing_h,
                "sizing_v": sizing_v,
                "absolute": False,
                "min_w": None, "max_w": None,
                "min_h": None, "max_h": None,
                "grid_column": None, "grid_row": None,
                "grid_column_span": 0, "grid_row_span": 0
            }
        }
        return self.add_node(text_node, parent_id)

    def create_vector(
        self,
        name: str,
        path_data: List[str],
        parent_id: int,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 12.0,
        height: float = 12.0,
        stroke: Optional[str] = None,
        stroke_width: float = 1.5,
    ) -> int:
        """Create an icon vector (Lucide 24-grid) with the engine's real file schema.

        Proven via a live session (probe node → save → read document.json):
        the engine stores a vector network {vertices[{x,y,radius}],
        segments[{a,b,ta,tb}], regions[]}, NOT a path string. TRANSFORM
        semantics: render position = the stored transform as is; the live
        engine ADDS bbox-min when creating via API. Because files are read
        raw, paths are normalised first (bbox-min → 0,0, scale width/24) so
        transform (x, y) equals the exact render position — no node.set
        correction needed. Stroke colour = the `strokes` list (solid paint)
        plus `stroke` metadata (weight/align/round cap as in Lucide); BOTH are
        required — a file without `strokes` renders invisible. See the log
        for context.
        """
        import re as _re
        scale = float(width) / 24.0 if width else 1.0

        def _subpaths() -> List[List[Tuple[float, float]]]:
            """Parse a path into subpaths (one per M/m; Z closes).

            Segments ONLY connect points inside the same subpath —
            cross-subpath segments draw stray lines (an old bug gave the x icon
            a diagonal tail). C curves are split per control point
            (documented approximation, sufficient for the Lucide icon set).
            """
            subs: List[List[Tuple[float, float]]] = []
            cur: List[Tuple[float, float]] = []
            for d in path_data:
                # Each path string is independent (one SVG d attribute): the
                # start point resets to (0,0). Without this, "m12 5..." in the
                # second string of an arrow is measured from the end of the
                # first string (overflowing to 31,36 outside the grid 24).
                cx = cy = sx = sy = 0.0
                toks = _re.findall(r"[MmLlHhVvCcZz]|-?\d*\.?\d+", d)
                cmd = "M"
                i = 0
                while i < len(toks):
                    t = toks[i]
                    if _re.fullmatch(r"[MmLlHhVvCcZz]", t):
                        cmd = t
                        i += 1
                        continue
                    if cmd == "Z":
                        if cur:
                            cur.append((sx, sy))
                        i += 1
                        continue
                    # SVG: coordinate pairs after M/m = implicit lineto.
                    # Without this, "M18 6 6 18" splits into two 1-point
                    # subpaths (the x icon loses its segment).
                    if cmd == "M":
                        if cur:
                            subs.append(cur)
                        cur = []
                        cx, cy = float(toks[i]), float(toks[i + 1])
                        i += 2
                        sx, sy = cx, cy
                        cur.append((cx, cy))
                        cmd = "L"
                        continue
                    if cmd == "m":
                        if cur:
                            subs.append(cur)
                        cur = []
                        cx, cy = cx + float(toks[i]), cy + float(toks[i + 1])
                        i += 2
                        sx, sy = cx, cy
                        cur.append((cx, cy))
                        cmd = "l"
                        continue
                    if cmd in "ML":
                        cx, cy = float(toks[i]), float(toks[i + 1])
                        i += 2
                    elif cmd in "ml":
                        cx, cy = cx + float(toks[i]), cy + float(toks[i + 1])
                        i += 2
                    elif cmd == "H":
                        cx = float(toks[i])
                        i += 1
                    elif cmd == "h":
                        cx = cx + float(toks[i])
                        i += 1
                    elif cmd == "V":
                        cy = float(toks[i])
                        i += 1
                    elif cmd == "v":
                        cy = cy + float(toks[i])
                        i += 1
                    elif cmd in "Cc":
                        vals = [float(toks[i + k]) for k in range(6)]
                        if cmd == "c":
                            vals = [vals[0] + cx, vals[1] + cy, vals[2] + cx,
                                    vals[3] + cy, vals[4] + cx, vals[5] + cy]
                        cur.extend([(vals[0], vals[1]), (vals[2], vals[3])])
                        cx, cy = vals[4], vals[5]
                        i += 6
                    else:
                        raise ValueError(f"create_vector: unsupported path command '{cmd}'")
                    cur.append((cx, cy))
            if cur:
                subs.append(cur)
            if not subs:
                raise ValueError("create_vector: empty path, no points")
            return subs

        subs = _subpaths()
        all_pts = [p for sub in subs for p in sub]
        min_x = min(p[0] for p in all_pts)
        min_y = min(p[1] for p in all_pts)
        verts: List[Dict[str, float]] = []
        segs: List[Dict[str, Any]] = []
        for sub in subs:
            base = len(verts)
            for px, py in sub:
                verts.append({
                    "x": round((px - min_x) * scale, 3),
                    "y": round((py - min_y) * scale, 3),
                    "radius": 0.0,
                })
            segs.extend(
                {"a": base + k, "b": base + k + 1, "ta": [0.0, 0.0], "tb": [0.0, 0.0]}
                for k in range(len(sub) - 1)
            )
        max_x = max((v["x"] for v in verts), default=0.0)
        max_y = max((v["y"] for v in verts), default=0.0)
        nid = self.alloc_id()
        vec_node: Dict[str, Any] = {
            "id": nid,
            "name": name,
            "type": "vector",
            "network": {"vertices": verts, "segments": segs, "regions": []},
            "parent": parent_id,
            "blend": "normal",
            "transform": [1.0, 0.0, 0.0, 1.0, float(x), float(y)],
            "width": float(max_x),
            "height": float(max_y),
        }
        if stroke:
            # The file renderer reads `strokes` (painted list) + `stroke`
            # (weight/align/cap metadata dict). Proven: a live-created,
            # rendered node stores BOTH; a file without `strokes` is invisible
            # even with a valid network (empty regions[] → fills do not apply
            # to open subpaths).
            vec_node["fills"] = []
            vec_node["strokes"] = make_solid_stroke(stroke)
            vec_node["stroke"] = {
                "weight": float(stroke_width),
                "align": "center",
                "sides": None,
                "cap_start": "round",
                "cap_end": "round",
                "join": "round",
                "miter_limit": 4.0,
                "dashes": [],
            }
        else:
            vec_node["fills"] = []
        return self.add_node(vec_node, parent_id)

    def build_connector(
        self,
        name: str,
        from_id: int,
        to_id: int,
        parent_id: int,
        from_side: str = "right",  # "right"|"left"|"top"|"bottom" (side midpoint)
        to_side: str = "left",      # "right"|"left"|"top"|"bottom"
        style: str = "solid",       # "solid" | "dashed"
        color: Optional[str] = None,
        width: float = 2.0,
        offset: float = 0.0,        # shift the centre line (e.g. upward loopback)
    ) -> int:
        """Orthogonal arrow between nodes (S-03) — replaces ad-hoc vectors.

        Anchor at the side midpoint; one-bend Manhattan route; the arrow
        head follows the last segment. The network uses raw pixels (not the
        grid-24 create_vector scheme). The from->to topology is explicit so
        orphaned or reversed arrows are caught during review.
        """
        nodes = self.doc["nodes"]
        a, b = nodes[str(from_id)], nodes[str(to_id)]
        ax, ay, aw, ah = a["transform"][4], a["transform"][5], a["width"], a["height"]
        bx, by, bw, bh = b["transform"][4], b["transform"][5], b["width"], b["height"]

        def anchor(x, y, w, h, side):
            return {
                "right": (x + w, y + h / 2), "left": (x, y + h / 2),
                "bottom": (x + w / 2, y + h), "top": (x + w / 2, y),
            }[side]

        p1, p2 = anchor(ax, ay, aw, ah, from_side), anchor(bx, by, bw, bh, to_side)
        x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
        if from_side in ("left", "right") and to_side in ("left", "right"):
            if y1 == y2:
                pts = [p1, p2]
            else:
                mx = (x1 + x2) / 2.0
                pts = [p1, (mx, y1), (mx, y2), p2]
        elif from_side in ("top", "bottom") and to_side in ("top", "bottom"):
            if x1 == x2 and not offset:
                pts = [p1, p2]
            else:
                my = (y1 + y2) / 2.0 + offset
                pts = [p1, (x1, my), (x2, my), p2]
        elif from_side in ("left", "right"):
            pts = [p1, p2] if y1 == y2 else [p1, (x2, y1), p2]
        else:
            pts = [p1, p2] if x1 == x2 else [p1, (x1, y2), p2]
        # Arrow head follows the direction of the last segment.
        (qx, qy), (tx, ty) = pts[-2], pts[-1]
        head = 10.0
        dx = 1 if tx > qx else (-1 if tx < qx else 0)
        dy = 1 if ty > qy else (-1 if ty < qy else 0)
        base = (tx - dx * head, ty - dy * head)
        if dx:
            wings = [(base[0], base[1] - head * 0.55), (tx, ty), (base[0], base[1] + head * 0.55)]
        else:
            wings = [(base[0] - head * 0.55, base[1]), (tx, ty), (base[0] + head * 0.55, base[1])]
        main = pts[:-1] + [base]
        subpaths = [main, wings]
        verts, segs = [], []
        for sub in subpaths:
            base_i = len(verts)
            for px, py in sub:
                verts.append({"x": round(px, 3), "y": round(py, 3), "radius": 0.0})
            segs.extend(
                {"a": base_i + k, "b": base_i + k + 1, "ta": [0.0, 0.0], "tb": [0.0, 0.0]}
                for k in range(len(sub) - 1))
        stroke_color = color or TOKENS["colors"]["ink_muted"]
        node = {
            "id": self.alloc_id(), "name": name, "type": "vector",
            "network": {"vertices": verts, "segments": segs, "regions": []},
            "parent": 0, "blend": "normal",
            "transform": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            "width": max(v["x"] for v in verts),
            "height": max(v["y"] for v in verts),
            "fills": [], "strokes": make_solid_stroke(stroke_color),
            "stroke": {"weight": float(width), "align": "center", "sides": None,
                       "cap_start": "round", "cap_end": "round",
                       "join": "round", "miter_limit": 4.0,
                       "dashes": [6.0, 4.0] if style == "dashed" else []},
        }
        return self.add_node(node, parent_id)

    # ------------------------------------------------------------------
    # Builder v2.4 (SKILL §8 contract): dialog, empty, error, ledger, pipe
    # ------------------------------------------------------------------
    def build_dialog(
        self,
        name: str,
        title: str,
        body_text: str,
        confirm_label: str,
        parent_id: int,
        width: float = 1280.0,
        height: float = 960.0,
    ) -> int:
        """Modal: scrim + card + header (question + Close) + body + footer (1 primary + Cancel)."""
        wrap = self.create_frame(name, parent_id, width, height,
                                 fill=None, sizing_h="fill", sizing_v="fill")
        scrim = self.create_frame("Scrim", wrap, width, height,
                                 fill=CONTENT["scrim"], sizing_h="fill", sizing_v="fill")
        self.doc["nodes"][str(scrim)]["fills"][0]["opacity"] = 0.6
        dw, dh = 480.0, 300.0
        card = self.create_frame("Dialog", wrap, dw, dh,
                                 x=(width - dw) / 2.0, y=(height - dh) / 2.0,
                                 fill=TOKENS["colors"]["surface_card"],
                                 stroke=TOKENS["colors"]["border_accent"],
                                 corner_radius=12.0, layout_mode="vertical",
                                 gap=0.0, padding=(0.0, 0.0, 0.0, 0.0),
                                 sizing_h="fixed", sizing_v="fixed")
        head = self.create_frame("DialogHeader", card, dw, 56.0,
                                 layout_mode="horizontal", gap=8.0,
                                 padding=(12.0, 16.0, 12.0, 16.0),
                                 main_align="spaceBetween", cross_align="center",
                                 sizing_h="fill", sizing_v="fixed")
        self.create_text("Title", title, head, font_size=15.0,
                         font_weight="SemiBold",
                         font_family=TOKENS["typography"]["font_brand"],
                         color=TOKENS["colors"]["ink_primary"])
        self.build_button("Btn_Tutup", "Close", head, variant="ghost", size="sm")
        dbody = self.create_frame("DialogBody", card, dw, 120.0,
                                  layout_mode="vertical", gap=6.0,
                                  padding=(8.0, 16.0, 8.0, 16.0),
                                  sizing_h="fill", sizing_v="fixed")
        self.create_text("Body", body_text, dbody, font_size=13.0,
                         color=TOKENS["colors"]["ink_secondary"])
        foot = self.create_frame("DialogFooter", card, dw, 64.0,
                                 layout_mode="horizontal", gap=8.0,
                                 padding=(12.0, 16.0, 12.0, 16.0),
                                 main_align="max", cross_align="center",
                                 sizing_h="fill", sizing_v="fixed")
        self.build_button("Btn_Confirm", confirm_label, foot,
                          variant="primary", size="md")
        self.build_button("Btn_Batal", "Cancel", foot,
                          variant="ghost", size="md")
        return wrap

    def build_empty_state(
        self,
        name: str,
        title: str,
        desc: str,
        action_label: str,
        parent_id: int,
        width: float = 400.0,
    ) -> int:
        """Empty state: title + description + action. No illustration."""
        box = self.create_frame(name, parent_id, width, 180.0,
                                fill=None, layout_mode="vertical", gap=12.0,
                                padding=(24.0, 24.0, 24.0, 24.0),
                                sizing_h="fixed", sizing_v="fixed")
        self.create_text("Title", title, box, font_size=15.0,
                         font_weight="SemiBold",
                         color=TOKENS["colors"]["ink_primary"])
        self.create_text("Desc", desc, box, font_size=13.0,
                         color=TOKENS["colors"]["ink_secondary"])
        self.build_button("Btn_Action", action_label, box,
                          variant="primary", size="md")
        return box

    def build_error_inline(
        self,
        name: str,
        message: str,
        fix: str,
        parent_id: int,
    ) -> int:
        """Inline error: danger badge + cause + way out + [Try again]."""
        row = self.create_frame(name, parent_id, 420.0, 96.0,
                                fill=TOKENS["colors"]["danger_subtle"],
                                stroke=None, corner_radius=8.0,
                                layout_mode="horizontal", gap=12.0,
                                padding=(12.0, 16.0, 12.0, 16.0),
                                cross_align="center",
                                sizing_h="fixed", sizing_v="fixed")
        self.build_badge("Bdg_Err", "ERROR", row, tone="danger")
        col = self.create_frame("Col", row, 280.0, 72.0,
                                layout_mode="vertical", gap=2.0,
                                sizing_h="fill", sizing_v="hug")
        self.create_text("Msg", message, col, font_size=13.0,
                         font_weight="SemiBold",
                         color=TOKENS["colors"]["ink_primary"])
        self.create_text("Fix", fix, col, font_size=12.0,
                         color=TOKENS["colors"]["ink_secondary"])
        self.build_button("Btn_Retry", "Try again", row,
                          variant="ghost", size="sm")
        return row

    def build_ledger_row(
        self,
        name: str,
        c_num: str,
        c_page: str,
        c_src: str,
        c_dst: str,
        c_fit: str,
        c_check: str,
        parent_id: int,
        state: str = "plain",  # "plain" | "cursor" | "selected"
    ) -> int:
        """Ledger table row: 6 columns + 1px separator + state."""
        fill = TOKENS["colors"]["surface_card"]
        if state == "cursor":
            fill = TOKENS["colors"]["surface_active"]
        elif state == "selected":
            fill = TOKENS["colors"]["selected"]
        row = self.create_frame(name, parent_id, 640.0, 42.0, fill=fill,
                                stroke=TOKENS["colors"]["border"],
                                corner_radius=0.0, layout_mode="horizontal",
                                gap=8.0, padding=(6.0, 12.0, 6.0, 12.0),
                                cross_align="center",
                                sizing_h="fixed", sizing_v="fixed")
        for cname, txt, w in (("C_Num", c_num, 36.0), ("C_Page", c_page, 60.0),
                              ("C_Src", c_src, 170.0), ("C_Dst", c_dst, 170.0),
                              ("C_Fit", c_fit, 80.0), ("C_Chk", c_check, 60.0)):
            self.create_text(cname, txt, row, font_size=11.0,
                             font_family=TOKENS["typography"]["font_mono"],
                             color=TOKENS["colors"]["ink_secondary"],
                             width=w, max_w=w)
        return row

    def create_rect(
        self,
        name: str,
        parent_id: int,
        width: float,
        height: float,
        fill: Optional[str] = None,
        stroke: Optional[str] = None,
        stroke_width: float = 1.0,
        corner_radius: float = 0.0,
        x: float = 0.0,
        y: float = 0.0,
        sizing_h: str = "fixed",
        sizing_v: str = "fixed"
    ) -> int:
        nid = self.alloc_id()
        rect_node = {
            "id": nid,
            "name": name,
            "type": "rectangle",
            "parent": parent_id,
            "transform": [1.0, 0.0, 0.0, 1.0, float(x), float(y)],
            "width": float(width),
            "height": float(height),
            "fills": make_solid_fill(fill) if fill else [],
            "strokes": make_solid_stroke(stroke) if stroke else [],
            "stroke_weight": float(stroke_width) if stroke else 0.0,
            "child_layout": {
                "sizing_h": sizing_h,
                "sizing_v": sizing_v,
                "absolute": False,
                "min_w": None, "max_w": None,
                "min_h": None, "max_h": None,
                "grid_column": None, "grid_row": None,
                "grid_column_span": 0, "grid_row_span": 0
            }
        }
        if corner_radius > 0:
            rect_node["corners"] = {
                "radii": [corner_radius, corner_radius, corner_radius, corner_radius],
                "smoothing": 0.0
            }
        return self.add_node(rect_node, parent_id)

    def create_ellipse(
        self,
        name: str,
        parent_id: int,
        size: float,
        fill: str,
        x: float = 0.0,
        y: float = 0.0
    ) -> int:
        nid = self.alloc_id()
        ellipse_node = {
            "id": nid,
            "name": name,
            "type": "ellipse",
            "parent": parent_id,
            "start": 0.0,
            "sweep": 6.2831853,
            "inner": 0.0,
            "transform": [1.0, 0.0, 0.0, 1.0, float(x), float(y)],
            "width": float(size),
            "height": float(size),
            "fills": make_solid_fill(fill),
            "child_layout": {
                "sizing_h": "fixed",
                "sizing_v": "fixed",
                "absolute": False,
                "min_w": None, "max_w": None,
                "min_h": None, "max_h": None,
                "grid_column": None, "grid_row": None,
                "grid_column_span": 0, "grid_row_span": 0
            }
        }
        return self.add_node(ellipse_node, parent_id)

    # -----------------------------------------------------------------------
    # HIGH-LEVEL COMPONENT FACTORY
    # -----------------------------------------------------------------------

    def build_button(
        self,
        name: str,
        label: str,
        parent_id: int,
        variant: str = "default",  # "primary" | "default" | "ghost" | "danger"
        size: str = "md",          # "sm" (28px) | "md" (32px) | "lg" (40px)
        icon_name: Optional[str] = None
    ) -> int:
        """Create a consistent button with auto-layout matching DESIGN.md."""
        height = TOKENS["sizes"]["btn_md"]
        font_size = 12.0
        pad_x = 14.0
        pad_y = 6.0
        if size == "sm":
            height = TOKENS["sizes"]["btn_sm"]
            font_size = 11.0
            pad_x = 10.0
            pad_y = 4.0
        elif size == "lg":
            height = TOKENS["sizes"]["btn_lg"]
            font_size = 14.0
            pad_x = 18.0
            pad_y = 10.0

        if variant == "primary":
            bg = TOKENS["colors"]["action-primary"]
            stroke = None
            text_color = TOKENS["colors"]["action-primary-fg"]  # primary foreground on the primary surface
            font_weight = "SemiBold"
        elif variant == "danger":
            bg = TOKENS["colors"]["danger"]
            stroke = None
            text_color = CONTENT["sheet"]
            font_weight = "SemiBold"
        elif variant == "ghost":
            bg = None
            stroke = None
            text_color = TOKENS["colors"]["ink_secondary"]
            font_weight = "Medium"
        else: # default
            bg = TOKENS["colors"]["surface_2"]
            stroke = TOKENS["colors"]["border"]
            text_color = TOKENS["colors"]["ink_primary"]
            font_weight = "Medium"

        # R2: measure the label FIRST so the stored frame is honest (headless
        # does not reflow; a fixed width=100 used to overflow icon+label by 22px).
        label_w = estimate_text_width(label, font_size, TOKENS["typography"]["font_ui"])
        icon_dim = 0.0
        if icon_name:
            # DESIGN.md: icon sm/md/lg = 16/20/24, follows the button size tier.
            icon_dim = TOKENS["sizes"]["icon_md"]
            if size == "sm":
                icon_dim = TOKENS["sizes"]["icon_sm"]
            elif size == "lg":
                icon_dim = TOKENS["sizes"]["icon_lg"]
        frame_w = max(100.0, pad_x * 2 + label_w + (icon_dim + 6.0 if icon_dim else 0.0))

        btn_id = self.create_frame(
            name=name,
            parent_id=parent_id,
            width=frame_w,
            height=height,
            fill=bg,
            stroke=stroke,
            corner_radius=TOKENS["radii"]["control"],
            layout_mode="horizontal",
            gap=6.0,
            padding=(pad_y, pad_x, pad_y, pad_x),
            main_align="center",
            cross_align="center",
            sizing_h="hug",
            sizing_v="fixed"
        )

        if icon_name:
            paths = ICON_PATHS.get(icon_name)
            if paths is None:
                print(f"figcraft_tool: unknown icon '{icon_name}' — empty slot.",
                      file=sys.stderr)
            else:
                self.create_vector(
                    name=f"icon/{icon_name}",
                    path_data=paths,
                    parent_id=btn_id,
                    width=icon_dim,
                    height=icon_dim,
                    stroke=text_color,
                    stroke_width=1.5
                )

        self.create_text(
            name="label",
            text=label,
            parent_id=btn_id,
            font_size=font_size,
            font_weight=font_weight,
            font_family=TOKENS["typography"]["font_ui"],
            color=text_color
        )
        return btn_id

    # Legacy tone names stay as aliases; canonical semantic role names win.
    BADGE_TONES = {
        "data-technical": ("data-technical-soft", "data-technical"),
        "cyan": ("data-technical-soft", "data-technical"),
        "action-primary": ("action-primary-soft", "action-primary"),
        "coral": ("action-primary-soft", "action-primary"),
        "status-success": ("status-success-soft", "status-success"),
        "ok": ("status-success-soft", "status-success"),
        "status-warn": ("status-warn-soft", "status-warn"),
        "warn": ("status-warn-soft", "status-warn"),
        "status-danger": ("status-danger-soft", "status-danger"),
        "danger": ("status-danger-soft", "status-danger"),
        "status-info": ("status-info-soft", "status-info"),
        "info": ("status-info-soft", "status-info"),
        "muted": ("surface-2", "text-2"),
    }

    def build_badge(
        self,
        name: str,
        text: str,
        parent_id: int,
        tone: str = "data-technical",
    ) -> int:
        """Create a borderless semantic badge using manifest token roles."""
        bg_role, fg_role = self.BADGE_TONES.get(
            tone, self.BADGE_TONES["muted"]
        )
        badge_id = self.create_frame(
            name=name,
            parent_id=parent_id,
            width=float(COMPONENT.get("badge", {}).get("height", 20)) * 2.5,
            height=float(COMPONENT.get("badge", {}).get("height", 20)),
            fill=TOKENS["colors"][bg_role],
            stroke=None,
            corner_radius=TOKENS["radii"]["badge"],
            layout_mode="horizontal",
            gap=SPACE["xs"] / 2.0,
            # Keep vertical padding at zero: the badge height is the visual
            # component height, and inner padding would clip the label.
            padding=(0.0, SPACE["sm"], 0.0, SPACE["sm"]),
            main_align="center",
            cross_align="center",
            sizing_h="hug",
            sizing_v="fixed",
        )
        self.create_text(
            name="text",
            text=text,
            parent_id=badge_id,
            font_size=float(COMPONENT.get("badge", {}).get("fontSize",
                                                           TOKENS["typography"]["sizes"]["badge"])),
            font_weight="SemiBold",
            font_family=TOKENS["typography"]["font_mono"],
            color=TOKENS["colors"][fg_role],
        )
        return badge_id

    def build_window_bar(self, parent_id: int, title: str = DESIGN_DOC["name"]) -> int:
        """Build macOS-style top window header."""
        bar_id = self.create_frame(
            name="WindowBar",
            parent_id=parent_id,
            width=1280.0,
            height=TOKENS["sizes"]["window_bar"],
            fill=TOKENS["colors"]["surface_2"],
            stroke=TOKENS["colors"]["border_subtle"],
            layout_mode="horizontal",
            gap=12.0,
            padding=(0.0, 16.0, 0.0, 16.0),
            main_align="spaceBetween",
            cross_align="center",
            sizing_h="fill",
            sizing_v="fixed"
        )
        # Traffic lights
        traffic_id = self.create_frame(
            name="TrafficLights",
            parent_id=bar_id,
            width=52.0,
            height=12.0,
            layout_mode="horizontal",
            gap=8.0,
            sizing_h="hug",
            sizing_v="fixed"
        )
        self.create_ellipse("close", traffic_id, 12.0, CONTENT["traffic_close"])
        self.create_ellipse("minimize", traffic_id, 12.0, CONTENT["traffic_min"])
        self.create_ellipse("maximize", traffic_id, 12.0, CONTENT["traffic_max"])

        # Centered title
        self.create_text(
            name="AppTitle",
            text=title,
            parent_id=bar_id,
            font_size=11.0,
            font_weight="SemiBold",
            font_family=TOKENS["typography"]["font_ui"],
            color=TOKENS["colors"]["ink_secondary"]
        )

        # Right status indicator
        status_id = self.create_frame(
            name="StatusRight",
            parent_id=bar_id,
            width=60.0,
            height=16.0,
            layout_mode="horizontal",
            gap=6.0,
            cross_align="center",
            sizing_h="hug",
            sizing_v="fixed"
        )
        self.create_ellipse("dot_green", status_id, 6.0, TOKENS["colors"]["success"])
        self.create_text("status_text", "Ready", status_id, font_size=10.0, color=TOKENS["colors"]["ink_muted"])

        return bar_id

    def build_pipeline_bar(self, parent_id: int, active_stage: int = 1) -> int:
        """Pipeline Bar: Import -> Detect -> Translate -> Review -> Export"""
        bar_id = self.create_frame(
            name="PipelineBar",
            parent_id=parent_id,
            width=1280.0,
            height=40.0,
            fill=TOKENS["colors"]["surface"],
            stroke=TOKENS["colors"]["border"],
            layout_mode="horizontal",
            gap=12.0,
            padding=(0.0, 20.0, 0.0, 20.0),
            main_align="min",
            cross_align="center",
            sizing_h="fill",
            sizing_v="fixed"
        )

        stages = [
            ("1. Import", "ok"),
            ("2. Detect", "active" if active_stage == 2 else ("ok" if active_stage > 2 else "pending")),
            ("3. Translate", "active" if active_stage == 3 else ("ok" if active_stage > 3 else "pending")),
            ("4. Review", "active" if active_stage == 4 else ("ok" if active_stage > 4 else "pending")),
            ("5. Export", "active" if active_stage == 5 else ("ok" if active_stage > 5 else "pending")),
        ]

        for idx, (label, state) in enumerate(stages):
            if idx > 0:
                self.create_text(f"arrow_{idx}", "→", bar_id, font_size=12.0, color=TOKENS["colors"]["ink_muted"])

            color = TOKENS["colors"]["ink_muted"]
            weight = "Regular"
            bg = None
            if state == "active":
                color = TOKENS["colors"]["action-primary"]
                weight = "Bold"
                bg = TOKENS["colors"]["action-primary-soft"]
            elif state == "ok":
                color = TOKENS["colors"]["ink_primary"]
                weight = "Medium"

            stage_frame = self.create_frame(
                name=f"Stage_{idx+1}",
                parent_id=bar_id,
                width=80.0,
                height=26.0,
                fill=bg,
                corner_radius=4.0,
                layout_mode="horizontal",
                padding=(4.0, 8.0, 4.0, 8.0),
                main_align="center",
                cross_align="center",
                sizing_h="hug",
                sizing_v="fixed"
            )
            self.create_text("label", label, stage_frame, font_size=11.0, font_weight=weight, color=color)

        return bar_id


# ---------------------------------------------------------------------------
# FIGCRAFT CLIENT (LIVE CONTROL SERVER OVER TCP)
# ---------------------------------------------------------------------------
class FigcraftClient:
    """Communicates with running FigCraft app via `--control <port>` TCP JSON-RPC."""

    def __init__(self, port: int = 9880, host: str = "127.0.0.1"):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self._req_id = 0

    def connect(self, timeout: float = 2.0) -> bool:
        """Connect to FigCraft control port."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(timeout)
            self.sock.connect((self.host, self.port))
            return True
        except Exception:
            self.sock = None
            return False

    def is_connected(self) -> bool:
        return self.sock is not None

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def send_command(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a JSON command and return decoded result."""
        if not self.sock:
            raise ConnectionError("Not connected to FigCraft control server.")
        
        self._req_id += 1
        payload = {"id": self._req_id, "method": method}
        if params is not None:
            payload["params"] = params

        req_bytes = json.dumps(payload).encode("utf-8") + b"\n"
        self.sock.sendall(req_bytes)

        # Read JSON response line: socket timeout (set in connect) + hard
        # chunk cap so a chatty/misbehaving server cannot loop forever.
        buf = b""
        for _ in range(1024):  # cut-loop guard
            chunk = self.sock.recv(16384)
            if not chunk:
                break
            buf += chunk
            if b"\n" in buf:
                break

        if not buf:
            raise EOFError("Connection closed by FigCraft control server.")

        return json.loads(buf.decode("utf-8"))

    # High-level RPC methods
    def document_inspect(self) -> Dict[str, Any]:
        return self.send_command("document.inspect")

    def node_get(self, node_id: int) -> Dict[str, Any]:
        return self.send_command("node.get", {"id": node_id})

    def engine_execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.send_command("engine.execute", {"command": command, "params": params or {}})

    def engine_commands(self) -> List[Dict[str, Any]]:
        res = self.send_command("engine.commands")
        return res.get("result", [])

    def export_frame(self, node_id: int, out_path: str, format: str = "png", scale: float = 1.0) -> Dict[str, Any]:
        return self.engine_execute("file.export", {
            "ids": [node_id],
            "format": format,
            "scale": scale,
            "path": os.path.abspath(out_path)
        })

    def save_file(self, path: Optional[str] = None) -> Dict[str, Any]:
        p = {"path": os.path.abspath(path)} if path else {}
        return self.engine_execute("file.save", p)


# ---------------------------------------------------------------------------
# SCREEN BUILDERS (TEMPLATES MATCHING DESIGN.MD)
# ---------------------------------------------------------------------------
def build_workbench_screen(doc: FigcraftDocument, x: float = 40.0, y: float = 40.0,
                           page_index: Optional[int] = None,
                           page_name: Optional[str] = None) -> int:
    """Build the complete Kuron Studio Desktop Workbench on the selected page."""
    # Main outer frame (Desktop 1280x960)
    screen_id = doc.create_frame(
        name="1. Workbench",
        parent_id=doc.resolve_page(page_index, page_name),
        width=1280.0,
        height=960.0,
        x=x,
        y=y,
        fill=TOKENS["colors"]["surface"],
        corner_radius=TOKENS["radii"]["window"],
        layout_mode="vertical",
        gap=0.0,
        clip=True
    )

    # 1. Window Bar
    doc.build_window_bar(screen_id, title="Kuron Studio — ONIMASA Ch.12 (P.04)")

    # 2. Pipeline Bar
    doc.build_pipeline_bar(screen_id, active_stage=3)

    # 3. Main Workspace Area (3 Columns: Rail 196px | Canvas 1fr | Inspector 268px)
    body_id = doc.create_frame(
        name="WorkbenchBody",
        parent_id=screen_id,
        width=1280.0,
        height=888.0,
        layout_mode="horizontal",
        gap=0.0,
        sizing_h="fill",
        sizing_v="fill"
    )

    # LEFT RAIL (196px): Page List & Navigator
    left_rail = doc.create_frame(
        name="LeftRail",
        parent_id=body_id,
        width=196.0,
        height=888.0,
        fill=TOKENS["colors"]["surface_2"],
        stroke=TOKENS["colors"]["border"],
        layout_mode="vertical",
        gap=8.0,
        padding=(12.0, 12.0, 12.0, 12.0),
        sizing_h="fixed",
        sizing_v="fill"
    )
    doc.create_text("PagesHeader", "PAGES (41)", left_rail, font_size=11.0, font_weight="Bold", color=TOKENS["colors"]["ink_muted"])
    
    # Page thumbnails list in Left Rail
    for i in range(1, 6):
        is_active = (i == 4)
        page_card = doc.create_frame(
            name=f"PageItem_{i}",
            parent_id=left_rail,
            width=172.0,
            height=48.0,
            fill=TOKENS["colors"]["surface_active"] if is_active else TOKENS["colors"]["surface_card"],
            stroke=TOKENS["colors"]["action-primary"] if is_active else TOKENS["colors"]["border"],
            corner_radius=TOKENS["radii"]["control"],
            layout_mode="horizontal",
            gap=8.0,
            padding=(6.0, 8.0, 6.0, 8.0),
            cross_align="center",
            sizing_h="fill",
            sizing_v="fixed"
        )
        doc.create_rect("Thumb", page_card, 32.0, 36.0, fill=TOKENS["colors"]["surface_active"], corner_radius=3.0)
        col_text = doc.create_frame(f"Meta_{i}", page_card, width=100.0, height=36.0, layout_mode="vertical", gap=2.0, sizing_h="fill", sizing_v="hug")
        doc.create_text("Title", f"Page {i:02d}", col_text, font_size=11.0, font_weight="SemiBold", color=TOKENS["colors"]["ink_primary"])
        doc.create_text("BubbleCount", f"{12 - i*2} bubbles", col_text, font_size=10.0, font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["data-technical"])

    # CENTER CANVAS (1fr): Dark Manga Preview with Coral Bubble Outlines
    center_canvas = doc.create_frame(
        name="CenterCanvas",
        parent_id=body_id,
        width=816.0,
        height=888.0,
        fill=TOKENS["colors"]["bg_app"],
        layout_mode="vertical",
        gap=16.0,
        padding=(24.0, 24.0, 24.0, 24.0),
        main_align="center",
        cross_align="center",
        sizing_h="fill",
        sizing_v="fill"
    )
    
    # Manga Page Mockup
    manga_page = doc.create_frame(
        name="MangaPage_P04",
        parent_id=center_canvas,
        width=520.0,
        height=740.0,
        fill=CONTENT["paper"],
        stroke=CONTENT["window_outline"],
        stroke_width=2.0,
        corner_radius=4.0,
        clip=True
    )
    
    # Manga comic panels inside page
    doc.create_rect("PanelTop", manga_page, 480.0, 220.0, fill=CONTENT["paper_alt"], stroke=CONTENT["ink_panel"], stroke_width=2.0, x=20.0, y=20.0)
    doc.create_rect("PanelMidLeft", manga_page, 230.0, 240.0, fill=CONTENT["paper_2"], stroke=CONTENT["ink_panel"], stroke_width=2.0, x=20.0, y=250.0)
    doc.create_rect("PanelMidRight", manga_page, 240.0, 240.0, fill=CONTENT["paper_3"], stroke=CONTENT["ink_panel"], stroke_width=2.0, x=260.0, y=250.0)
    doc.create_rect("PanelBottom", manga_page, 480.0, 210.0, fill=CONTENT["paper_4"], stroke=CONTENT["ink_panel"], stroke_width=2.0, x=20.0, y=500.0)

    # Active Detected Speech Bubbles (Highlighted in Coral)
    bubble1 = doc.create_frame("Bubble_01", manga_page, 140.0, 90.0, x=50.0, y=60.0, fill=CONTENT["sheet"], stroke=TOKENS["colors"]["action-primary"], stroke_width=2.0, corner_radius=20.0)
    doc.create_text("Txt1", "What?! Is it really them…", bubble1, font_size=11.0, font_weight="Bold", color=CONTENT["ink_soft"], x=12.0, y=14.0, width=116.0, height=60.0)
    
    bubble2 = doc.create_frame("Bubble_02", manga_page, 130.0, 80.0, x=330.0, y=270.0, fill=CONTENT["sheet"], stroke=TOKENS["colors"]["action-primary"], stroke_width=2.0, corner_radius=18.0)
    doc.create_text("Txt2", "嘘じゃない。この目で見た。", bubble2, font_size=11.0, font_weight="Bold", color=CONTENT["ink_soft"], x=12.0, y=14.0, width=106.0, height=52.0)

    # RIGHT INSPECTOR (268px): Translation cards & Fit bar
    right_inspector = doc.create_frame(
        name="RightInspector",
        parent_id=body_id,
        width=268.0,
        height=888.0,
        fill=TOKENS["colors"]["surface_2"],
        stroke=TOKENS["colors"]["border"],
        layout_mode="vertical",
        gap=12.0,
        padding=(16.0, 16.0, 16.0, 16.0),
        sizing_h="fixed",
        sizing_v="fill"
    )
    doc.create_text("InspectorTitle", "BUBBLE INSPECTOR #01", right_inspector, font_size=11.0, font_weight="Bold", font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["data-technical"])

    # Original Japanese Card
    card_orig = doc.create_frame("CardOriginal", right_inspector, 236.0, 90.0, fill=TOKENS["colors"]["surface_card"], stroke=TOKENS["colors"]["border"], corner_radius=TOKENS["radii"]["control"], layout_mode="vertical", gap=6.0, padding=(10.0, 12.0, 10.0, 12.0), sizing_h="fill", sizing_v="hug")
    doc.create_text("LblOrig", "ASLI (JA)", card_orig, font_size=10.0, font_weight="Bold", color=TOKENS["colors"]["ink_muted"])
    doc.create_text("ValOrig", "What?! Is it really them…", card_orig, font_size=12.0, color=TOKENS["colors"]["ink_primary"])

    # Indonesian Translation Card
    card_trans = doc.create_frame("CardTrans", right_inspector, 236.0, 120.0, fill=TOKENS["colors"]["surface_card"], stroke=TOKENS["colors"]["action-primary"], stroke_width=1.5, corner_radius=TOKENS["radii"]["control"], layout_mode="vertical", gap=6.0, padding=(10.0, 12.0, 10.0, 12.0), sizing_h="fill", sizing_v="hug")
    doc.create_text("LblTrans", "TRANSLATION (EN)", card_trans, font_size=10.0, font_weight="Bold", color=TOKENS["colors"]["action-primary"])
    doc.create_text("ValTrans", "What?! Is it really them…", card_trans, font_size=13.0, font_weight="SemiBold", color=TOKENS["colors"]["ink_primary"])
    doc.create_text("FitBar", "Fit: 94%  •  2 lines  •  Font: 14pt", card_trans, font_size=10.0, font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["success"])

    # Actions footer inside inspector
    doc.build_button("BtnApply", "Apply translation", right_inspector, variant="primary", size="md")
    doc.build_button("BtnInpaint", "Clean bubble (inpaint)", right_inspector, variant="default", size="md")

    return screen_id

def build_tokens_screen(doc: FigcraftDocument, x: float = 1360.0, y: float = 40.0,
                        page_index: Optional[int] = None,
                        page_name: Optional[str] = None) -> int:
    """Build the Design Tokens style guide on the selected page."""
    frame_id = doc.create_frame(
        name="03. Design Tokens & Patterns",
        parent_id=doc.resolve_page(page_index, page_name),
        width=1280.0,
        height=960.0,
        x=x,
        y=y,
        fill=TOKENS["colors"]["surface"],
        corner_radius=TOKENS["radii"]["window"],
        layout_mode="vertical",
        gap=20.0,
        padding=(32.0, 40.0, 32.0, 40.0),
        clip=True
    )
    
    # Header
    doc.create_text("TokenHeader", "KURON STUDIO — DESIGN TOKENS & SYSTEM", frame_id, font_size=20.0, font_weight="Bold", color=TOKENS["colors"]["ink_primary"])
    doc.create_text("TokenSub", "Single source of visual truth. Follow the tokens below consistently.", frame_id, font_size=13.0, color=TOKENS["colors"]["ink_secondary"])

    # Colors Section Grid
    doc.create_text("ColorSecTitle", "01 / COLOUR PALETTE", frame_id, font_size=13.0, font_weight="Bold", color=TOKENS["colors"]["action-primary"])
    color_row = doc.create_frame("ColorRow", frame_id, 1200.0, 90.0, layout_mode="horizontal", gap=16.0, sizing_h="fill", sizing_v="hug")
    
    swatches = [
        ("Primary action", TOKENS["colors"]["action-primary"]),
        ("Technical info", TOKENS["colors"]["data-technical"]),
        ("Surface (background)", TOKENS["colors"]["surface"]),
        ("Surface 2 (Panel)", TOKENS["colors"]["surface_2"]),
        ("Card (elevation)", TOKENS["colors"]["surface_card"]),
        ("Border (line)", TOKENS["colors"]["border"]),
        ("Success", TOKENS["colors"]["success"]),
        ("Danger (error)", TOKENS["colors"]["danger"]),
    ]
    for name, hex_code in swatches:
        sw = doc.create_frame(f"Sw_{name}", color_row, 130.0, 80.0, fill=TOKENS["colors"]["surface_card"], stroke=TOKENS["colors"]["border"], corner_radius=6.0, layout_mode="vertical", gap=6.0, padding=(8.0, 8.0, 8.0, 8.0), sizing_h="fixed", sizing_v="fixed")
        doc.create_rect("ColorBox", sw, 114.0, 32.0, fill=hex_code, corner_radius=4.0)
        doc.create_text("CName", name, sw, font_size=10.0, font_weight="Medium", color=TOKENS["colors"]["ink_primary"])
        doc.create_text("CHex", hex_code, sw, font_size=9.0, font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["ink_muted"])

    # Components Preview Row
    doc.create_text("CompSecTitle", "02 / PRIMITIVE COMPONENTS", frame_id, font_size=13.0, font_weight="Bold", color=TOKENS["colors"]["data-technical"])
    comp_row = doc.create_frame("CompRow", frame_id, 1200.0, 80.0, fill=TOKENS["colors"]["surface_2"], stroke=TOKENS["colors"]["border"], corner_radius=8.0, layout_mode="horizontal", gap=20.0, padding=(16.0, 20.0, 16.0, 20.0), cross_align="center", sizing_h="fill", sizing_v="hug")
    
    doc.build_button("BtnPri", "Primary action", comp_row, variant="primary", size="md")
    doc.build_button("BtnDef", "Default button", comp_row, variant="default", size="md")
    doc.build_button("BtnDgr", "Delete", comp_row, variant="danger", size="md")
    doc.build_badge("BdgCyan", "12 BUBBLES", comp_row, tone="cyan")
    doc.build_badge("BdgCoral", "CH.12 ACTIVE", comp_row, tone="coral")
    doc.build_badge("BdgOk", "VERIFIED", comp_row, tone="ok")

    # Typography Scale
    doc.create_text("TypeSecTitle", "03 / TATA TIPOGRAFI", frame_id, font_size=13.0, font_weight="Bold", color=TOKENS["colors"]["ink_primary"])
    type_box = doc.create_frame("TypeBox", frame_id, 1200.0, 180.0, fill=TOKENS["colors"]["surface_2"], stroke=TOKENS["colors"]["border"], corner_radius=8.0, layout_mode="vertical", gap=12.0, padding=(16.0, 24.0, 16.0, 24.0), sizing_h="fill", sizing_v="hug")
    doc.create_text("T1", "Space Grotesk Bold 20pt — Heading and project identity", type_box, font_size=20.0, font_weight="Bold", font_family="Space Grotesk", color=TOKENS["colors"]["ink_primary"])
    doc.create_text("T2", "Inter Medium 13pt — UI labels, buttons, and instruction text", type_box, font_size=13.0, font_weight="Medium", font_family="Inter", color=TOKENS["colors"]["ink_secondary"])
    doc.create_text("T3", "JetBrains Mono Regular 11pt — tabular numbers, coordinates [x: 420, y: 180, w: 90], status 94%", type_box, font_size=11.0, font_family="JetBrains Mono", color=TOKENS["colors"]["data-technical"])

    return frame_id


# ---------------------------------------------------------------------------
# QUIET-WORKBENCH LINTER (murni: tanpa I/O, warn-only)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# LINTER CONFIG — loaded from DESIGN.md, never frozen in code
# ---------------------------------------------------------------------------
# Content colours (manga paper, print ink, system traffic lights, scrims) are
# legitimate artwork values, not UI tokens. Their allowlists come from the
# manifest's optional `lint` section so a project can extend them in one place.
_CONTENT_ALLOWLIST = frozenset(
    str(value).lower() for value in LINT_CONFIG.get("contentAllow", [])
)
_BORDER_CONTENT_ALLOW = frozenset(
    str(value).lower() for value in LINT_CONFIG.get("borderContentAllow", [])
)
_FORBIDDEN_NEON = str(LINT_CONFIG.get("forbiddenNeon", "")).lower()
_BORDER_ALLOWED_ROLES = frozenset(LINT_CONFIG.get("borderAllowedRoles", [
    "line", "line-strong", "ring", "action-primary",
]))

# Reverse lookup used by the design-to-code converter. It is derived from the
# manifest for both themes, so no hex-to-role table is frozen in this file.
CSS_ROLE_NAMES = {
    "action-primary": "accent", "action-primary-hover": "accent-hover",
    "action-primary-fg": "accent-fg", "action-primary-soft": "accent-soft",
    "data-technical": "technical", "data-technical-soft": "technical-soft",
    "raised": "surface-card", "surface-2": "surface-2",
    "text": "ink", "text-2": "ink-2", "text-3": "ink-3",
    "status-success": "success", "status-warn": "warn",
    "status-danger": "danger", "status-info": "info",
}


def _role_hex_map() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for theme in ("light", "dark"):
        for role, value in get_tokens(theme)["colors"].items():
            if isinstance(value, str) and value.startswith("#"):
                mapping[value.lower()] = CSS_ROLE_NAMES.get(role, role)
    return mapping


_ROLE_HEX_MAP = _role_hex_map()



def _lint_hex(color: Dict[str, Any]) -> str:
    """Convert a FigCraft float RGBA dict to hex `#rrggbb` (ignore alpha)."""
    r = int(round(color.get("r", 0) * 255))
    g = int(round(color.get("g", 0) * 255))
    b = int(round(color.get("b", 0) * 255))
    return f"#{r:02x}{g:02x}{b:02x}"


def _lint_paint_hexes(node: Dict[str, Any]) -> List[str]:
    """Collect all visible fill and stroke hex values on one node."""
    hexes: List[str] = []
    for key in ("fills", "strokes"):
        for paint in node.get(key, []) or []:
            if not paint.get("visible", True):
                continue
            color = paint.get("color")
            if isinstance(color, dict):
                hexes.append(_lint_hex(color))
    return hexes


def lint_design(doc: "FigcraftDocument") -> List[str]:
    """Validate a document with pure, I/O-free, warn-only quiet-workbench rules.

    Accepts a ``FigcraftDocument`` or a raw ``json.loads(document.json)`` dict.
    Colours are compared against semantic roles resolved from DESIGN.md, never
    against frozen literals in this file. Rules S-01/S-02/S-09 refer to the
    ``action-primary`` and ``data-technical`` roles; S-08/S-10 detect overflow
    and S-11 detects screen frames with clipping disabled.
    """
    warnings: List[str] = []
    raw = doc.doc if hasattr(doc, "doc") else doc
    nodes: Dict[str, Any] = raw.get("nodes", {})
    light = get_tokens("light")["colors"]
    dark = TOKENS["colors"]
    known = {str(v).lower() for v in list(dark.values()) + list(light.values())}
    action = str(dark["action-primary"]).lower()
    action_fg = str(dark["action-primary-fg"]).lower()
    technical = str(dark["data-technical"]).lower()
    border_roles = {
        str(role_value).lower()
        for role in _BORDER_ALLOWED_ROLES
        for role_value in (dark.get(role), light.get(role))
        if role_value
    }

    def label(nid: Any, node: Dict[str, Any]) -> str:
        return f"[{nid}] {node.get('name', '?')}"

    # Per-node checks: forbidden neon, bordered badges, S-01 borders, unknown
    # colours, S-02 technical-colour misuse, S-08 horizontal overflow.
    for nid, node in nodes.items():
        if not isinstance(node, dict) or node.get("type") not in (
            "frame", "rectangle", "ellipse", "text",
        ):
            continue
        hexes = _lint_paint_hexes(node)
        lname = str(node.get("name", "")).lower()

        if _FORBIDDEN_NEON and _FORBIDDEN_NEON in hexes:
            warnings.append(
                f"{label(nid, node)}: fill/stroke {_FORBIDDEN_NEON} is forbidden — "
                f"use the data-technical role ({technical})."
            )

        corners = node.get("corners", {}).get("radii", [0]) if isinstance(node.get("corners"), dict) else [0]
        is_pill_shape = (corners or [0])[0] >= 9000
        looks_like_badge = (
            "badge" in lname or "chip" in lname or "pill" in lname
            or lname.startswith("bdg") or is_pill_shape
        )
        if looks_like_badge and node.get("strokes"):
            warnings.append(
                f"{label(nid, node)}: badge/chip uses a border — the quiet "
                "workbench uses borderless soft surfaces instead."
            )

        # S-01: structural borders are neutral hairlines. A coloured stroke
        # on a frame/rectangle is border hijacking, even if the node name
        # does not look like a component.
        if node.get("type") in ("frame", "rectangle") and node.get("strokes"):
            for paint in node.get("strokes", []) or []:
                color = paint.get("color")
                if isinstance(color, dict) and paint.get("visible", True):
                    border_hex = _lint_hex(color)
                    if border_hex and border_hex not in border_roles | _BORDER_CONTENT_ALLOW:
                        warnings.append(
                            f"{label(nid, node)}: border {border_hex} is outside "
                            "the neutral line / line-strong roles — map it in DESIGN.md."
                        )
                        break

        unknown = sorted({h for h in hexes if h not in known and h not in _CONTENT_ALLOWLIST})
        if unknown:
            warnings.append(
                f"{label(nid, node)}: colour outside the token table: "
                f"{', '.join(unknown)}."
            )

        if node.get("type") == "text":
            style = node.get("style", {}) or {}
            chars = str(node.get("characters", "") or "")
            if hexes and hexes[0] == technical:
                # S-02: the data-technical role is for short technical data
                # only. Monospace alone is not sufficient — a long heading
                # styled as mono must still be flagged.
                stripped = chars.strip()
                is_mono = style.get("font_family") == TOKENS["typography"]["font_mono"]
                is_tech_pattern = bool(
                    re.fullmatch(r"\[[^\]]*\]", stripped)
                    or re.fullmatch(r"#\d+", stripped)
                    or re.fullmatch(r"\d+\s*/\s*\d+", stripped)
                )
                is_short_code = len(stripped) <= 24 and not re.search(r"[a-z]", chars)
                if not (is_mono and (is_tech_pattern or is_short_code)):
                    warnings.append(
                        f"{label(nid, node)}: data-technical colour is used for "
                        "non-technical text — reserve it for short mono "
                        "coordinates, IDs, ratios, and counters."
                    )
            # S-08: text wider than the parent's inner width overflows.
            parent = nodes.get(str(node.get("parent", ""))) or {}
            parent_width = parent.get("width") or 0
            padding = (parent.get("layout") or {}).get("padding", [0, 0, 0, 0]) or [0, 0, 0, 0]
            try:
                inner = float(parent_width) - float(padding[1]) - float(padding[3])
            except (IndexError, TypeError, ValueError):
                inner = float(parent_width)
            if parent_width and node.get("width", 0) > inner + 1:
                warnings.append(
                    f"{label(nid, node)}: text {node.get('width', 0):.0f}px "
                    f"overflows the parent inner width {inner:.0f}px — reduce "
                    "max_w or widen the card."
                )

    # S-01 role counts: the action-primary role has three distinct meanings.
    # A fill on a shape is the single primary action surface; a fill on text
    # is an accent; a stroke is an active-selection ring.
    progress_exempt = ("progressfill", "progressbar")

    def action_roles(nids: List[Any]) -> tuple:
        surfaces, texts, rings = [], [], []
        for nid in nids:
            node = nodes.get(str(nid), {})
            if not isinstance(node, dict):
                continue
            if str(node.get("name", "")).lower().replace("_", "") in progress_exempt:
                continue
            bucket = texts if node.get("type") == "text" else surfaces
            for paint in node.get("fills", []) or []:
                color = paint.get("color")
                if isinstance(color, dict) and paint.get("visible", True):
                    if _lint_hex(color) == action:
                        bucket.append(label(nid, node))
            for paint in node.get("strokes", []) or []:
                color = paint.get("color")
                if isinstance(color, dict) and paint.get("visible", True):
                    if _lint_hex(color) == action:
                        rings.append(label(nid, node))
        return surfaces, texts, rings

    def subtree(nid: Any) -> List[Any]:
        # Cut-loop guard: visited set plus a hard ceiling on visited nodes.
        out, stack, seen = [], [nid], set()
        while stack and len(seen) < 100000:
            cur = str(stack.pop())
            if cur in seen:
                continue
            seen.add(cur)
            out.append(cur)
            node = nodes.get(cur, {})
            if isinstance(node, dict):
                stack.extend(node.get("children", []) or [])
        return out

    for pid in raw.get("pages", []):
        page = nodes.get(str(pid), {})
        if not isinstance(page, dict):
            continue
        for screen_id in page.get("children", []) or []:
            screen = nodes.get(str(screen_id), {})
            if not isinstance(screen, dict):
                continue
            screen_name = screen.get("name", screen_id)
            # Documentation canvases (component libraries, token guides) are
            # exempt from the one-primary-action rule per SKILL §5.
            is_docs_canvas = any(
                word in str(screen_name).lower()
                for word in ("component", "token", "guide", "palette")
            )
            surfaces, texts, rings = action_roles(subtree(screen_id))
            if len(surfaces) > 1 and not is_docs_canvas:
                warnings.append(
                    f"Screen '{screen_name}': {len(surfaces)} action-primary "
                    f"surfaces ({', '.join(surfaces)}) — only one primary "
                    "action fill is allowed per screen."
                )
            if len(texts) > 3 and not is_docs_canvas:
                warnings.append(
                    f"Screen '{screen_name}': {len(texts)} action-primary "
                    f"text nodes ({', '.join(texts)}) — at most three accent "
                    "text nodes (badge tone + active heading)."
                )
            if len(rings) > 4 and not is_docs_canvas:
                warnings.append(
                    f"Screen '{screen_name}': {len(rings)} action-primary "
                    f"strokes ({', '.join(rings)}) — several selection rings "
                    "are fine, but more than four suggests duplicate accents."
                )
            if (screen.get("type") == "frame" and (screen.get("width") or 0) >= 1000
                    and screen.get("clip") is False):
                warnings.append(
                    f"Screen '{screen_name}': clip is false — enable clipping "
                    "so child content cannot leak past the rounded frame."
                )

    # S-10: text must not overflow the bottom of a fixed-height parent.
    for nid, node in nodes.items():
        if not isinstance(node, dict) or node.get("type") != "text":
            continue
        parent = nodes.get(str(node.get("parent", "")), {})
        if not isinstance(parent, dict) or parent.get("type") not in (
            "frame", "rectangle", "ellipse",
        ):
            continue
        if (parent.get("child_layout", {}) or {}).get("sizing_v") == "hug":
            continue  # a hug parent grows with its content
        padding = (parent.get("layout") or {}).get("padding", [0, 0, 0, 0]) or [0, 0, 0, 0]
        try:
            limit = float(parent.get("height", 0)) - float(padding[2])
            bottom = float(node.get("transform", [0] * 6)[5]) + float(node.get("height", 0))
        except (IndexError, TypeError, ValueError):
            continue
        if bottom > limit + 1.0:
            warnings.append(
                f"{label(nid, node)}: text overflows vertically "
                f"({bottom:.0f}px > inner height {limit:.0f}px) — increase "
                "the parent height or switch it to hug."
            )

    # S-09: an icon on an action-primary surface must use action-primary-fg.
    for nid, node in nodes.items():
        if not isinstance(node, dict) or node.get("type") not in (
            "frame", "rectangle", "ellipse",
        ):
            continue
        fills = node.get("fills", []) or []
        if not any(
            isinstance(p.get("color"), dict) and _lint_hex(p["color"]) == action
            for p in fills if isinstance(p, dict)
        ):
            continue
        for sub in subtree(nid):
            vec = nodes.get(str(sub), {})
            if not isinstance(vec, dict) or vec.get("type") != "vector":
                continue
            for paint in vec.get("strokes", []) or []:
                color = paint.get("color")
                if (isinstance(color, dict) and paint.get("visible", True)
                        and _lint_hex(color) not in (action_fg, action)):
                    warnings.append(
                        f"{label(sub, vec)}: icon on an action-primary surface "
                        f"uses {_lint_hex(color)} — use action-primary-fg "
                        f"({action_fg}) to match the button label."
                    )

    return warnings


def component_first(doc: "FigcraftDocument", component_id: int, parent_id: int,
                    **overrides: Any) -> Optional[int]:
    """Component-first rule: reuse an existing component via duplicate/refine."""
    return doc.duplicate_node(component_id, parent_id=parent_id, overrides=overrides or None)


def ensure_board(doc: "FigcraftDocument", name: str, x: float = 0.0, y: float = 0.0,
                 width: Optional[float] = None, height: Optional[float] = None,
                 fill: Optional[str] = None, corner_radius: float = 0.0,
                 clip: bool = True, page_index: Optional[int] = None,
                 page_name: Optional[str] = None) -> int:
    """Reuse an existing board on the selected page or create it once."""
    return doc.ensure_board(name, x=x, y=y, width=width, height=height,
                            fill=fill, corner_radius=corner_radius, clip=clip,
                            page_index=page_index, page_name=page_name)


def find_or_reuse_component(
    doc: "FigcraftDocument", name: str, parent_id: Optional[int] = None,
    builder: Optional[Callable[[], int]] = None,
    page_index: Optional[int] = None, page_name: Optional[str] = None,
) -> Optional[int]:
    """Find a component across ``pages[0..N]``; build it only when absent."""
    return doc.find_or_reuse_component(name, parent_id=parent_id, builder=builder,
                                       page_index=page_index, page_name=page_name)


# ---------------------------------------------------------------------------
# DESIGN-TO-CODE CONVERTER (FIGCRAFT NODE -> SVELTE + TAILWIND)
# ---------------------------------------------------------------------------
def node_to_svelte(doc: FigcraftDocument, node_id: int, indent_level: int = 0) -> str:
    """Convert any FigCraft node hierarchy directly into Svelte + Tailwind markup."""
    nodes = doc.doc.get("nodes", {})
    node = nodes.get(str(node_id))
    if not node:
        return ""

    indent = "  " * indent_level
    ntype = node.get("type", "").lower()
    name = node.get("name", "")

    # Colour classes come from the manifest-derived role reverse map.
    def map_color(hex_str: str) -> str:
        return _ROLE_HEX_MAP.get(hex_str.lower(), f"[{hex_str}]")

    # Helper: extract hex fill
    fills = node.get("fills", [])
    bg_class = ""
    if fills and fills[0].get("visible", True):
        c = fills[0].get("color", {})
        r, g, b = int(c.get("r", 0)*255), int(c.get("g", 0)*255), int(c.get("b", 0)*255)
        hex_val = f"#{r:02x}{g:02x}{b:02x}"
        tok = map_color(hex_val)
        bg_class = f"bg-{tok}"

    # Helper: extract stroke
    strokes = node.get("strokes", [])
    border_class = ""
    if strokes and strokes[0].get("visible", True):
        border_class = "border border-border"

    # Helper: corner radius
    corners = node.get("corners", {}).get("radii", [0])[0] if "corners" in node else 0
    rounded_class = ""
    if corners >= 9000: rounded_class = "rounded-full"
    elif corners >= 16: rounded_class = "rounded-2xl"
    elif corners >= 12: rounded_class = "rounded-card"
    elif corners >= 6:  rounded_class = "rounded-md"
    elif corners >= 4:  rounded_class = "rounded"

    if ntype == "text":
        chars = node.get("characters", "")
        style = node.get("style", {})
        fsize = style.get("font_size", 13.0)
        ffam = style.get("font_family", "Inter")
        fweight = style.get("font_style", "Regular")

        # Color
        c = fills[0].get("color", {}) if fills else {}
        r, g, b = int(c.get("r", 1)*255), int(c.get("g", 1)*255), int(c.get("b", 1)*255)
        hex_val = f"#{r:02x}{g:02x}{b:02x}"
        text_color_class = "text-" + _ROLE_HEX_MAP.get(hex_val.lower(), "ink")

        classes = [f"text-[{int(fsize)}px]", text_color_class]
        if fweight in ["Bold", "SemiBold"]: classes.append("font-semibold")
        if "Space" in ffam: classes.append("font-brand")
        elif "Mono" in ffam: classes.append("font-mono tnum")

        return f'{indent}<span class="{" ".join(classes)}">{chars}</span>'

    elif ntype == "rectangle":
        w = node.get("width", 16)
        h = node.get("height", 16)
        classes = [f"w-[{int(w)}px]", f"h-[{int(h)}px]", bg_class, border_class, rounded_class]
        classes = [c for c in classes if c]
        return f'{indent}<div class="{" ".join(classes)}" />'

    elif ntype == "ellipse":
        w = node.get("width", 12)
        classes = [f"size-[{int(w)}px]", "rounded-full", bg_class]
        classes = [c for c in classes if c]
        return f'{indent}<div class="{" ".join(classes)}" />'

    elif ntype in ["frame", "page"]:
        # Layout classes
        layout = node.get("layout", {})
        mode = layout.get("mode", "none")
        gap = layout.get("gap", 0)
        pad = layout.get("padding", [0, 0, 0, 0])
        main_align = layout.get("main_align", "min")
        cross_align = layout.get("cross_align", "min")

        classes = []
        if mode == "horizontal":
            classes.append("flex flex-row")
            if gap > 0: classes.append(f"gap-[{int(gap)}px]")
            if main_align == "spaceBetween": classes.append("justify-between")
            elif main_align == "center": classes.append("justify-center")
            if cross_align == "center": classes.append("items-center")
        elif mode == "vertical":
            classes.append("flex flex-col")
            if gap > 0: classes.append(f"gap-[{int(gap)}px]")
            if main_align == "spaceBetween": classes.append("justify-between")
            elif main_align == "center": classes.append("justify-center")
            if cross_align == "center": classes.append("items-center")

        # Padding
        pt, pr, pb, pl = pad
        if pt == pb == pr == pl and pt > 0: classes.append(f"p-[{int(pt)}px]")
        else:
            if pt == pb and pt > 0: classes.append(f"py-[{int(pt)}px]")
            elif pt > 0: classes.append(f"pt-[{int(pt)}px]")
            if pr == pl and pr > 0: classes.append(f"px-[{int(pr)}px]")
            elif pr > 0: classes.append(f"pr-[{int(pr)}px]")

        if bg_class: classes.append(bg_class)
        if border_class: classes.append(border_class)
        if rounded_class: classes.append(rounded_class)
        if node.get("clip"): classes.append("overflow-hidden")

        # Sizing inside parent
        ch = node.get("child_layout", {})
        if ch.get("sizing_h") == "fill": classes.append("w-full")
        if ch.get("sizing_v") == "fill": classes.append("h-full")

        classes_str = f' class="{" ".join([c for c in classes if c])}"' if classes else ""
        children = node.get("children", [])

        if not children:
            return f'{indent}<div{classes_str} />'

        lines = [f'{indent}<div{classes_str}> <!-- {name} -->']
        for cid in children:
            child_str = node_to_svelte(doc, cid, indent_level + 1)
            if child_str:
                lines.append(child_str)
        lines.append(f'{indent}</div>')
        return "\n".join(lines)

    return ""


# ---------------------------------------------------------------------------
# CLI CONTROLLER
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="FigCraft CLI: Live automation & offline .figcraft generator for AI agents"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: file
    file_p = subparsers.add_parser("file", help="Offline .figcraft file operations")
    file_sub = file_p.add_subparsers(dest="file_action", required=True)

    # file inspect
    p_ins = file_sub.add_parser("inspect", help="Inspect a .figcraft document")
    p_ins.add_argument("path", help="Path to .figcraft file")

    # file code (Design-to-Code generator)
    p_code = file_sub.add_parser("code", help="Convert FigCraft node into Svelte + Tailwind markup")
    p_code.add_argument("path", help="Path to .figcraft file")
    p_code.add_argument("--id", type=int, default=None, help="Node ID to convert (default: first top frame)")

    # file create
    p_create = file_sub.add_parser("create", help="Create a new consistent .figcraft file")
    p_create.add_argument("path", help="Output .figcraft file path")
    p_create.add_argument("--template", choices=["workbench", "tokens", "blank", "all"], default="all", help="Preset design template")
    p_create.add_argument("--name", default="Kuron Studio", help="Project name")

    # file add-screen
    p_add = file_sub.add_parser("add-screen", help="Add a screen frame to existing .figcraft file")
    p_add.add_argument("path", help="Path to .figcraft file")
    p_add.add_argument("--screen", choices=["workbench", "tokens"], required=True, help="Screen type")
    p_add.add_argument("--page-index", type=int, help="Target page index (default: 0)")
    p_add.add_argument("--page-name", help="Target page name (overrides index)")

    # Subcommand: live
    live_p = subparsers.add_parser("live", help="Live FigCraft.app automation via socket")
    live_sub = live_p.add_subparsers(dest="live_action", required=True)

    # live status
    p_stat = live_sub.add_parser("status", help="Check FigCraft live status")
    p_stat.add_argument("--port", type=int, default=9880, help="Control server port")

    # live exec
    p_exec = live_sub.add_parser("exec", help="Execute an engine command live")
    p_exec.add_argument("cmd", help="Engine command ID (e.g. node.create, node.set, file.save)")
    p_exec.add_argument("params", nargs="?", default="{}", help="JSON params for command")
    p_exec.add_argument("--port", type=int, default=9880)

    # live export
    p_exp = live_sub.add_parser("export", help="Export active node to PNG/SVG")
    p_exp.add_argument("--id", type=int, required=True, help="Node ID to export")
    p_exp.add_argument("--out", required=True, help="Output image path (.png/.svg)")
    p_exp.add_argument("--format", default="png", choices=["png", "svg", "jpg", "pdf", "webp"])
    p_exp.add_argument("--scale", type=float, default=1.0)
    p_exp.add_argument("--port", type=int, default=9880)

    # Subcommand: tokens
    tok_p = subparsers.add_parser("tokens", help="Print design tokens")
    tok_p.add_argument("--json", action="store_true", help="Print in JSON format")

    args = parser.parse_args()

    if args.command == "tokens":
        if args.json:
            print(json.dumps(TOKENS, indent=2))
        else:
            print("=== KURON STUDIO DESIGN TOKENS ===")
            print("\n[COLORS]")
            for k, v in TOKENS["colors"].items():
                print(f"  --ks-{k.replace('_', '-')}: {v}")
            print("\n[TYPOGRAPHY]")
            for k, v in TOKENS["typography"]["sizes"].items():
                print(f"  text-{k}: {v}pt")
            print("\n[RADII]")
            for k, v in TOKENS["radii"].items():
                print(f"  rounded-{k}: {v}px")
        return

    elif args.command == "file":
        if args.file_action == "inspect":
            doc = FigcraftDocument.load(args.path)
            nodes = doc.doc.get("nodes", {})
            page = nodes.get("1", {})
            print(f"Document: {doc.name}")
            print(f"File Path: {args.path}")
            print(f"Total Nodes: {len(nodes)}")
            top_level = page.get("children", [])
            print(f"Top-Level Frames ({len(top_level)}):")
            for cid in top_level:
                cnode = nodes.get(str(cid), {})
                print(f"  - [{cid}] {cnode.get('name')} ({cnode.get('type')}) - {cnode.get('width')}x{cnode.get('height')}")

        elif args.file_action == "code":
            doc = FigcraftDocument.load(args.path)
            nodes = doc.doc.get("nodes", {})
            target_id = args.id
            if target_id is None:
                page = nodes.get("1", {})
                ch = page.get("children", [])
                if ch:
                    target_id = ch[0]
                else:
                    print("Error: No frames found in document.")
                    sys.exit(1)
            code = node_to_svelte(doc, target_id)
            print(f"<!-- SVELTE + TAILWIND CODE FOR NODE [{target_id}] -->")
            print(code)

        elif args.file_action == "create":
            doc = FigcraftDocument(args.name)
            if args.template in ["workbench", "all"]:
                build_workbench_screen(doc, x=40.0, y=40.0)
            if args.template in ["tokens", "all"]:
                build_tokens_screen(doc, x=1360.0, y=40.0)
            doc.save(args.path)
            print(f"Successfully generated FigCraft design file: {args.path}")

        elif args.file_action == "add-screen":
            doc = FigcraftDocument.load(args.path)
            # Find max X on the selected page to place the screen to the right.
            nodes = doc.doc.get("nodes", {})
            page = nodes.get(str(doc.resolve_page(args.page_index, args.page_name)), {})
            max_x = 40.0
            for cid in page.get("children", []):
                cn = nodes.get(str(cid), {})
                tf = cn.get("transform", [1,0,0,1,0,0])
                w = cn.get("width", 0)
                right = tf[4] + w
                if right > max_x:
                    max_x = right
            new_x = max_x + 80.0

            if args.screen == "workbench":
                build_workbench_screen(doc, x=new_x, y=40.0,
                                       page_index=args.page_index,
                                       page_name=args.page_name)
            elif args.screen == "tokens":
                build_tokens_screen(doc, x=new_x, y=40.0,
                                    page_index=args.page_index,
                                    page_name=args.page_name)
            doc.save()
            print(f"Added {args.screen} screen at x={new_x} to {args.path}")

    elif args.command == "live":
        client = FigcraftClient(port=args.port)
        if not client.connect():
            print(f"Error: FigCraft is not running on 127.0.0.1:{args.port}")
            print("Start FigCraft with: /Applications/FigCraft.app/Contents/MacOS/FigCraft --control " + str(args.port))
            sys.exit(1)

        try:
            if args.live_action == "status":
                info = client.document_inspect()
                print("FigCraft Live Status: CONNECTED")
                print(json.dumps(info.get("result", {}), indent=2))

            elif args.live_action == "exec":
                params = json.loads(args.params)
                res = client.engine_execute(args.cmd, params)
                print(json.dumps(res, indent=2))

            elif args.live_action == "export":
                res = client.export_frame(args.id, args.out, format=args.format, scale=args.scale)
                print(f"Exported node {args.id} to {args.out}")
                print(json.dumps(res, indent=2))
        finally:
            client.close()

if __name__ == "__main__":
    main()
