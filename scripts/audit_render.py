#!/usr/bin/env python3
"""Objective render audit for kuron-design-figcraft 3.1.0.

Numeric evidence replaces "the PNG looks right": canvas utilisation, text
overflow, child content escaping frame bounds, disabled clipping, connector
topology, dot semantics, and WCAG contrast in **both** themes. Every check
cites the rule ID it enforces.

Usage: python3 scripts/audit_render.py <file.figcraft> [--screen ID]
Exit 0 = all checks pass; 1 = at least one failure.
"""

import argparse
import json
import os
import sys
import zipfile
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from design_manifest import contrast_ratio, load_design, to_builder_tokens  # noqa: E402
from figcraft_tool import _lint_hex  # noqa: E402

DESIGN = load_design()
FAIL: List[str] = []
MAX_TREE_NODES = 100000
MAX_ANCESTOR_STEPS = 64


def note(screen: Any, rule: str, msg: str) -> None:
    FAIL.append("[%s] %s: %s" % (screen, rule, msg))


def frame_box(node: Dict[str, Any]):
    transform = node.get("transform", [1, 0, 0, 1, 0, 0])
    return transform[4], transform[5], node.get("width", 0), node.get("height", 0)


# Leaf types are the only shapes that occupy visible pixels on their own. A
# full-size layout wrapper (Body, Canvas, Card grid, ...) is not content just
# because it has a bounding box.
CONTENT_TYPES = {"text", "rectangle", "vector", "ellipse"}


def is_visible_content(node: Dict[str, Any]) -> bool:
    """Whether a node itself paints visible content (not a layout wrapper)."""
    if node.get("visible") is False or node.get("type") not in CONTENT_TYPES:
        return False
    return first_paint_hex(node) is not None


def absolute_box(nodes: Dict[str, Any], node_id: Any):
    """Accumulate local transforms up to the screen for a descendant node.

    Child transforms are stored relative to their parent frame, so summing the
    ancestor chain (bounded by ``MAX_ANCESTOR_STEPS``) yields canvas-relative
    coordinates suitable for a utilisation calculation.
    """
    x = y = 0.0
    current = str(node_id)
    width = height = 0.0
    seen = set()
    for step in range(MAX_ANCESTOR_STEPS):
        if current in seen:
            break
        seen.add(current)
        node = nodes.get(current)
        if not isinstance(node, dict):
            break
        tx, ty, node_w, node_h = frame_box(node)
        x += tx
        y += ty
        if step == 0:
            width, height = node_w, node_h
        parent = node.get("parent")
        if parent is None or str(parent) == current or str(parent) == "1":
            return x, y, width, height
        current = str(parent)
    return x, y, 0.0, 0.0


def content_bounds(nodes: Dict[str, Any], screen_id: Any):
    """Bounding box of visible leaf content in a screen's subtree.

    Returns ``(x0, y0, x1, y1)`` or ``None`` when the screen holds no visible
    leaf content — an empty full-size wrapper therefore scores zero, not 100%.
    """
    xs0, ys0, xs1, ys1 = [], [], [], []
    for nid in subtree(nodes, screen_id):
        if nid == str(screen_id):
            continue
        node = nodes.get(nid)
        if not isinstance(node, dict) or not is_visible_content(node):
            continue
        x, y, w, h = absolute_box(nodes, nid)
        if w > 0 and h > 0:
            xs0.append(x)
            ys0.append(y)
            xs1.append(x + w)
            ys1.append(y + h)
    if not xs0:
        return None
    return min(xs0), min(ys0), max(xs1), max(ys1)


def first_paint_hex(node: Dict[str, Any]) -> Optional[str]:
    """Return the first visible solid paint colour of a node, if any."""
    for key in ("fills", "strokes"):
        for paint in node.get(key, []) or []:
            if not paint.get("visible", True):
                continue
            color = paint.get("color")
            if isinstance(color, dict):
                return _lint_hex(color)
    return None


def subtree(nodes: Dict[str, Any], root_id: Any) -> List[str]:
    """Bounded subtree walk with a visited set (cut-loop guard)."""
    out, stack, seen = [], [str(root_id)], set()
    while stack and len(seen) < MAX_TREE_NODES:
        current = str(stack.pop())
        if current in seen:
            continue
        seen.add(current)
        out.append(current)
        node = nodes.get(current, {})
        if isinstance(node, dict):
            stack.extend(str(child) for child in node.get("children", []) or [])
    return out


def ancestor_fill(nodes: Dict[str, Any], node: Dict[str, Any]) -> Optional[str]:
    """Find the nearest ancestor with a solid background fill."""
    parent_id = str(node.get("parent", ""))
    for _ in range(MAX_ANCESTOR_STEPS):
        parent = nodes.get(parent_id)
        if not isinstance(parent, dict):
            return None
        paint = first_paint_hex(parent)
        if parent.get("type") in ("frame", "rectangle", "page") and paint:
            return paint
        parent_id = str(parent.get("parent", ""))
        if not parent_id:
            return None
    return None


def contrast_thresholds() -> Dict[str, Any]:
    """Derive the required WCAG ratio from a11y.minContrast."""
    a11y = DESIGN["a11y"]
    level = str(a11y["minContrast"]).upper()
    key = "aaaNormal" if level == "AAA" else "normal"
    return {"level": level, "required": float(a11y["minContrastRatio"][key])}


def audit_contract_contrast() -> None:
    """Audit the canonical role pairs for dark and light themes."""
    thresholds = contrast_thresholds()
    for theme in ("dark", "light"):
        colors = to_builder_tokens(DESIGN, theme)["colors"]
        for foreground, background in (
            ("text", "bg"),
            ("action-primary", "action-primary-fg"),
            ("data-technical", "bg"),
        ):
            ratio = contrast_ratio(colors[foreground], colors[background])
            if ratio is None or ratio + 1e-9 < thresholds["required"]:
                shown = "unmeasurable" if ratio is None else "%.2f:1" % ratio
                note(theme, "S-12",
                     "contrast of %s on %s is %s, below %s %.2f:1"
                     % (foreground, background, shown, thresholds["level"],
                        thresholds["required"]))


def audit_screen(nodes: Dict[str, Any], screen_id: Any) -> None:
    """Audit one top-level screen frame."""
    screen = nodes[str(screen_id)]
    name = screen.get("name", screen_id)
    x0, y0, width, height = frame_box(screen)
    if not width or not height:
        return
    children = [nodes[str(c)] for c in screen.get("children", [])
                if str(c) in nodes]

    # Canvas utilisation: bounding box of visible leaf content vs the screen
    # frame. Empty layout wrappers (Body, Canvas, ...) never count as content.
    bounds = content_bounds(nodes, screen_id)
    if bounds is None:
        note(name, "S-06", "canvas utilisation 0% < 60% (no visible leaf content)")
    else:
        content_left, content_top, content_right, content_bottom = bounds
        utilisation = ((content_right - content_left)
                       * (content_bottom - content_top)) / (width * height)
        if utilisation < 0.60:
            note(name, "S-06", "canvas utilisation %.0f%% < 60%%" % (utilisation * 100))
        if y0 + height - content_bottom > 150 and "Flow" not in str(name):
            note(name, "S-06", "more than 150px of dead space at the bottom")

    # Clipping: a screen frame must contain its own content.
    if screen.get("clip") is False:
        note(name, "S-11", "screen frame has clip: false — enable clipping")

    # Text overflow, border escapes, and contrast.
    thresholds = contrast_thresholds()
    for node in subtree(nodes, screen_id):
        if node == str(screen_id):
            continue
        current = nodes.get(node)
        if not isinstance(current, dict):
            continue
        parent = nodes.get(str(current.get("parent", "")), {})
        if not isinstance(parent, dict):
            continue

        if current.get("type") == "text":
            parent_width = parent.get("width") or 0
            padding = (parent.get("layout") or {}).get("padding", [0, 0, 0, 0]) or [0, 0, 0, 0]
            try:
                inner_width = float(parent_width) - float(padding[1]) - float(padding[3])
                inner_height = float(parent.get("height", 0)) - float(padding[2])
                bottom = float(current.get("transform", [0] * 6)[5]) + float(current.get("height", 0))
            except (IndexError, TypeError, ValueError):
                inner_width, inner_height, bottom = float(parent_width), 0.0, 0.0
            if parent_width and current.get("width", 0) > inner_width + 1:
                note(name, "S-08", "text '%s' overflows horizontally (%.0f > %.0f)"
                     % (current.get("name"), current.get("width", 0), inner_width))
            if inner_height and bottom > inner_height + 1:
                note(name, "S-10", "text '%s' overflows vertically (%.0f > %.0f)"
                     % (current.get("name"), bottom, inner_height))

            foreground = first_paint_hex(current)
            background = ancestor_fill(nodes, current)
            ratio = contrast_ratio(foreground, background) if foreground and background else None
            if ratio is not None and ratio + 1e-9 < thresholds["required"]:
                note(name, "S-12", "text '%s' contrast %.2f:1 below %s %.2f:1"
                     % (current.get("name"), ratio, thresholds["level"],
                        thresholds["required"]))

        # Content escaping its parent's frame bounds is a clipping defect
        # regardless of the clip flag; the flag itself is reported above.
        if parent.get("type") in ("frame", "rectangle") and current.get("type") in (
            "frame", "rectangle", "text", "vector", "ellipse",
        ):
            # Child transforms are stored relative to the parent frame, so
            # compare against the parent's local (0, 0, width, height) box.
            cx, cy, cw, ch = frame_box(current)
            _, _, pw, ph = frame_box(parent)
            if pw and ph and (cx < -1 or cy < -1
                              or cx + cw > pw + 1 or cy + ch > ph + 1):
                note(name, "S-11", "node '%s' escapes parent '%s' bounds"
                     % (current.get("name"), parent.get("name")))

    # Connector topology: a connector must be anchored at both ends.
    for child in children:
        if child.get("type") != "vector" or not str(child.get("name", "")).startswith(
                ("lnk", "drop", "back", "br", "loop", "blink")):
            continue
        vertices = child.get("network", {}).get("vertices", [])
        if not vertices:
            note(name, "S-03", "connector '%s' has no vertices" % child.get("name"))
            continue
        points = [(v["x"], v["y"]) for v in vertices]
        anchored = 0
        for px, py in (points[0], points[-1]):
            for candidate in children:
                if candidate.get("type") not in ("frame", "rectangle"):
                    continue
                x, y, w, h = frame_box(candidate)
                if x - 4 <= px <= x + w + 4 and y - 4 <= py <= y + h + 4:
                    anchored += 1
                    break
        if anchored < 2:
            note(name, "S-03", "connector '%s' is orphaned (%d/2 ends attached)"
                 % (child.get("name"), anchored))

    # Dot semantics: completion/cancellation/prerequisite colours.
    colors = to_builder_tokens(DESIGN, DESIGN.get("default_theme", "dark"))["colors"]
    for child in children:
        node_name = str(child.get("name", ""))
        if child.get("type") != "frame" or not (
                node_name.startswith("Note_") or node_name == "Prereq"):
            continue
        descendants = subtree(nodes, child.get("id"))
        titles = " ".join(str(nodes[n].get("characters", "")) for n in descendants
                          if nodes[n].get("type") == "text").upper()
        dots = [nodes[n] for n in descendants
                if nodes[n].get("type") == "rectangle"
                and (nodes[n].get("width") or 0) <= 12]
        for dot in dots:
            fill = first_paint_hex(dot)
            if not fill:
                continue
            expected = None
            if "CANCEL" in titles or "BATAL" in titles:
                expected = colors["text-3"]
            elif "DONE" in titles or "SELESAI" in titles or "NOTIF" in titles:
                expected = colors["status-success"]
            elif "PREREQ" in titles or "IZIN" in titles:
                expected = colors["status-warn"]
            if expected and fill.lower() != str(expected).lower():
                note(name, "S-13", "dot '%s' uses %s, expected %s"
                     % (node_name, fill, expected))


def audit_file(path: str, screen_id: Optional[str] = None) -> List[str]:
    """Audit a .figcraft file; returns the shared failure list."""
    FAIL.clear()
    audit_contract_contrast()
    with zipfile.ZipFile(path) as archive:
        document = json.load(archive.open("document.json"))
    nodes = document.get("nodes", {})
    if screen_id:
        audit_screen(nodes, screen_id)
    else:
        for page_id in document.get("pages", [1]):
            page = nodes.get(str(page_id), {})
            for child_id in page.get("children", []):
                child = nodes.get(str(child_id), {})
                if child.get("type") == "frame" and (child.get("width") or 0) >= 1000:
                    audit_screen(nodes, child_id)
    return FAIL


def main() -> None:
    parser = argparse.ArgumentParser(description="Objective FigCraft render audit")
    parser.add_argument("file", help="Path to a .figcraft file")
    parser.add_argument("--screen", help="Audit only this screen id")
    args = parser.parse_args()
    failures = audit_file(args.file, args.screen)
    if failures:
        print("FAIL:")
        for failure in failures:
            print(" -", failure)
        sys.exit(1)
    print("PASS: all screens passed the render audit.")


if __name__ == "__main__":
    main()
