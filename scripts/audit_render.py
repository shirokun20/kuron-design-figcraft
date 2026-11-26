#!/usr/bin/env python3
"""Objective render audit for kuron-design-figcraft 3.2.3.

Numeric evidence replaces "the PNG looks right": canvas utilisation, text
overflow, child content escaping frame bounds, disabled clipping, connector
topology, dot semantics, WCAG contrast in **both** themes, descriptive English
labels (S-15), and wrapper-card containment/fit (S-16). Every check cites the
rule ID it enforces.

Every top-level frame on every page (``pages[0..N]``) is audited as its own
board. Traversal, contrast ancestry, and layout checks are scoped to that
board, so adjacent boards and other pages never create false positives; board
overlap is checked separately per page. A specific page can be selected by
index or name.

Usage: python3 scripts/audit_render.py <file.figcraft> [--screen ID]
       [--page-index N | --page-name NAME]
Exit 0 = all checks pass; 1 = at least one failure.
"""

import argparse
import json
import os
import re
import sys
import zipfile
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from design_manifest import contrast_ratio, load_design, to_builder_tokens  # noqa: E402
from figcraft_tool import _lint_hex, freeform_piled_children  # noqa: E402

DESIGN = load_design()
FAIL: List[str] = []
SUMMARY: Dict[str, int] = {}
# Names such as "frame", "Untitled 2", or "text" are not descriptive labels.
GENERIC_NAME = re.compile(
    r"^(untitled|frame|rectangle|ellipse|text|group|component|node|layer|"
    r"shape|object|item|section)(\s+\d+)?$", re.IGNORECASE)
# Typographic punctuation that is safe in English captions (S-15). Other
# non-ASCII characters still indicate non-English text or mojibake.
SAFE_TYPOGRAPHY = frozenset("·—–★•…")
MIN_CARD_DIMENSION = 60.0
MIN_CARD_FILL = 0.30
MAX_TREE_NODES = 100000
MAX_ANCESTOR_STEPS = 64
MAX_BOARDS = 256


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


def absolute_box(nodes: Dict[str, Any], node_id: Any, root_id: Any = None):
    """Accumulate local transforms up to the board root for a descendant.

    Child transforms are stored relative to their parent frame, so summing the
    ancestor chain (bounded by ``MAX_ANCESTOR_STEPS``) yields board-relative
    coordinates. Stopping at ``root_id`` keeps sibling boards out of the
    calculation.
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
        if root_id is not None and current == str(root_id):
            return x, y, width, height
        parent = node.get("parent")
        parent_node = nodes.get(str(parent))
        if (parent is None or str(parent) == current
                or (isinstance(parent_node, dict) and parent_node.get("type") == "page")):
            return x, y, width, height
        current = str(parent)
    return x, y, 0.0, 0.0


def content_bounds(nodes: Dict[str, Any], screen_id: Any, root_id: Any = None):
    """Bounding box of visible leaf content in one board's subtree.

    Returns ``(x0, y0, x1, y1)`` or ``None`` when the board holds no visible
    leaf content — an empty full-size wrapper therefore scores zero, not 100%.
    """
    xs0, ys0, xs1, ys1 = [], [], [], []
    for nid in subtree(nodes, screen_id):
        if nid == str(screen_id):
            continue
        node = nodes.get(nid)
        if not isinstance(node, dict) or not is_visible_content(node):
            continue
        x, y, w, h = absolute_box(nodes, nid, root_id=root_id or screen_id)
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


def ancestor_fill(nodes: Dict[str, Any], node: Dict[str, Any],
                  root_id: Any = None) -> Optional[str]:
    """Find the nearest solid fill, bounded by the audited board root.

    Without the board bound a text node in an unfilled wrapper could be
    measured against a sibling board's surface — a cross-board false positive.
    """
    parent_id = str(node.get("parent", ""))
    for _ in range(MAX_ANCESTOR_STEPS):
        parent = nodes.get(parent_id)
        if not isinstance(parent, dict):
            return None
        paint = first_paint_hex(parent)
        if parent.get("type") in ("frame", "rectangle", "page") and paint:
            return paint
        if root_id is not None and parent_id == str(root_id):
            return None
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


def is_descriptive_name(name: Any) -> bool:
    """Whether a node name or visible caption is a descriptive English label."""
    value = str(name or "").strip()
    if not value or GENERIC_NAME.match(value):
        return False
    if any(ord(char) > 127 and char not in SAFE_TYPOGRAPHY for char in value):
        return False
    return any(char.isascii() and char.isalpha() for char in value)


def corner_radius(node: Dict[str, Any]) -> float:
    """Read the first corner radius from either schema spelling."""
    radii = (node.get("corners") or {}).get("radii") or []
    if radii:
        try:
            return float(radii[0])
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(node.get("cornerRadius") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def is_wrapper_card(node: Dict[str, Any]) -> bool:
    """A filled, rounded rectangular container that wraps child content.

    Circular icon badges are excluded: their small glyphs are intentionally
    centred with wide visual padding, not card content that should fill them.
    """
    if node.get("type") != "frame" or not node.get("children"):
        return False
    if first_paint_hex(node) is None:
        return False
    width, height = float(node.get("width", 0)), float(node.get("height", 0))
    if min(width, height) < MIN_CARD_DIMENSION:
        return False
    return corner_radius(node) < min(width, height) / 2.0 - 1.0


def audit_labels(nodes: Dict[str, Any], screen_id: Any, label: str) -> None:
    """Rule S-15: every board item needs a descriptive English name/label."""
    for node_id in subtree(nodes, screen_id):
        node = nodes.get(node_id)
        if not isinstance(node, dict) or node.get("type") == "page":
            continue
        name = node.get("name")
        SUMMARY["labels"] += 1
        if not is_descriptive_name(name):
            note(label, "S-15", "node %s has a non-descriptive name %r"
                 % (node_id, name))
        if node.get("type") == "text":
            characters = str(node.get("characters") or "").strip()
            # Decorative glyphs ("—", "•") are not labels; only text that
            # reads as a word needs a descriptive English caption.
            if any(char.isascii() and char.isalpha() for char in characters) \
                    and not is_descriptive_name(characters):
                note(label, "S-15", "text %s has a non-descriptive label %r"
                     % (node_id, characters))


def audit_card_fit(nodes: Dict[str, Any], screen_id: Any, label: str) -> None:
    """Rule S-16: wrapper cards contain their children and fit their content."""
    for node_id in subtree(nodes, screen_id):
        node = nodes.get(node_id)
        if not isinstance(node, dict) or not is_wrapper_card(node):
            continue
        width, height = float(node.get("width", 0)), float(node.get("height", 0))
        boxes = []
        for child_id in node.get("children", []) or []:
            child = nodes.get(str(child_id))
            if isinstance(child, dict):
                boxes.append(frame_box(child))
        if not boxes:
            continue
        SUMMARY["cards"] += 1
        x0, y0 = min(box[0] for box in boxes), min(box[1] for box in boxes)
        x1 = max(box[0] + box[2] for box in boxes)
        y1 = max(box[1] + box[3] for box in boxes)
        escape = max(-x0, -y0, x1 - width, y1 - height)
        if escape > 1.0:
            note(label, "S-16", "card '%s' containment: child escapes bounds "
                 "by %.0fpx" % (node.get("name"), escape))
            continue
        fill = max(0.0, x1 - x0) * max(0.0, y1 - y0) / (width * height)
        if fill + 1e-9 < MIN_CARD_FILL:
            note(label, "S-16", "card '%s' fit: content occupies %.0f%% of the "
                 "card (needs >= %d%%)" % (node.get("name"), fill * 100,
                                          MIN_CARD_FILL * 100))


def audit_structure(nodes: Dict[str, Any], screen_id: Any, label: str) -> None:
    """Structural checks: no duplicate child ids, no piled freeform siblings."""
    for node_id in subtree(nodes, screen_id):
        node = nodes.get(node_id)
        if not isinstance(node, dict):
            continue
        children = node.get("children") or []
        if not isinstance(children, list):
            continue
        seen: set = set()
        duplicates: List[str] = []
        for child_id in children:
            key = str(child_id)
            if key in seen and key not in duplicates:
                duplicates.append(key)
            seen.add(key)
        if duplicates:
            note(label, "S-17",
                 "node '%s' has duplicate child id %s"
                 % (node.get("name"), ", ".join(duplicates)))
        piled = freeform_piled_children(nodes, node)
        if len(piled) >= 2:
            note(label, "S-18",
                 "frame '%s' has %d siblings piled at (0,0) in freeform layout"
                 % (node.get("name"), len(piled)))


def audit_screen(nodes: Dict[str, Any], screen_id: Any,
                 root_id: Any = None,
                 page_label: Optional[str] = None) -> None:
    """Audit one board on a page, scoped to its root."""
    board_root = root_id if root_id is not None else screen_id
    screen = nodes[str(screen_id)]
    name = screen.get("name", screen_id)
    label = ("%s / %s" % (page_label, name)) if page_label else name
    audit_labels(nodes, screen_id, label)
    audit_card_fit(nodes, screen_id, label)
    audit_structure(nodes, screen_id, label)
    x0, y0, width, height = frame_box(screen)
    children = [nodes[str(c)] for c in screen.get("children", [])
                if str(c) in nodes]
    if not screen.get("children"):
        note(label, "S-06", "board has 0 children (empty board)")
    try:
        valid_size = float(width) > 0 and float(height) > 0
    except (TypeError, ValueError):
        valid_size = False
    if not valid_size:
        note(label, "S-06", "board has non-positive size (%sx%s)" % (width, height))
        return

    # Canvas utilisation: bounding box of visible leaf content vs the screen
    # frame. Empty layout wrappers (Body, Canvas, ...) never count as content.
    bounds = content_bounds(nodes, screen_id, root_id=board_root)
    if bounds is None:
        note(label, "S-06", "canvas utilisation 0% < 60% (no visible leaf content)")
    else:
        content_left, content_top, content_right, content_bottom = bounds
        utilisation = ((content_right - content_left)
                       * (content_bottom - content_top)) / (width * height)
        if utilisation < 0.60:
            note(label, "S-06", "canvas utilisation %.0f%% < 60%%" % (utilisation * 100))
        if y0 + height - content_bottom > 150 and "Flow" not in str(name):
            note(label, "S-06", "more than 150px of dead space at the bottom")

    # Clipping: a screen frame must contain its own content.
    if screen.get("clip") is False:
        note(label, "S-11", "screen frame has clip: false — enable clipping")

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
                note(label, "S-08", "text '%s' overflows horizontally (%.0f > %.0f)"
                     % (current.get("name"), current.get("width", 0), inner_width))
            if inner_height and bottom > inner_height + 1:
                note(label, "S-10", "text '%s' overflows vertically (%.0f > %.0f)"
                     % (current.get("name"), bottom, inner_height))

            foreground = first_paint_hex(current)
            background = ancestor_fill(nodes, current, root_id=board_root)
            ratio = contrast_ratio(foreground, background) if foreground and background else None
            if ratio is not None and ratio + 1e-9 < thresholds["required"]:
                note(label, "S-12", "text '%s' contrast %.2f:1 below %s %.2f:1"
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
                note(label, "S-11", "node '%s' escapes parent '%s' bounds"
                     % (current.get("name"), parent.get("name")))

    # Connector topology: a connector must be anchored at both ends.
    for child in children:
        if child.get("type") != "vector" or not str(child.get("name", "")).startswith(
                ("lnk", "drop", "back", "br", "loop", "blink")):
            continue
        vertices = child.get("network", {}).get("vertices", [])
        if not vertices:
            note(label, "S-03", "connector '%s' has no vertices" % child.get("name"))
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
            note(label, "S-03", "connector '%s' is orphaned (%d/2 ends attached)"
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
                note(label, "S-13", "dot '%s' uses %s, expected %s"
                     % (node_name, fill, expected))


def audit_board_overlap(nodes: Dict[str, Any], board_ids: List[int],
                        label: str) -> None:
    """Flag any two top-level boards whose rectangles overlap (rule S-14)."""
    for index, first in enumerate(board_ids[:MAX_BOARDS]):
        ax, ay, aw, ah = frame_box(nodes[str(first)])
        for second in board_ids[index + 1:MAX_BOARDS]:
            bx, by, bw, bh = frame_box(nodes[str(second)])
            overlap_w = min(ax + aw, bx + bw) - max(ax, bx)
            overlap_h = min(ay + ah, by + bh) - max(ay, by)
            if overlap_w > 1 and overlap_h > 1:
                note(label, "S-14",
                     "boards '%s' and '%s' overlap by %.0fx%.0fpx"
                     % (nodes[str(first)].get("name"), nodes[str(second)].get("name"),
                        overlap_w, overlap_h))


def resolve_page_ids(document: Dict[str, Any], nodes: Dict[str, Any],
                     page_index: Optional[int] = None,
                     page_name: Optional[str] = None) -> List[int]:
    """Resolve page ids for ``pages[0..N]`` by name, index, or all by default."""
    ids = [int(pid) for pid in (document.get("pages") or [])]
    if page_name is not None:
        matches = [pid for pid in ids
                   if str(nodes.get(str(pid), {}).get("name")) == page_name]
        if not matches:
            available = [str(nodes.get(str(pid), {}).get("name")) for pid in ids]
            raise ValueError("page %r not found; available pages: %s"
                             % (page_name, ", ".join(available)))
        return matches
    if page_index is not None:
        index = int(page_index)
        if index < 0 or index >= len(ids):
            raise ValueError("page_index %d is out of range for %d page(s)"
                             % (index, len(ids)))
        return [ids[index]]
    return ids


def audit_file(path: str, screen_id: Optional[str] = None,
               page_index: Optional[int] = None,
               page_name: Optional[str] = None) -> List[str]:
    """Audit every board on every page of a .figcraft file."""
    FAIL.clear()
    SUMMARY.clear()
    SUMMARY.update({"labels": 0, "cards": 0})
    audit_contract_contrast()
    with zipfile.ZipFile(path) as archive:
        with archive.open("document.json") as handle:
            document = json.load(handle)
    nodes = document.get("nodes", {})
    if screen_id:
        audit_screen(nodes, screen_id, root_id=screen_id)
    else:
        for page_id in resolve_page_ids(document, nodes, page_index, page_name):
            page = nodes.get(str(page_id), {})
            label = "page '%s'" % page.get("name") if page.get("name") \
                else "pages[%d]" % page_id
            if not (page.get("children") or []):
                note(label, "S-06", "page has 0 children (no boards to audit)")
                continue
            board_ids = [
                int(child_id) for child_id in page.get("children", [])
                if isinstance(nodes.get(str(child_id)), dict)
                and nodes[str(child_id)].get("type") == "frame"
            ]
            if not board_ids:
                continue
            audit_board_overlap(nodes, board_ids, label)
            for board_id in board_ids[:MAX_BOARDS]:
                audit_screen(nodes, board_id, root_id=board_id, page_label=label)
    return FAIL


def main() -> None:
    parser = argparse.ArgumentParser(description="Objective FigCraft render audit")
    parser.add_argument("file", help="Path to a .figcraft file")
    parser.add_argument("--screen", help="Audit only this screen id")
    page_group = parser.add_mutually_exclusive_group()
    page_group.add_argument("--page-index", type=int,
                            help="Audit only this page index (0-based)")
    page_group.add_argument("--page-name", help="Audit only this page name")
    args = parser.parse_args()
    failures = audit_file(args.file, args.screen,
                          page_index=args.page_index, page_name=args.page_name)
    if failures:
        print("FAIL:")
        for failure in failures:
            print(" -", failure)
        sys.exit(1)
    print("PASS: all screens passed the render audit.")
    print("  S-15 labels: %d/%d descriptive English names and captions checked."
          % (SUMMARY.get("labels", 0) - len([f for f in failures if "S-15" in f]),
             SUMMARY.get("labels", 0)))
    print("  S-16 containment/fit: %d/%d wrapper cards fit their content."
          % (SUMMARY.get("cards", 0) - len([f for f in failures if "S-16" in f]),
             SUMMARY.get("cards", 0)))


if __name__ == "__main__":
    main()
