#!/usr/bin/env python3
"""
FigCraft Artistic Flow Generator — Clean Master (kuron-design-figcraft 3.0.0)
Implements the portable, token-driven UI design system:
- 100% compliant with references/DESIGN.md and references/design-tokens.css
- Full recursive AutoLayout engine that computes exact (x, y, w, h) coordinates
- Cell-frame architecture for tabular ledger (zero column overlap)
- Realistic manga artwork mockups, dense tables, accurate speech bubbles, and inspector fit bars
- 6 complete screens: Dashboard, Page Grid & Pipeline, Workbench Editor, Bubble Ledger, Export Modal, Design Tokens
"""

import sys
import os
import json
import socket
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figcraft_tool import (FigcraftClient, FigcraftDocument, estimate_text_width,
                           hex_to_rgba, make_solid_fill, make_solid_stroke)
from design_manifest import DesignManifestError, load_design, to_builder_tokens

# ---------------------------------------------------------------------------
# DESIGN TOKENS — resolved from DESIGN.md (design-contract/v1)
# ---------------------------------------------------------------------------
# No colour or font dictionary is frozen here. The historical `C` lookup is
# now a derived view over the manifest, which also removes the old
# ring always follows semantic.color.ring, so the old fixed focus colour is gone.
DESIGN_DOC = load_design()
_DARK = to_builder_tokens(DESIGN_DOC, "dark")
_LIGHT = to_builder_tokens(DESIGN_DOC, "light")
CONTENT = DESIGN_DOC.get("content", {})
FONTS = _DARK["fonts"] or {"ui": "Inter", "brand": "Space Grotesk", "mono": "JetBrains Mono"}

_C_MAP = {
    "bg": "bg", "surface": "surface", "surface_2": "surface-2",
    "surface_card": "raised", "surface_raised": "raised", "surface_hover": "hover",
    "line": "line", "line_strong": "line-strong", "ring": "ring",
    "row_hover": "hover", "row_active": "hover",
    "text": "text", "text_muted": "text-2", "text_dim": "text-3",
    "coral": "action-primary", "coral_hover": "action-primary-hover",
    "coral_subtle": "action-primary-soft",
    "cyan": "data-technical", "cyan_subtle": "data-technical-soft",
    "success": "status-success", "success_subtle": "status-success-soft",
    "warn": "status-warn", "warn_subtle": "status-warn-soft",
    "danger": "status-danger", "danger_subtle": "status-danger-soft",
    "info": "status-info", "info_subtle": "status-info-soft",
}
_LIGHT_MAP = {
    "light_bg": "bg", "light_surface": "surface", "light_surface_2": "surface-2",
    "light_raised": "raised", "light_hover": "hover", "light_line": "line",
    "light_text": "text", "light_accent": "action-primary",
    "light_cyan": "data-technical", "light_ring": "ring",
}
C = {key: _DARK["colors"][role] for key, role in _C_MAP.items()}
C.update({key: _LIGHT["colors"][role] for key, role in _LIGHT_MAP.items()})

# Screen map comes from DESIGN.md. The reference generator refuses to guess
# screen positions when the manifest does not declare them.
SCREENS = {
    entry["id"]: entry
    for entry in DESIGN_DOC.get("screens", [])
    if isinstance(entry, dict) and "id" in entry
}


def screen_spec(key: str) -> dict:
    """Return one screen definition from the manifest or fail actionably."""
    if key not in SCREENS:
        raise DesignManifestError(
            "DESIGN.md has no screens entry with id %r. Add a `screens` array "
            "to the design-contract/v1 block (see the package manifest)." % key
        )
    return SCREENS[key]



# ---------------------------------------------------------------------------
# RECURSIVE AUTOLAYOUT RESOLVER
# ---------------------------------------------------------------------------
def resolve_tree_layout(doc_nodes, root_id):
    root = doc_nodes[str(root_id)]
    
    def resolve_node(nid, avail_w, avail_h):
        node = doc_nodes[str(nid)]
        ntype = node.get("type", "frame")
        
        if ntype == "text":
            chars = node.get("characters", "")
            style = node.get("style", {})
            fsize = style.get("font_size", 13.0)
            ffam = style.get("font_family", "Inter")
            tw = estimate_text_width(chars, fsize, ffam)
            th = fsize * 1.35
            ch_layout = node.get("child_layout", {})
            # Engine parity: fill ONLY empty values (0). Measured sizes
            # (from the app save or explicit input) are never overwritten —
            # this stops the script-vs-engine tug-of-war.
            if ch_layout.get("sizing_h") == "hug" and node.get("width", 0) <= 0:
                node["width"] = round(tw, 1)
            if ch_layout.get("sizing_v") == "hug" and node.get("height", 0) <= 0:
                node["height"] = round(th, 1)
            return node["width"], node["height"]

        if ntype != "frame":
            return node.get("width", 0.0), node.get("height", 0.0)

        layout_cfg = node.get("layout")
        children_ids = node.get("children", [])
        
        if not layout_cfg or layout_cfg.get("mode") == "none":
            for cid in children_ids:
                c = doc_nodes[str(cid)]
                resolve_node(cid, c.get("width", 100.0), c.get("height", 100.0))
            return node.get("width", avail_w), node.get("height", avail_h)

        mode = layout_cfg.get("mode", "vertical")
        gap = float(layout_cfg.get("gap", 0.0))
        pad = layout_cfg.get("padding", [0.0, 0.0, 0.0, 0.0])
        pad_t, pad_r, pad_b, pad_l = float(pad[0]), float(pad[1]), float(pad[2]), float(pad[3])
        main_align = layout_cfg.get("main_align", "min")
        cross_align = layout_cfg.get("cross_align", "min")

        parent_w = node.get("width", avail_w)
        parent_h = node.get("height", avail_h)
        inner_w = max(0.0, parent_w - pad_l - pad_r)
        inner_h = max(0.0, parent_h - pad_t - pad_b)

        if not children_ids:
            return parent_w, parent_h

        if mode == "vertical":
            total_fixed_h = 0.0
            fill_v_children = []

            for cid in children_ids:
                c = doc_nodes[str(cid)]
                ch_sizing = c.get("child_layout", {})
                sz_h = ch_sizing.get("sizing_h", "fixed")
                sz_v = ch_sizing.get("sizing_v", "fixed")

                cw, ch = resolve_node(cid, inner_w if sz_h == "fill" else c.get("width", inner_w), c.get("height", 32.0))
                if sz_v == "fill":
                    fill_v_children.append(c)
                else:
                    total_fixed_h += ch

            total_gaps = max(0, len(children_ids) - 1) * gap

            if node.get("child_layout", {}).get("sizing_v") == "hug":
                node["height"] = round(pad_t + total_fixed_h + total_gaps + pad_b, 1)
                inner_h = max(0.0, node["height"] - pad_t - pad_b)

            rem_h = max(0.0, inner_h - total_fixed_h - total_gaps)
            if fill_v_children:
                h_per_fill = rem_h / len(fill_v_children)
                for c in fill_v_children:
                    c["height"] = max(10.0, h_per_fill)
                    resolve_node(c["id"], c["width"], c["height"])

            # main_align vertikal: cermin cabang horizontal (paritas engine —
            # engine live memusatkan/memaksimalkan/menyebar blok vertikal;
            # reflow lama selalu top-pin hingga save-app menggeser 95 wadah).
            tot_children_h = sum(doc_nodes[str(cid)]["height"] for cid in children_ids)
            # CATAT 2026-11-08: spaceBetween vertikal SENGAJA tak di mirror.
            # NOTE 2026-11-08: vertical spaceBetween is deliberately NOT
            # mirrored. Evidence: the engine renders Panel1-02 (spaceBetween)
            # pinned to the top (= min), while Panel1-01 in the middle is a
            # manual user arrangement (43.6, not any layout output). Mirroring
            # spread would break twelve cards in 02 (+37px). The mid-panel
            # intent is preserved via per-case main_align=center.
            if main_align == "max":
                cur_gap = gap
                cur_y = pad_t + max(0.0, inner_h - tot_children_h - total_gaps)
            elif main_align == "center":
                cur_gap = gap
                cur_y = pad_t + max(0.0, (inner_h - tot_children_h - total_gaps) / 2.0)
            else:
                cur_gap = gap
                cur_y = pad_t
            for cid in children_ids:
                c = doc_nodes[str(cid)]
                if cross_align == "center":
                    cur_x = pad_l + max(0.0, (inner_w - c["width"]) / 2.0)
                elif cross_align == "max":
                    cur_x = pad_l + max(0.0, inner_w - c["width"])
                else:
                    cur_x = pad_l

                c["transform"] = [1.0, 0.0, 0.0, 1.0, round(cur_x, 1), round(cur_y, 1)]
                cur_y += c["height"] + cur_gap

        elif mode == "horizontal":
            total_fixed_w = 0.0
            fill_h_children = []

            for cid in children_ids:
                c = doc_nodes[str(cid)]
                ch_sizing = c.get("child_layout", {})
                sz_h = ch_sizing.get("sizing_h", "fixed")
                sz_v = ch_sizing.get("sizing_v", "fixed")

                cw, ch = resolve_node(cid, c.get("width", 100.0), inner_h if sz_v == "fill" else c.get("height", 32.0))
                if sz_h == "fill":
                    fill_h_children.append(c)
                else:
                    total_fixed_w += cw

            total_gaps = max(0, len(children_ids) - 1) * gap

            if node.get("child_layout", {}).get("sizing_h") == "hug":
                node["width"] = round(pad_l + total_fixed_w + total_gaps + pad_r, 1)
                inner_w = max(0.0, node["width"] - pad_l - pad_r)

            rem_w = max(0.0, inner_w - total_fixed_w - total_gaps)
            if fill_h_children:
                w_per_fill = rem_w / len(fill_h_children)
                for c in fill_h_children:
                    c["width"] = max(10.0, w_per_fill)
                    resolve_node(c["id"], c["width"], c["height"])

            tot_children_w = sum(doc_nodes[str(cid)]["width"] for cid in children_ids)
            
            if main_align == "spaceBetween" and len(children_ids) > 1:
                cur_gap = (inner_w - tot_children_w) / (len(children_ids) - 1)
                cur_x = pad_l
            elif main_align == "max":
                cur_gap = gap
                cur_x = pad_l + max(0.0, inner_w - tot_children_w - total_gaps)
            elif main_align == "center":
                cur_gap = gap
                cur_x = pad_l + max(0.0, (inner_w - tot_children_w - total_gaps) / 2.0)
            else:
                cur_gap = gap
                cur_x = pad_l

            # Wrap: split children into several lines when they exceed inner_w
            # (engine parity — without this, a wrapped line collapses to 1 line,
            # mis. ScChecks: chip_1295 meleset 540px).
            wrap = bool(node.get("layout", {}).get("wrap", False))
            cross_gap = float(node.get("layout", {}).get("cross_gap", gap))
            lines: list = []
            if wrap:
                cur_line: list = []
                cur_w = 0.0
                for cid in children_ids:
                    cw = doc_nodes[str(cid)]["width"]
                    add = cw if not cur_line else gap + cw
                    if cur_line and cur_w + add > inner_w + 1e-6:
                        lines.append(cur_line)
                        cur_line = []
                        cur_w = 0.0
                        add = cw
                    cur_line.append(cid)
                    cur_w += add
                if cur_line:
                    lines.append(cur_line)
            else:
                lines = [list(children_ids)]

            if (node.get("child_layout", {}).get("sizing_v") == "hug"
                    and wrap and len(lines) > 1):
                node["height"] = round(
                    pad_t + sum(max(doc_nodes[str(cid)]["height"] for cid in ln) for ln in lines)
                    + cross_gap * (len(lines) - 1) + pad_b, 1)
                inner_h = max(0.0, node["height"] - pad_t - pad_b)

            cur_y = pad_t
            for line in lines:
                line_w = sum(doc_nodes[str(cid)]["width"] for cid in line)
                line_gaps = max(0, len(line) - 1) * gap
                if main_align == "spaceBetween" and len(line) > 1:
                    cur_gap = (inner_w - line_w) / (len(line) - 1)
                    cur_x = pad_l
                elif main_align == "max":
                    cur_gap = gap
                    cur_x = pad_l + max(0.0, inner_w - line_w - line_gaps)
                elif main_align == "center":
                    cur_gap = gap
                    cur_x = pad_l + max(0.0, (inner_w - line_w - line_gaps) / 2.0)
                else:
                    cur_gap = gap
                    cur_x = pad_l

                for cid in line:
                    c = doc_nodes[str(cid)]
                    if cross_align == "center":
                        # The engine draws glyphs from the top of the box (+-2px):
                        # a centred box => centred glyph. Do not tune y manually —
                        # save() always recomputes (see SKILL anti-illusion).
                        y = pad_t + max(0.0, (inner_h - c["height"]) / 2.0) if not wrap else cur_y
                    elif cross_align == "max":
                        y = pad_t + max(0.0, inner_h - c["height"]) if not wrap else cur_y
                    else:
                        y = cur_y

                    c["transform"] = [1.0, 0.0, 0.0, 1.0, round(cur_x, 1), round(y, 1)]
                    cur_x += c["width"] + cur_gap
                if wrap:
                    cur_y += max(doc_nodes[str(cid)]["height"] for cid in line) + cross_gap

        return node.get("width", avail_w), node.get("height", avail_h)

    resolve_node(root_id, root["width"], root["height"])


# ---------------------------------------------------------------------------
# ARTISTIC BUILDER HELPERS
# ---------------------------------------------------------------------------
def add_dimmed_app_background(doc: FigcraftDocument, parent_id: int, title: str):
    """
    Renders an authentic Kuron Studio workbench window in the background,
    layered under a soft translucent dimmed overlay (Level 3 Floating Modal pattern).
    Prevents the empty 'flat black void' and provides realistic atmospheric depth!
    """
    # 1. Base window bar
    add_window_bar(doc, parent_id, title)

    # 2. Mock app header
    h = doc.create_frame("MockHeader", parent_id, 1280.0, 48.0, fill=C["surface_2"], stroke=C["line"], layout_mode="horizontal", gap=16.0, padding=(0.0, 20.0, 0.0, 20.0), main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    hl = doc.create_frame("HL", h, 400.0, 32.0, layout_mode="horizontal", gap=12.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.create_rect("MockLogo", hl, 24.0, 24.0, fill=C["coral"], corner_radius=6.0)
    doc.create_text("MockTitle", "Document 12 ▾", hl, font_size=12.0, font_weight="Bold", color=C["text_dim"])
    doc.create_text("MockCount", "007/182 items", hl, font_size=11.0, font_family=FONTS["mono"], color=C["text_dim"])
    
    hr = doc.create_frame("HR", h, 300.0, 32.0, layout_mode="horizontal", gap=8.0, main_align="max", cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_button("MB1", "Review (F3)", hr, variant="default", size="sm")
    doc.build_button("MB2", "Translate", hr, variant="default", size="sm")

    # 3. Dimmed Manga Grid in the background
    b_grid = doc.create_frame("DimmedGrid", parent_id, 1280.0, 884.0, fill=C["bg"], layout_mode="vertical", gap=14.0, padding=(20.0, 24.0, 20.0, 24.0), sizing_h="fill", sizing_v="fill")
    bg_r1 = doc.create_frame("BGR1", b_grid, 1232.0, 260.0, layout_mode="horizontal", gap=16.0, sizing_h="fill", sizing_v="fixed")
    for i in range(1, 5):
        c = doc.create_frame(f"BGC_{i}", bg_r1, 296.0, 260.0, fill=CONTENT["manga_card"], stroke=C["line"], corner_radius=10.0, layout_mode="vertical", gap=6.0, padding=(10.0, 10.0, 10.0, 10.0), sizing_h="fixed", sizing_v="fixed")
        add_manga_panel_art(doc, c, 276.0, 180.0, f"HALAMAN p00{i}.jpg")
        ft = doc.create_frame(f"BGCF_{i}", c, 276.0, 28.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
        doc.create_text(f"BGCT1_{i}", f"p00{i}.jpg", ft, font_size=11.0, font_family=FONTS["mono"], color=C["text_dim"])
        doc.create_text(f"BGCT2_{i}", "Done", ft, font_size=10.0, color=C["text_dim"])

    bg_r2 = doc.create_frame("BGR2", b_grid, 1232.0, 260.0, layout_mode="horizontal", gap=16.0, sizing_h="fill", sizing_v="fixed")
    for i in range(5, 9):
        c = doc.create_frame(f"BGC_{i}", bg_r2, 296.0, 260.0, fill=CONTENT["manga_card"], stroke=C["line"], corner_radius=10.0, layout_mode="vertical", gap=6.0, padding=(10.0, 10.0, 10.0, 10.0), sizing_h="fixed", sizing_v="fixed")
        add_manga_panel_art(doc, c, 276.0, 180.0, f"HALAMAN p00{i}.jpg")
        ft = doc.create_frame(f"BGCF_{i}", c, 276.0, 28.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
        doc.create_text(f"BGCT1_{i}", f"p00{i}.jpg", ft, font_size=11.0, font_family=FONTS["mono"], color=C["text_dim"])
        doc.create_text(f"BGCT2_{i}", "Processing", ft, font_size=10.0, color=C["text_dim"])

def add_window_bar(doc: FigcraftDocument, parent_id: int, title: str):
    wbar = doc.create_frame(
        name="WindowBar", parent_id=parent_id,
        width=1280.0, height=32.0,
        fill=C["surface_2"], stroke=C["line"],
        layout_mode="horizontal", gap=12.0,
        padding=(0.0, 16.0, 0.0, 16.0),
        main_align="spaceBetween", cross_align="center",
        sizing_h="fill", sizing_v="fixed"
    )
    tl = doc.create_frame("TrafficLights", wbar, 52.0, 12.0, layout_mode="horizontal", gap=8.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.create_ellipse("close", tl, 12.0, CONTENT["traffic_close"])
    doc.create_ellipse("min", tl, 12.0, CONTENT["traffic_min"])
    doc.create_ellipse("max", tl, 12.0, CONTENT["traffic_max"])
    
    doc.create_text("WinTitle", title, wbar, font_size=11.0, font_weight="SemiBold", font_family=FONTS["ui"], color=C["text_muted"])
    
    tag = doc.create_frame("RTag", wbar, 110.0, 18.0, layout_mode="horizontal", gap=6.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.create_ellipse("dot", tag, 6.0, C["success"])
    doc.create_text("stat", "Tauri v2 · Local", tag, font_size=10.0, font_family=FONTS["mono"], color=C["text_dim"])
    return wbar

def add_manga_panel_art(doc: FigcraftDocument, parent_id: int, width: float, height: float, title: str = "MANGA PANEL"):
    art = doc.create_frame(
        name="MangaArt", parent_id=parent_id,
        width=width, height=height,
        fill=CONTENT["panel"], stroke=C["line"],
        corner_radius=6.0, layout_mode="vertical",
        gap=6.0, padding=(8.0, 8.0, 8.0, 8.0),
        sizing_h="fill", sizing_v="fixed"
    )
    top_row = doc.create_frame("PanelRow1", art, width - 16.0, (height - 28.0) * 0.55, layout_mode="horizontal", gap=6.0, sizing_h="fill", sizing_v="fixed")
    p1 = doc.create_frame("Panel1", top_row, (width - 22.0) * 0.6, (height - 28.0) * 0.55, fill=CONTENT["panel_1"], stroke=C["line_strong"], corner_radius=3.0, layout_mode="vertical", main_align="spaceBetween", padding=(6.0, 6.0, 6.0, 6.0), sizing_h="fill", sizing_v="fill")
    doc.create_text("Lbl1", title, p1, font_size=9.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text_dim"])
    bub1 = doc.create_frame("BubMock1", p1, 64.0, 22.0, fill=CONTENT["sheet"], corner_radius=11.0, layout_mode="horizontal", main_align="center", cross_align="center", padding=(2.0, 6.0, 2.0, 6.0), sizing_h="hug", sizing_v="fixed")
    doc.create_text("BTxt1", "なん…", bub1, font_size=9.0, font_family=FONTS["ui"], color=CONTENT["ink"])

    p2 = doc.create_frame("Panel2", top_row, (width - 22.0) * 0.4, (height - 28.0) * 0.55, fill=CONTENT["panel_2"], stroke=C["line_strong"], corner_radius=3.0, layout_mode="vertical", main_align="center", cross_align="center", sizing_h="fixed", sizing_v="fill")
    doc.create_text("Screentone", "/// SPEED ///", p2, font_size=8.0, font_family=FONTS["mono"], color=C["text_dim"])

    p3 = doc.create_frame("Panel3", art, width - 16.0, (height - 28.0) * 0.45, fill=CONTENT["panel_3"], stroke=C["line_strong"], corner_radius=3.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(8.0, 10.0, 8.0, 10.0), sizing_h="fill", sizing_v="fill")
    doc.create_text("ActionText", "BOUKENSHA ACTION SCENE", p3, font_size=9.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text_dim"])
    bub2 = doc.create_frame("BubMock2", p3, 72.0, 22.0, fill=CONTENT["sheet"], corner_radius=11.0, layout_mode="horizontal", main_align="center", cross_align="center", padding=(2.0, 6.0, 2.0, 6.0), sizing_h="hug", sizing_v="fixed")
    doc.create_text("BTxt2", "行くぞ！", bub2, font_size=9.0, font_family=FONTS["ui"], color=CONTENT["ink"])
    return art

def build_full_flow():
    doc = FigcraftDocument("Kuron Studio Master Flow")
    doc.doc["nodes"]["1"]["background"] = hex_to_rgba(C["bg"])
    doc.doc["nodes"]["1"]["name"] = "Kuron Studio — Clean Master Flow"

    # =======================================================================
    # SCREEN 1: 01. DASHBOARD (LIBRARY & PROJECT CARDS)
    # =======================================================================
    sp = screen_spec("dashboard")
    s1 = doc.create_frame(sp["name"], 1, sp["width"], sp["height"], x=sp["x"], y=sp["y"], fill=C["surface"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=16.0, layout_mode="vertical", gap=0.0, clip=True)
    add_window_bar(doc, s1, _DARK["name"] + " — Library")

    # Header
    h1 = doc.create_frame("Header", s1, 1280.0, 48.0, fill=C["surface_2"], stroke=C["line"], layout_mode="horizontal", gap=16.0, padding=(0.0, 24.0, 0.0, 24.0), main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    h1_l = doc.create_frame("Left", h1, 300.0, 32.0, layout_mode="horizontal", gap=10.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.create_rect("Logo", h1_l, 24.0, 24.0, fill=C["coral"], corner_radius=6.0)
    doc.create_text("Brand", "Kuron Studio", h1_l, font_size=14.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.create_text("Sep", "·", h1_l, font_size=12.0, color=C["text_dim"])
    doc.create_text("View", "Library", h1_l, font_size=13.0, font_weight="Medium", color=C["text_muted"])

    h1_r = doc.create_frame("Right", h1, 300.0, 32.0, layout_mode="horizontal", gap=10.0, main_align="max", cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_badge("BdgSync", "3 PROJECTS", h1_r, tone="cyan")
    doc.build_button("BtnNew", "New project", h1_r, variant="primary", size="md")

    # Stats line
    sbar1 = doc.create_frame("StatsLine", s1, 1280.0, 36.0, fill=C["surface"], stroke=C["line"], layout_mode="horizontal", gap=12.0, padding=(0.0, 24.0, 0.0, 24.0), cross_align="center", sizing_h="fill", sizing_v="fixed")
    doc.create_text("StatTxt", "3 projects  ·  41 pages left  ·  2 failed  ·  Model: DeepSeek V3", sbar1, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])

    # Cards area
    carea1 = doc.create_frame("CardsArea", s1, 1280.0, 844.0, fill=C["bg"], layout_mode="vertical", gap=24.0, padding=(28.0, 32.0, 28.0, 32.0), sizing_h="fill", sizing_v="fill")
    doc.create_text("SecTitle", "RECENT PROJECTS", carea1, font_size=12.0, font_weight="Bold", font_family=FONTS["brand"], color=C["coral"])

    crow = doc.create_frame("CardsRow", carea1, 1216.0, 380.0, layout_mode="horizontal", gap=20.0, sizing_h="fill", sizing_v="hug")

    # Card 1: ONIMASA (Active - Quiet, refined 1px border)
    c1 = doc.create_frame("Card_Onimasa", crow, 285.0, 370.0, fill=C["surface_card"], stroke=C["coral"], stroke_width=1.0, corner_radius=12.0, layout_mode="vertical", gap=10.0, padding=(14.0, 14.0, 14.0, 14.0), sizing_h="fixed", sizing_v="fixed")
    add_manga_panel_art(doc, c1, 257.0, 160.0, "ONIMASA #12")
    c1_info = doc.create_frame("Info", c1, 257.0, 64.0, layout_mode="vertical", gap=4.0, sizing_h="fill", sizing_v="hug")
    doc.create_text("T1", "ONIMASA Ch.12", c1_info, font_size=15.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.create_text("Cnt1", "007/182 bubbles · 35%", c1_info, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    doc.create_text("Sub1", "118 todo · 2 failed · 2 min ago", c1_info, font_size=10.0, color=C["text_muted"])
    pbar1 = doc.create_frame("PBar", c1, 257.0, 4.0, fill=C["surface_2"], corner_radius=2.0, sizing_h="fill", sizing_v="fixed")
    doc.create_rect("PFill", pbar1, 257.0 * 0.35, 4.0, fill=C["coral"], corner_radius=2.0)
    c1_act = doc.create_frame("Acts", c1, 257.0, 28.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    doc.build_button("BtnOpen1", "Buka Editor", c1_act, variant="primary", size="sm")
    doc.build_button("BtnLed1", "Ledger (F3)", c1_act, variant="ghost", size="sm")

    # Card 2: Kocak Atelier
    c2 = doc.create_frame("Card_Kocak", crow, 285.0, 370.0, fill=C["surface_card"], stroke=C["line"], corner_radius=12.0, layout_mode="vertical", gap=10.0, padding=(14.0, 14.0, 14.0, 14.0), sizing_h="fixed", sizing_v="fixed")
    add_manga_panel_art(doc, c2, 257.0, 160.0, "KOCAK ATELIER")
    c2_info = doc.create_frame("Info", c2, 257.0, 64.0, layout_mode="vertical", gap=4.0, sizing_h="fill", sizing_v="hug")
    doc.create_text("T2", "Kocak Atelier #04", c2_info, font_size=15.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.create_text("Cnt2", "052/052 bubbles · 100%", c2_info, font_size=11.0, font_family=FONTS["mono"], color=C["success"])
    doc.create_text("Sub2", "0 todo · TM 18 hits · yesterday", c2_info, font_size=10.0, color=C["text_muted"])
    pbar2 = doc.create_frame("PBar", c2, 257.0, 4.0, fill=C["surface_2"], corner_radius=2.0, sizing_h="fill", sizing_v="fixed")
    doc.create_rect("PFill", pbar2, 257.0, 4.0, fill=C["success"], corner_radius=2.0)
    c2_act = doc.create_frame("Acts", c2, 257.0, 28.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    doc.build_button("BtnOpen2", "Buka Editor", c2_act, variant="default", size="sm")
    doc.build_button("BtnCBZ", "Ekspor CBZ", c2_act, variant="default", size="sm")

    # Card 3: Boukensha
    c3 = doc.create_frame("Card_Boukensha", crow, 285.0, 370.0, fill=C["surface_card"], stroke=C["line"], corner_radius=12.0, layout_mode="vertical", gap=10.0, padding=(14.0, 14.0, 14.0, 14.0), sizing_h="fixed", sizing_v="fixed")
    add_manga_panel_art(doc, c3, 257.0, 160.0, "BOUKENSHA CH.8")
    c3_info = doc.create_frame("Info", c3, 257.0, 64.0, layout_mode="vertical", gap=4.0, sizing_h="fill", sizing_v="hug")
    doc.create_text("T3", "BOUKENSHA Ch.08", c3_info, font_size=15.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.create_text("Cnt3", "000/040 bubbles · 0%", c3_info, font_size=11.0, font_family=FONTS["mono"], color=C["warn"])
    doc.create_text("Sub3", "40 todo · Ch8 folder · today", c3_info, font_size=10.0, color=C["text_muted"])
    pbar3 = doc.create_frame("PBar", c3, 257.0, 4.0, fill=C["surface_2"], corner_radius=2.0, sizing_h="fill", sizing_v="fixed")
    doc.create_rect("PFill", pbar3, 257.0 * 0.05, 4.0, fill=C["warn"], corner_radius=2.0)
    c3_act = doc.create_frame("Acts", c3, 257.0, 28.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    doc.build_button("BtnDetect", "Mulai Deteksi", c3_act, variant="primary", size="sm")

    # Card 4: New Project Placeholder
    c4 = doc.create_frame("Card_New", crow, 285.0, 370.0, fill=C["surface"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=12.0, layout_mode="vertical", gap=12.0, padding=(32.0, 24.0, 32.0, 24.0), main_align="center", cross_align="center", sizing_h="fixed", sizing_v="fixed")
    doc.create_rect("PlusIco", c4, 40.0, 40.0, fill=C["surface_2"], stroke=C["line_strong"], corner_radius=20.0)
    doc.create_text("NewTitle", "Buat Project Baru", c4, font_size=14.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.create_text("NewSub", "Import manga folder / ZIP / CBZ", c4, font_size=11.0, color=C["text_muted"])
    doc.build_button("BtnDrop", "Pilih File...", c4, variant="default", size="sm")

    # Activity section below cards
    doc.create_text("ActTitle", "RECENT ACTIVITY LOG", carea1, font_size=12.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text_muted"])
    log_box = doc.create_frame("LogBox", carea1, 1216.0, 96.0, fill=C["surface_card"], stroke=C["line"], corner_radius=8.0, layout_mode="vertical", gap=6.0, padding=(12.0, 16.0, 12.0, 16.0), sizing_h="fill", sizing_v="hug")
    doc.create_text("L1", "[14:22] ONIMASA Ch.12: Batch detection of 14 pages finished (DeepSeek OCR v3 · 99.4% confidence)", log_box, font_size=11.0, font_family=FONTS["mono"], color=C["success"])
    doc.create_text("L2", "[11:05] Kocak Atelier #04: Print-ready CBZ export created (52 pages)", log_box, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    doc.create_text("L3", "[09:40] ONIMASA Ch.12 (p011.jpg): 2 balon kata memerlukan verifikasi manual (overflow fit 118%)", log_box, font_size=11.0, font_family=FONTS["mono"], color=C["warn"])

    doc.create_text("Hint1", "Enter to open the selected project  ·  ⌘N to import a chapter  ·  AI settings in Preferences", carea1, font_size=11.0, color=C["text_dim"])

    resolve_tree_layout(doc.doc["nodes"], s1)

    # =======================================================================
    # SCREEN 2: 02. PAGE GRID & PIPELINE
    # =======================================================================
    sp = screen_spec("grid")
    s2 = doc.create_frame(sp["name"], 1, sp["width"], sp["height"], x=sp["x"], y=sp["y"], fill=C["surface"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=16.0, layout_mode="vertical", gap=0.0, clip=True)
    add_window_bar(doc, s2, "Kuron Studio — ONIMASA Ch.12 (Pipeline Grid)")

    # Header
    h2 = doc.create_frame("Header", s2, 1280.0, 48.0, fill=C["surface_2"], stroke=C["line"], layout_mode="horizontal", gap=16.0, padding=(0.0, 20.0, 0.0, 20.0), main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    h2_l = doc.create_frame("Left", h2, 400.0, 32.0, layout_mode="horizontal", gap=12.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.create_rect("Logo2", h2_l, 24.0, 24.0, fill=C["coral"], corner_radius=6.0)
    dtrig = doc.create_frame("DropTrig", h2_l, 170.0, 32.0, fill=C["surface_card"], stroke=C["line_strong"], corner_radius=6.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 10.0, 0.0, 10.0), sizing_h="hug", sizing_v="fixed")
    doc.create_text("DVal", "Document 12 ▾", dtrig, font_size=12.0, font_weight="SemiBold", color=C["text"])
    doc.create_text("Counter2", "007/182", h2_l, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    doc.create_text("LangPill2", "JA → ID", h2_l, font_size=11.0, color=C["text_muted"])

    h2_r = doc.create_frame("Right", h2, 400.0, 32.0, layout_mode="horizontal", gap=8.0, main_align="max", cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_button("BtnSearch", "⌘K Search", h2_r, variant="default", size="sm")
    doc.build_button("BtnReview", "Tinjau Ledger (F3)", h2_r, variant="default", size="sm")
    doc.build_button("BtnTransAll", "Translate remaining 118", h2_r, variant="primary", size="sm")

    # 5-Stage Pipeline Stepper Bar
    pipe_bar = doc.create_frame("PipelineBar", s2, 1280.0, 44.0, fill=C["surface"], stroke=C["line"], layout_mode="horizontal", gap=16.0, padding=(0.0, 24.0, 0.0, 24.0), main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    pipe_stages = doc.create_frame("Stages", pipe_bar, 800.0, 32.0, layout_mode="horizontal", gap=10.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
    
    stages_data = [
        ("1. Import 182", C["success"], True),
        ("2. Detect 164", C["success"], True),
        ("3. Translate 064", C["coral"], True),
        ("4. Review 012", C["text_dim"], False),
        ("5. Export", C["text_dim"], False)
    ]
    for idx, (st_label, st_col, is_done) in enumerate(stages_data):
        if idx > 0:
            doc.create_text(f"Arr_{idx}", "→", pipe_stages, font_size=11.0, color=C["line_strong"])
        st_box = doc.create_frame(f"St_{idx}", pipe_stages, 110.0, 26.0, fill=C["coral_subtle"] if st_col == C["coral"] else None, stroke=None, corner_radius=4.0, layout_mode="horizontal", gap=6.0, cross_align="center", padding=(0.0, 8.0, 0.0, 8.0), sizing_h="hug", sizing_v="fixed")
        doc.create_ellipse(f"dot_{idx}", st_box, 6.0, st_col)
        doc.create_text(f"lbl_{idx}", st_label, st_box, font_size=11.0, font_weight="Bold" if is_done else "Regular", font_family=FONTS["mono"], color=st_col)

    doc.build_badge("BdgProgress2", "64/182 SELESAI", pipe_bar, tone="cyan")

    # 4-Column Page Grid
    grid_content = doc.create_frame("GridContent", s2, 1280.0, 836.0, fill=C["bg"], layout_mode="vertical", gap=14.0, padding=(20.0, 24.0, 20.0, 24.0), sizing_h="fill", sizing_v="fill")
    p_row1 = doc.create_frame("PagesRow1", grid_content, 1232.0, 260.0, layout_mode="horizontal", gap=16.0, sizing_h="fill", sizing_v="fixed")

    pages_row1 = [
        ("p001.jpg", 6, "Done", C["success"], False, "TM Hit (6/6)"),
        ("p002.jpg", 4, "Done", C["success"], False, "AI DeepSeek"),
        ("p003.jpg", 8, "Done", C["success"], False, "AI DeepSeek"),
        ("p004.jpg", 5, "Translating", C["coral"], True, "Batch process"),
    ]
    for fn, b_count, st_name, st_col, is_sel, note in pages_row1:
        p_card = doc.create_frame(f"Card_{fn}", p_row1, 296.0, 260.0, fill=C["surface_card"], stroke=C["coral"] if is_sel else C["line"], stroke_width=1.0, corner_radius=10.0, layout_mode="vertical", gap=6.0, padding=(10.0, 10.0, 10.0, 10.0), sizing_h="fixed", sizing_v="fixed")
        add_manga_panel_art(doc, p_card, 276.0, 180.0, f"HALAMAN {fn}")
        p_ft = doc.create_frame(f"Meta_{fn}", p_card, 276.0, 28.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
        doc.create_text(f"Fn_{fn}", fn, p_ft, font_size=12.0, font_weight="Bold", font_family=FONTS["mono"], color=C["text"])
        doc.build_badge(f"BdgCount_{fn}", f"{b_count} BALON", p_ft, tone="cyan")
        doc.build_badge(f"StBdg_{fn}", st_name.upper(), p_ft, tone="coral" if is_sel else "ok")

    # Row 2 (Optimisation Issue #67: 0-bubble skip & TM cache)
    p_row2 = doc.create_frame("PagesRow2", grid_content, 1232.0, 240.0, layout_mode="horizontal", gap=16.0, sizing_h="fill", sizing_v="fixed")
    pages_row2 = [
        ("p005.jpg", 0, "0 bubbles (skipped)", C["text_dim"], False, "Quota saved #67"),
        ("p006.jpg", 11, "TM Cache (0 Req)", C["cyan"], False, "100% TM Hit #67"),
        ("p007.jpg", 7, "AI queue", C["warn"], False, "Waiting for turn"),
        ("p008.jpg", 3, "AI queue", C["warn"], False, "Waiting for turn"),
    ]
    for fn, b_count, st_name, st_col, is_sel, note in pages_row2:
        p_card = doc.create_frame(f"Card_{fn}", p_row2, 296.0, 240.0, fill=C["surface_card"], stroke=C["line"], stroke_width=1.0, corner_radius=10.0, layout_mode="vertical", gap=6.0, padding=(10.0, 10.0, 10.0, 10.0), sizing_h="fixed", sizing_v="fixed")
        add_manga_panel_art(doc, p_card, 276.0, 160.0, f"HALAMAN {fn}")
        p_ft = doc.create_frame(f"Meta_{fn}", p_card, 276.0, 28.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
        doc.create_text(f"Fn_{fn}", fn, p_ft, font_size=12.0, font_weight="Bold", font_family=FONTS["mono"], color=C["text"])
        doc.build_badge(f"BdgCount_{fn}", f"{b_count} BALON" if b_count > 0 else "KOSONG", p_ft, tone="cyan" if b_count > 0 else "neutral")
        doc.build_badge(f"StBdg_{fn}", st_name.upper(), p_ft, tone="neutral" if b_count == 0 else ("cyan" if "TM" in st_name else "warn"))

    # Row 3 (Dense Manga Grid - No empty black void!)
    p_row3 = doc.create_frame("PagesRow3", grid_content, 1232.0, 240.0, layout_mode="horizontal", gap=16.0, sizing_h="fill", sizing_v="fixed")
    pages_row3 = [
        ("p009.jpg", 9, "Done", C["success"], False, "AI DeepSeek"),
        ("p010.jpg", 4, "Done", C["success"], False, "AI DeepSeek"),
        ("p011.jpg", 2, "Needs review (118%)", C["warn"], False, "Overflow fit"),
        ("p012.jpg", 6, "Done", C["success"], False, "AI DeepSeek"),
    ]
    for fn, b_count, st_name, st_col, is_sel, note in pages_row3:
        p_card = doc.create_frame(f"Card_{fn}", p_row3, 296.0, 240.0, fill=C["surface_card"], stroke=C["line"], stroke_width=1.0, corner_radius=10.0, layout_mode="vertical", gap=6.0, padding=(10.0, 10.0, 10.0, 10.0), sizing_h="fixed", sizing_v="fixed")
        add_manga_panel_art(doc, p_card, 276.0, 160.0, f"HALAMAN {fn}")
        p_ft = doc.create_frame(f"Meta_{fn}", p_card, 276.0, 28.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
        doc.create_text(f"Fn_{fn}", fn, p_ft, font_size=12.0, font_weight="Bold", font_family=FONTS["mono"], color=C["text"])
        doc.build_badge(f"BdgCount_{fn}", f"{b_count} BALON", p_ft, tone="cyan")
        doc.build_badge(f"StBdg_{fn}", st_name.upper(), p_ft, tone="warn" if "review" in st_name.lower() else "ok")

    # Bottom floating action dock (Subtle monochrome border, high-end quiet workbench)
    dock = doc.create_frame("ActionDock", grid_content, 1232.0, 52.0, fill=C["surface_raised"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=8.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 20.0, 0.0, 20.0), sizing_h="fill", sizing_v="fixed")
    dock_l = doc.create_frame("DockL", dock, 500.0, 32.0, layout_mode="horizontal", gap=10.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.create_ellipse("seldot", dock_l, 8.0, C["coral"])
    doc.create_text("DockTxt", "1 page selected (p004.jpg) · 5 bubbles detected", dock_l, font_size=12.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    
    dock_r = doc.create_frame("DockR", dock, 420.0, 32.0, layout_mode="horizontal", gap=10.0, main_align="max", cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_button("BtnRedetect", "Re-detect", dock_r, variant="default", size="sm")
    doc.build_button("BtnGoEdit", "Buka di Editor (Enter)", dock_r, variant="primary", size="sm")

    resolve_tree_layout(doc.doc["nodes"], s2)

    # =======================================================================
    # SCREEN 3: 03. TRANSLATION WORKBENCH (3-COLUMN WORKSPACE EDITOR)
    # =======================================================================
    sp = screen_spec("editor")
    s3 = doc.create_frame(sp["name"], 1, sp["width"], sp["height"], x=sp["x"], y=sp["y"], fill=C["surface"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=16.0, layout_mode="vertical", gap=0.0, clip=True)
    add_window_bar(doc, s3, "Kuron Studio — ONIMASA Ch.12 (p004.jpg)")

    # Slim Toolbar
    h3 = doc.create_frame("Toolbar", s3, 1280.0, 44.0, fill=C["surface_2"], stroke=C["line"], layout_mode="horizontal", gap=16.0, padding=(0.0, 16.0, 0.0, 16.0), main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    h3_l = doc.create_frame("TL", h3, 450.0, 32.0, layout_mode="horizontal", gap=10.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_button("BtnBack", "← Grid", h3_l, variant="ghost", size="sm")
    doc.create_text("CurPg", "Page 04 / 41", h3_l, font_size=12.0, font_weight="Bold", font_family=FONTS["mono"], color=C["text"])
    doc.build_badge("BdgBubbles3", "5 BALON", h3_l, tone="cyan")
    doc.create_text("ModelTag", "DeepSeek V3 OCR", h3_l, font_size=11.0, font_family=FONTS["mono"], color=C["text_dim"])

    h3_c = doc.create_frame("TC", h3, 180.0, 32.0, layout_mode="horizontal", gap=6.0, main_align="center", cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_button("ZmOut", "−", h3_c, variant="ghost", size="sm")
    doc.create_text("ZmLbl", "100%", h3_c, font_size=11.0, font_family=FONTS["mono"], color=C["text"])
    doc.build_button("ZmIn", "+", h3_c, variant="ghost", size="sm")

    h3_r = doc.create_frame("TR", h3, 420.0, 32.0, layout_mode="horizontal", gap=10.0, main_align="max", cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_button("BtnRedet", "Re-detect", h3_r, variant="default", size="sm")
    doc.build_button("BtnSavePg", "Save translation (Enter)", h3_r, variant="primary", size="sm")

    # 3-Column Body: Rail 196px | Canvas 1fr | Inspector 310px
    body3 = doc.create_frame("WorkbenchBody", s3, 1280.0, 884.0, layout_mode="horizontal", gap=0.0, sizing_h="fill", sizing_v="fill")

    # COLUMN 1: LEFT RAIL (196px)
    rail = doc.create_frame("LeftRail", body3, 196.0, 884.0, fill=C["surface_2"], stroke=C["line"], layout_mode="vertical", gap=8.0, padding=(12.0, 10.0, 12.0, 10.0), sizing_h="fixed", sizing_v="fill")
    rail_h = doc.create_frame("RH", rail, 176.0, 24.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
    doc.create_text("PagesH", "PAGES", rail_h, font_size=11.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text_muted"])
    doc.create_text("TotPages", "41", rail_h, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])

    page_items = [
        ("p001.jpg", "6 balon", C["success"], False),
        ("p002.jpg", "4 balon", C["success"], False),
        ("p003.jpg", "8 balon", C["success"], False),
        ("p004.jpg", "5 balon · AKTIF", C["coral"], True),
        ("p005.jpg", "3 balon", C["text_dim"], False),
        ("p006.jpg", "5 balon", C["text_dim"], False),
        ("p007.jpg", "2 failed", C["danger"], False),
    ]
    for p_fn, p_desc, p_col, is_p_active in page_items:
        p_row_card = doc.create_frame(f"PItem_{p_fn}", rail, 176.0, 36.0, fill=C["surface_card"] if is_p_active else None, stroke=C["line_strong"] if is_p_active else None, corner_radius=6.0, layout_mode="horizontal", gap=8.0, cross_align="center", padding=(0.0, 8.0, 0.0, 8.0), sizing_h="fill", sizing_v="fixed")
        doc.create_ellipse(f"pdot_{p_fn}", p_row_card, 6.0, p_col)
        p_txts = doc.create_frame("PTxts", p_row_card, 130.0, 28.0, layout_mode="vertical", gap=1.0, sizing_h="fill", sizing_v="hug")
        doc.create_text("PFn", p_fn, p_txts, font_size=11.0, font_weight="Bold" if is_p_active else "Regular", font_family=FONTS["mono"], color=C["text"] if is_p_active else C["text_muted"])
        doc.create_text("PDesc", p_desc, p_txts, font_size=9.0, color=p_col if is_p_active else C["text_dim"])

    doc.create_rect("DivRail", rail, 176.0, 1.0, fill=C["line"])
    doc.build_button("BtnGlossary", "Glossary (G)", rail, variant="default", size="sm")
    doc.build_button("BtnProvider", "Providers (P)", rail, variant="default", size="sm")
    doc.build_button("BtnDiag", "Diagnostics (D)", rail, variant="default", size="sm")

    # COLUMN 2: CENTER CANVAS (1fr / 774px)
    center_canvas = doc.create_frame("CenterCanvas", body3, 774.0, 884.0, fill=C["bg"], layout_mode="vertical", main_align="center", cross_align="center", padding=(20.0, 20.0, 20.0, 20.0), sizing_h="fill", sizing_v="fill")
    
    manga_sheet = doc.create_frame("MangaPageSheet", center_canvas, 520.0, 740.0, fill=CONTENT["sheet"], stroke=C["surface_card"], stroke_width=2.0, corner_radius=4.0, layout_mode="vertical", gap=12.0, padding=(16.0, 16.0, 16.0, 16.0), sizing_h="fixed", sizing_v="fixed")
    
    mp_top = doc.create_frame("TopPanel", manga_sheet, 488.0, 240.0, fill=CONTENT["sheet_panel_1"], stroke=CONTENT["ink_art"], stroke_width=2.0, corner_radius=2.0, layout_mode="horizontal", main_align="spaceBetween", padding=(12.0, 12.0, 12.0, 12.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("MangaArtTitle", "ONIMASA — CHAPTER 12 PAGE 04", mp_top, font_size=10.0, font_weight="Bold", font_family=FONTS["brand"], color=CONTENT["ink_muted_1"])
    
    bub_1 = doc.create_frame("Bubble_1", mp_top, 110.0, 50.0, fill=CONTENT["sheet"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=25.0, layout_mode="vertical", main_align="center", cross_align="center", padding=(2.0, 6.0, 2.0, 6.0), sizing_h="fixed", sizing_v="fixed")
    doc.create_text("B1Text", "やれやれ…", bub_1, font_size=12.0, font_weight="Bold", color=CONTENT["ink"])

    mp_mid = doc.create_frame("MidPanel", manga_sheet, 488.0, 280.0, fill=CONTENT["sheet_panel_2"], stroke=CONTENT["ink_art"], stroke_width=2.0, corner_radius=2.0, layout_mode="vertical", main_align="center", cross_align="center", padding=(16.0, 16.0, 16.0, 16.0), sizing_h="fill", sizing_v="fixed")
    
    # ACTIVE BUBBLE #2 (Refined 1.5px coral border)
    bub_2_active = doc.create_frame("ActiveBubble_2", mp_mid, 220.0, 100.0, fill=CONTENT["sheet"], stroke=C["coral"], stroke_width=1.5, corner_radius=16.0, layout_mode="vertical", main_align="spaceBetween", padding=(8.0, 10.0, 8.0, 10.0), sizing_h="fixed", sizing_v="fixed")
    b2_hdr = doc.create_frame("B2Hdr", bub_2_active, 200.0, 20.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
    doc.build_badge("BdgB2", "#2 AKTIF", b2_hdr, tone="cyan")
    doc.create_text("Coords", "[X:142 Y:280]", b2_hdr, font_size=9.0, font_family=FONTS["mono"], color=C["coral"])
    doc.create_text("B2Text", "なんだって…！", bub_2_active, font_size=16.0, font_weight="Bold", color=CONTENT["ink"])
    doc.create_text("B2Sub", "Apa-apaan…!", bub_2_active, font_size=11.0, color=CONTENT["ink_muted_2"])

    mp_btm = doc.create_frame("BtmPanel", manga_sheet, 488.0, 160.0, fill=CONTENT["sheet_panel_1"], stroke=CONTENT["ink_art"], stroke_width=2.0, corner_radius=2.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(12.0, 12.0, 12.0, 12.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("ActionSFX", "DONNNN! (DOKIDOKI)", mp_btm, font_size=14.0, font_weight="Bold", font_family=FONTS["brand"], color=CONTENT["ink_muted_3"])
    bub_3 = doc.create_frame("Bubble_3", mp_btm, 120.0, 60.0, fill=CONTENT["sheet"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=30.0, layout_mode="vertical", main_align="center", cross_align="center", padding=(2.0, 6.0, 2.0, 6.0), sizing_h="fixed", sizing_v="fixed")
    doc.create_text("B3Text", "逃げろ！", bub_3, font_size=13.0, font_weight="Bold", color=CONTENT["ink"])

    hud = doc.create_frame("CanvasHUD", center_canvas, 420.0, 32.0, fill=C["surface_2"], stroke=C["line"], corner_radius=16.0, layout_mode="horizontal", gap=12.0, main_align="center", cross_align="center", padding=(0.0, 16.0, 0.0, 16.0), sizing_h="hug", sizing_v="fixed")
    doc.create_text("H1", "Zoom 100%", hud, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    doc.create_text("HDot", "·", hud, font_size=11.0, color=C["line_strong"])
    doc.create_text("H2", "5 Balon Terdeteksi", hud, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    doc.create_text("HDot2", "·", hud, font_size=11.0, color=C["line_strong"])
    doc.create_text("H3", "RTL mode active", hud, font_size=11.0, color=C["text_muted"])

    # COLUMN 3: RIGHT INSPECTOR (310px - Quiet monochrome card border)
    insp = doc.create_frame("Inspector", body3, 310.0, 884.0, fill=C["surface_2"], stroke=C["line"], layout_mode="vertical", gap=12.0, padding=(14.0, 14.0, 14.0, 14.0), sizing_h="fixed", sizing_v="fill")
    
    insp_hdr = doc.create_frame("InspHdr", insp, 282.0, 24.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
    doc.create_text("InspTitle", "INSPEKTOR BALON", insp_hdr, font_size=12.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.create_text("InspStep", "2 / 5", insp_hdr, font_size=12.0, font_family=FONTS["mono"], color=C["text_muted"])

    bcard = doc.create_frame("ActiveBubbleCard", insp, 282.0, 370.0, fill=C["surface_card"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=8.0, layout_mode="vertical", gap=10.0, padding=(12.0, 12.0, 12.0, 12.0), sizing_h="fill", sizing_v="hug")
    
    bcard_top = doc.create_frame("BCTop", bcard, 258.0, 20.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
    doc.create_text("B2Id", "#2 · hlm 004", bcard_top, font_size=11.0, font_weight="Bold", font_family=FONTS["mono"], color=C["text"])
    doc.build_badge("BdgActive", "ACTIVE", bcard_top, tone="cyan")

    doc.create_text("LblAsli", "Teks Asli (Jepang)", bcard, font_size=10.0, font_weight="SemiBold", color=C["text_dim"])
    box_asli = doc.create_frame("BoxAsli", bcard, 258.0, 36.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", cross_align="center", padding=(0.0, 10.0, 0.0, 10.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("ValAsli", "なんだって…", box_asli, font_size=14.0, font_weight="Bold", color=C["text"])

    doc.create_text("ValRomaji", "nandatte…", bcard, font_size=11.0, color=C["text_muted"])

    doc.create_text("LblHasil", "Translation result (English)", bcard, font_size=10.0, font_weight="SemiBold", color=C["coral"])
    box_hasil = doc.create_frame("BoxHasil", bcard, 258.0, 40.0, fill=C["surface_2"], stroke=C["coral"], stroke_width=1.0, corner_radius=6.0, layout_mode="horizontal", cross_align="center", padding=(0.0, 10.0, 0.0, 10.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("ValHasil", "What is this…", box_hasil, font_size=14.0, font_weight="Medium", color=C["text"])

    doc.create_text("LblFit", "Kepadatan Teks & Ukuran Font", bcard, font_size=10.0, font_weight="SemiBold", color=C["text_dim"])
    fit_row = doc.create_frame("FitRow", bcard, 258.0, 20.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
    doc.create_text("FitStatus", "Fit (optimal)", fit_row, font_size=11.0, font_weight="Bold", color=C["success"])
    doc.create_text("FitVal", "9/12 huruf · 74%", fit_row, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    
    fit_bar = doc.create_frame("FitBarTrack", bcard, 258.0, 6.0, fill=C["surface_2"], corner_radius=3.0, sizing_h="fill", sizing_v="fixed")
    doc.create_rect("FitFill", fit_bar, 258.0 * 0.74, 6.0, fill=C["success"], corner_radius=3.0)

    doc.create_text("LblTypo", "Font and text style", bcard, font_size=10.0, font_weight="SemiBold", color=C["text_dim"])
    typo_row = doc.create_frame("TypoRow", bcard, 258.0, 32.0, layout_mode="horizontal", gap=8.0, sizing_h="fill", sizing_v="fixed")
    font_sel = doc.create_frame("FontSel", typo_row, 170.0, 32.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 8.0, 0.0, 8.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("FontName", "CC Wild Words ▾", font_sel, font_size=11.0, color=C["text"])
    size_box = doc.create_frame("SizeBox", typo_row, 80.0, 32.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", main_align="center", cross_align="center", sizing_h="fixed", sizing_v="fixed")
    doc.create_text("SizeVal", "18px", size_box, font_size=11.0, font_family=FONTS["mono"], color=C["text"])

    c_next = doc.create_frame("NextBubbleCard", insp, 282.0, 64.0, fill=C["surface_card"], stroke=C["line"], corner_radius=6.0, layout_mode="vertical", gap=4.0, padding=(8.0, 10.0, 8.0, 10.0), sizing_h="fill", sizing_v="hug")
    doc.create_text("NxtHdr", "#3 · Needs review (tight 104%)", c_next, font_size=10.0, font_weight="Bold", color=C["warn"])
    doc.create_text("NxtTxt", "これは嘘だ → Ini bohong...", c_next, font_size=11.0, color=C["text_muted"])

    # Bottom inspector actions
    insp_acts = doc.create_frame("InspActs", insp, 282.0, 76.0, layout_mode="vertical", gap=8.0, sizing_h="fill", sizing_v="hug")
    doc.build_button("BtnRetranslate", "Re-translate (⌘R)", insp_acts, variant="default", size="sm")
    doc.build_button("BtnApplyNext", "Terapkan & Lanjut (⌘Enter)", insp_acts, variant="primary", size="md")

    resolve_tree_layout(doc.doc["nodes"], s3)

    # =======================================================================
    # SCREEN 4: 04. BUBBLE LEDGER (REVIEW DATA TABLE WITH CELL FRAMES)
    # =======================================================================
    sp = screen_spec("ledger")
    s4 = doc.create_frame(sp["name"], 1, sp["width"], sp["height"], x=sp["x"], y=sp["y"], fill=C["surface"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=16.0, layout_mode="vertical", gap=0.0, clip=True)
    add_window_bar(doc, s4, "Kuron Studio — Ledger Review Balon Kata")

    # Header
    h4 = doc.create_frame("Header", s4, 1280.0, 48.0, fill=C["surface_2"], stroke=C["line"], layout_mode="horizontal", gap=16.0, padding=(0.0, 24.0, 0.0, 24.0), main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    h4_l = doc.create_frame("Left", h4, 520.0, 32.0, layout_mode="horizontal", gap=10.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.create_text("LTitle", "Ledger Review Balon Kata", h4_l, font_size=14.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.create_text("LSub", "·  182 total  ·  162 lolos  ·  18 perlu cek  ·  2 overflow", h4_l, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])

    h4_r = doc.create_frame("Right", h4, 400.0, 32.0, layout_mode="horizontal", gap=8.0, main_align="max", cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_button("BtnExportCSV", "Export CSV", h4_r, variant="default", size="sm")
    doc.build_button("BtnApproveAll", "Approve all (162)", h4_r, variant="primary", size="sm")

    # Toolbar
    tb4 = doc.create_frame("Toolbar", s4, 1280.0, 44.0, fill=C["surface"], stroke=C["line"], layout_mode="horizontal", gap=16.0, padding=(0.0, 24.0, 0.0, 24.0), main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    sbox = doc.create_frame("SearchBox", tb4, 340.0, 32.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", cross_align="center", padding=(0.0, 12.0, 0.0, 12.0), sizing_h="fixed", sizing_v="fixed")
    doc.create_text("STxt", "Search source or translated text... (⌘F)", sbox, font_size=11.0, color=C["text_dim"])

    filters = doc.create_frame("FilterSeg", tb4, 450.0, 32.0, layout_mode="horizontal", gap=6.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_button("FAll", "All (182)", filters, variant="default", size="sm")
    doc.build_button("FRev", "Needs review (18)", filters, variant="primary", size="sm")
    doc.build_button("FOver", "Overflow (2)", filters, variant="default", size="sm")
    doc.build_button("FDone", "Lolos (162)", filters, variant="default", size="sm")

    # Table Container
    t_container = doc.create_frame("TableContainer", s4, 1280.0, 836.0, fill=C["bg"], layout_mode="vertical", gap=1.0, padding=(20.0, 24.0, 20.0, 24.0), sizing_h="fill", sizing_v="fill")
    
    # Table Header Row with CELL FRAMES for 100% alignment!
    th_row = doc.create_frame("TableHeader", t_container, 1232.0, 32.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", cross_align="center", padding=(0.0, 14.0, 0.0, 14.0), sizing_h="fill", sizing_v="fixed")
    
    cols = [
        ("C_ID", 45.0, "#", True),
        ("C_PG", 55.0, "HLM", True),
        ("C_ORIG", 220.0, "ASLI (JEPANG)", False),
        ("C_TRANS", 320.0, "TERJEMAHAN (INDONESIA)", False),
        ("C_FIT", 130.0, "FIT / KAPASITAS", False),
        ("C_CONF", 120.0, "CONFIDENCE", True),
        ("C_STAT", 110.0, "STATUS", False),
        ("C_ACT", 80.0, "AKSI", False),
    ]
    for cid, cw, clbl, is_m in cols:
        cell = doc.create_frame(f"TH_{cid}", th_row, cw, 24.0, layout_mode="horizontal", cross_align="center", sizing_h="fixed", sizing_v="fixed")
        doc.create_text(f"Txt_{cid}", clbl, cell, font_size=10.0, font_weight="Bold", font_family=FONTS["mono"] if is_m else FONTS["brand"], color=C["text_dim"])

    # 8 Dense Rows with CELL FRAMES & List Row States (Issue #84)
    # State types: idle, hover, keyboard_cursor, active_persistent
    ledger_rows = [
        ("01", "p001", "やれやれ、またか", "Oh no, not again...", "92% (fit)", C["success"], "99.2%", "PASSED", "ok", "idle"),
        ("02", "p001", "待ちなさい！", "Wait a moment!", "85% (fit)", C["success"], "98.5%", "PASSED", "ok", "hover"),
        ("03", "p002", "逃げられると思うなよ", "Don't think you can run!", "118% (tight)", C["danger"], "94.0%", "OVERFLOW", "danger", "idle"),
        ("04", "p002", "何者だ…？", "Who are you really...?", "78% (fit)", C["success"], "99.1%", "PASSED", "ok", "cursor"),
        ("05", "p003", "力を貸してくれ", "Help me finish this", "60% (fit)", C["success"], "97.4%", "PASSED", "ok", "idle"),
        ("06", "p004", "なんだって…", "What is this…", "74% (fit)", C["text_muted"], "99.4%", "ACTIVE", "coral", "active"),
        ("07", "p004", "これは嘘だ、信じない", "Ini bohong, aku tak percaya", "104% (Ketat)", C["warn"], "91.2%", "REVIEW", "warn", "idle"),
        ("08", "p004", "もう遅いんだ", "It is all too late", "80% (fit)", C["success"], "98.9%", "PASSED", "ok", "idle"),
    ]

    for r_id, r_pg, r_orig, r_trans, r_fit, r_fit_col, r_conf, r_st, r_tone, r_state in ledger_rows:
        # Determine fill & stroke based on Issue #84 list row rules (Monochrome quiet workbench)
        if r_state == "active":
            row_fill = C["row_active"]
            row_stroke = C["coral"]
            row_stroke_w = 1.0
        elif r_state == "cursor":
            row_fill = C["row_hover"]
            row_stroke = C["line_strong"]
            row_stroke_w = 1.0
        elif r_state == "hover":
            row_fill = C["row_hover"]
            row_stroke = C["line"]
            row_stroke_w = 1.0
        else: # idle
            row_fill = C["surface"]
            row_stroke = C["line"]
            row_stroke_w = 1.0

        row = doc.create_frame(f"Row_{r_id}", t_container, 1232.0, 42.0, fill=row_fill, stroke=row_stroke, stroke_width=row_stroke_w, corner_radius=4.0, layout_mode="horizontal", cross_align="center", padding=(0.0, 14.0, 0.0, 14.0), sizing_h="fill", sizing_v="fixed")
        
        # Cell 1: ID
        c_1 = doc.create_frame(f"C1_{r_id}", row, 45.0, 24.0, layout_mode="horizontal", cross_align="center", sizing_h="fixed", sizing_v="fixed")
        doc.create_text(f"ID_{r_id}", f"#{r_id}", c_1, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
        
        # Cell 2: Page
        c_2 = doc.create_frame(f"C2_{r_id}", row, 55.0, 24.0, layout_mode="horizontal", cross_align="center", sizing_h="fixed", sizing_v="fixed")
        doc.create_text(f"PG_{r_id}", r_pg, c_2, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])

        # Cell 3: Original JP
        c_3 = doc.create_frame(f"C3_{r_id}", row, 220.0, 24.0, layout_mode="horizontal", cross_align="center", sizing_h="fixed", sizing_v="fixed")
        doc.create_text(f"OR_{r_id}", r_orig, c_3, font_size=13.0, font_weight="Bold", color=C["text"])

        # Cell 4: Translation ID
        c_4 = doc.create_frame(f"C4_{r_id}", row, 320.0, 24.0, layout_mode="horizontal", cross_align="center", sizing_h="fixed", sizing_v="fixed")
        doc.create_text(f"TR_{r_id}", r_trans, c_4, font_size=12.0, color=C["text"])

        # Cell 5: Fit
        c_5 = doc.create_frame(f"C5_{r_id}", row, 130.0, 24.0, layout_mode="horizontal", cross_align="center", sizing_h="fixed", sizing_v="fixed")
        doc.create_text(f"FT_{r_id}", r_fit, c_5, font_size=11.0, font_family=FONTS["mono"], color=r_fit_col)

        # Cell 6: Confidence
        c_6 = doc.create_frame(f"C6_{r_id}", row, 120.0, 24.0, layout_mode="horizontal", cross_align="center", sizing_h="fixed", sizing_v="fixed")
        doc.create_text(f"CF_{r_id}", r_conf, c_6, font_size=11.0, font_family=FONTS["mono"], color=C["text_dim"])

        # Cell 7: Status Badge
        c_7 = doc.create_frame(f"C7_{r_id}", row, 110.0, 24.0, layout_mode="horizontal", cross_align="center", sizing_h="fixed", sizing_v="fixed")
        doc.build_badge(f"BD_{r_id}", r_st, c_7, tone=r_tone)

        # Cell 8: Action
        c_8 = doc.create_frame(f"C8_{r_id}", row, 80.0, 24.0, layout_mode="horizontal", cross_align="center", sizing_h="fixed", sizing_v="fixed")
        doc.build_button(f"BT_{r_id}", "Edit", c_8, variant="ghost", size="sm")

    # Table Footer Pagination
    t_foot = doc.create_frame("TFoot", t_container, 1232.0, 40.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 16.0, 0.0, 16.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("TFInfo", "Showing 1-8 of 182 bubbles", t_foot, font_size=11.0, font_family=FONTS["mono"], color=C["text_dim"])
    
    pag = doc.create_frame("PagControls", t_foot, 220.0, 28.0, layout_mode="horizontal", gap=6.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_button("PPrev", "< Prev", pag, variant="ghost", size="sm")
    doc.build_badge("PPage", "1 / 23", pag, tone="cyan")
    doc.build_button("PNext", "Next >", pag, variant="ghost", size="sm")

    resolve_tree_layout(doc.doc["nodes"], s4)

    # =======================================================================
    # SCREEN 5: 05. EXPORT MODAL FLOW (FINAL DELIVERY & PACKAGING)
    # =======================================================================
    sp = screen_spec("export")
    s5 = doc.create_frame(sp["name"], 1, sp["width"], sp["height"], x=sp["x"], y=sp["y"], fill=C["surface"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=16.0, layout_mode="none", clip=True)
    
    # 1. Render realistic Kuron Studio workbench grid in the background
    add_dimmed_app_background(doc, s5, _DARK["name"] + " — Chapter 12 (print ready)")

    # 2. Translucent Dimmed Backdrop Overlay (Level 3 Floating Modal Pattern)
    overlay5 = doc.create_frame("DimOverlay5", s5, 1280.0, 960.0, x=0.0, y=0.0, fill=CONTENT["scrim_overlay"], layout_mode="vertical", main_align="center", cross_align="center", sizing_h="fixed", sizing_v="fixed")

    # 3. 680px wide modal dialog centered over dimmed app grid
    modal = doc.create_frame("ExportModalWindow", overlay5, 680.0, 720.0, fill=C["surface_raised"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=16.0, layout_mode="vertical", gap=16.0, padding=(24.0, 28.0, 24.0, 28.0), sizing_h="fixed", sizing_v="fixed")
    
    m_hdr = doc.create_frame("MHdr", modal, 624.0, 32.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
    doc.create_text("MTitle", "Print-ready export and release", m_hdr, font_size=16.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.build_button("MClose", "✕", m_hdr, variant="ghost", size="sm")

    doc.create_text("MSub", "Choose an export format for the translated manga pages.", modal, font_size=12.0, color=C["text_muted"])

    f_grid = doc.create_frame("FormatGrid", modal, 624.0, 190.0, layout_mode="vertical", gap=10.0, sizing_h="fill", sizing_v="hug")
    
    opt1 = doc.create_frame("Opt_PDF", f_grid, 624.0, 56.0, fill=C["surface_card"], stroke=C["coral"], stroke_width=1.0, corner_radius=8.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 16.0, 0.0, 16.0), sizing_h="fill", sizing_v="fixed")
    o1_l = doc.create_frame("O1L", opt1, 460.0, 40.0, layout_mode="vertical", gap=2.0, sizing_h="fill", sizing_v="hug")
    doc.create_text("O1T", "Print-ready PDF (3mm bleed + CMYK)", o1_l, font_size=13.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.create_text("O1D", "Physical print standard, vector text layer, 3mm crop marks", o1_l, font_size=10.0, color=C["text_muted"])
    doc.build_badge("BdgRec", "REKOMENDASI", opt1, tone="coral")

    opt2 = doc.create_frame("Opt_CBZ", f_grid, 624.0, 56.0, fill=C["surface_2"], stroke=C["line"], corner_radius=8.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 16.0, 0.0, 16.0), sizing_h="fill", sizing_v="fixed")
    o2_l = doc.create_frame("O2L", opt2, 460.0, 40.0, layout_mode="vertical", gap=2.0, sizing_h="fill", sizing_v="hug")
    doc.create_text("O2T", "CBZ (Comic Book Archive Digital)", o2_l, font_size=13.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.create_text("O2D", "Format reader e-book (Kobo, Kindle, Mihon, CDisplayEx)", o2_l, font_size=10.0, color=C["text_muted"])
    doc.build_badge("BdgCBZ", "DIGITAL", opt2, tone="cyan")

    opt3 = doc.create_frame("Opt_Folder", f_grid, 624.0, 56.0, fill=C["surface_2"], stroke=C["line"], corner_radius=8.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 16.0, 0.0, 16.0), sizing_h="fill", sizing_v="fixed")
    o3_l = doc.create_frame("O3L", opt3, 460.0, 40.0, layout_mode="vertical", gap=2.0, sizing_h="fill", sizing_v="hug")
    doc.create_text("O3T", "Image folder (lossless PNG / WebP)", o3_l, font_size=13.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.create_text("O3D", "High-quality loose images with consistent naming", o3_l, font_size=10.0, color=C["text_muted"])
    doc.build_badge("BdgPNG", "RAW", opt3, tone="neutral")

    doc.create_text("OptsTitle", "PENGATURAN CETAK & RENDERING", modal, font_size=11.0, font_weight="Bold", font_family=FONTS["brand"], color=C["coral"])
    opts_box = doc.create_frame("OptsBox", modal, 624.0, 180.0, fill=C["surface_card"], stroke=C["line"], corner_radius=8.0, layout_mode="vertical", gap=10.0, padding=(12.0, 14.0, 12.0, 14.0), sizing_h="fill", sizing_v="hug")
    
    dpi_row = doc.create_frame("DPIRow", opts_box, 596.0, 28.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    doc.create_text("DPILabel", "Resolusi Rendering:", dpi_row, font_size=11.0, color=C["text"])
    dpi_segs = doc.create_frame("DPISegs", dpi_row, 340.0, 26.0, layout_mode="horizontal", gap=8.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_badge("DPI1", "300 DPI (print)", dpi_segs, tone="coral")
    doc.build_badge("DPI2", "150 DPI (web)", dpi_segs, tone="neutral")
    doc.build_badge("DPI3", "600 DPI (master)", dpi_segs, tone="neutral")

    doc.create_text("Chk1", "[x]  Add 3mm bleed and crop marks", opts_box, font_size=11.0, font_family=FONTS["mono"], color=C["success"])
    doc.create_text("Chk2", "[x]  Convert CMYK separations (Japan Color 2001 Coated)", opts_box, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    doc.create_text("Chk3", "[ ]  Include cover page and publisher colophon", opts_box, font_size=11.0, font_family=FONTS["mono"], color=C["text_dim"])

    sum_box = doc.create_frame("SummaryBox", modal, 624.0, 60.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="vertical", gap=4.0, padding=(10.0, 12.0, 10.0, 12.0), sizing_h="fill", sizing_v="hug")
    doc.create_text("SumFile", "File: Chapter12_ID_PrintReady.pdf", sum_box, font_size=11.0, font_weight="Bold", font_family=FONTS["mono"], color=C["text"])
    doc.create_text("SumMeta", "Estimated size: ~48.2 MB  ·  41 complete pages  ·  182 bubbles translated", sum_box, font_size=10.0, color=C["text_muted"])

    m_foot = doc.create_frame("MFoot", modal, 624.0, 44.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    doc.build_button("BtnCancel", "Batal (Esc)", m_foot, variant="ghost", size="md")
    m_actions = doc.create_frame("MActions", m_foot, 360.0, 36.0, layout_mode="horizontal", gap=10.0, main_align="max", cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_button("BtnPreset", "Save preset", m_actions, variant="default", size="md")
    doc.build_button("BtnDoExport", "Export print-ready (41 pages)", m_actions, variant="primary", size="md")

    resolve_tree_layout(doc.doc["nodes"], s5)

    # =======================================================================
    # SCREEN 6: 06. DESIGN SYSTEM, LIVING TOKENS & SHADCN/BITS-UI PRIMITIVES
    # =======================================================================
    sp = screen_spec("system")
    s6 = doc.create_frame(sp["name"], 1, sp["width"], sp["height"], x=sp["x"], y=sp["y"], fill=C["surface"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=16.0, layout_mode="vertical", gap=0.0, clip=True)
    add_window_bar(doc, s6, "Kuron Studio — Living Design System & Primitives (Issue #83, #84, #88)")

    h6 = doc.create_frame("Header", s6, 1280.0, 48.0, fill=C["surface_2"], stroke=C["line"], layout_mode="horizontal", gap=16.0, padding=(0.0, 24.0, 0.0, 24.0), main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    doc.create_text("DSTitle", "Kuron Studio Design System (Tokens, Parity & Bits-UI)", h6, font_size=14.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.build_badge("BdgSpec", "1:1 WITH ISSUES & APP.CSS", h6, tone="cyan")

    ds_body = doc.create_frame("DSBody", s6, 1280.0, 1324.0, fill=C["bg"], layout_mode="vertical", gap=20.0, padding=(24.0, 32.0, 24.0, 32.0), sizing_h="fill", sizing_v="fill")

    # 1. Surface Ramp: Dark vs Light 1:1 Parity (Issue #84)
    doc.create_text("S_Title", "1. SURFACES & ELEVATION: DUAL RAMP PARITY (DARK DEFAULT VS LIGHT THEME)", ds_body, font_size=12.0, font_weight="Bold", font_family=FONTS["brand"], color=C["coral"])
    s_row = doc.create_frame("SRow", ds_body, 1216.0, 115.0, layout_mode="horizontal", gap=12.0, sizing_h="fill", sizing_v="fixed")
    
    surfaces = [
        ("bg", C["bg"], C["light_bg"], "Base canvas"),
        ("surface", C["surface"], C["light_surface"], "Main window"),
        ("surface_2", C["surface_2"], C["light_surface_2"], "Sidebar and bars"),
        ("raised", C["surface_card"], C["light_raised"], "Cards (levels 2/3)"),
        ("hover", C["surface_hover"], C["light_hover"], "Hover row"),
    ]
    for s_name, d_hex, l_hex, s_role in surfaces:
        scard = doc.create_frame(f"SC_{s_name}", s_row, 230.0, 115.0, fill=C["surface_card"], stroke=C["line"], corner_radius=8.0, layout_mode="vertical", main_align="spaceBetween", padding=(10.0, 12.0, 10.0, 12.0), sizing_h="fill", sizing_v="fixed")
        doc.create_text("SCN", f"--ks-{s_name}", scard, font_size=12.0, font_weight="Bold", font_family=FONTS["mono"], color=C["text"])
        
        # Swatch pair row
        sw_pair = doc.create_frame("SwPair", scard, 206.0, 40.0, layout_mode="horizontal", gap=8.0, sizing_h="fill", sizing_v="fixed")
        # Dark swatch
        d_sw = doc.create_frame("DSw", sw_pair, 98.0, 40.0, fill=d_hex, stroke=C["line"], corner_radius=4.0, layout_mode="vertical", main_align="center", padding=(2.0, 6.0, 2.0, 6.0), sizing_h="fill", sizing_v="fixed")
        doc.create_text("DHex", f"Dark {d_hex}", d_sw, font_size=9.0, font_family=FONTS["mono"], color=C["text"] if s_name != "bg" else C["text_muted"])
        # Light swatch
        l_sw = doc.create_frame("LSw", sw_pair, 98.0, 40.0, fill=l_hex, stroke=C["line"], corner_radius=4.0, layout_mode="vertical", main_align="center", padding=(2.0, 6.0, 2.0, 6.0), sizing_h="fill", sizing_v="fixed")
        doc.create_text("LHex", f"Light {l_hex}", l_sw, font_size=9.0, font_family=FONTS["mono"], color=_LIGHT["colors"]["text"])
        
        doc.create_text("SCR", s_role, scard, font_size=10.0, color=C["text_muted"])

    # 2. Accents & Semantics
    doc.create_text("A_Title", "2. SEMANTIC ROLES (NO NEW HEX OUTSIDE APP.CSS)", ds_body, font_size=12.0, font_weight="Bold", font_family=FONTS["brand"], color=C["coral"])
    a_row = doc.create_frame("ARow", ds_body, 1216.0, 95.0, layout_mode="horizontal", gap=12.0, sizing_h="fill", sizing_v="fixed")
    
    accents = [
        (f"ACTION {C['coral']}", C["coral"], "Primary action only", "Export, translate, bubble selection. Never a background."),
        (f"TECHNICAL {C['cyan']}", C["cyan"], "Technical info", "Counter [007/182], Coords [X,Y], Confidence %, Monospace."),
        (f"SUCCESS {C['success']}", C["success"], "Done / passed", "100% translated, optimal fit, online status."),
        (f"WARN {C['warn']}", C["warn"], "Needs review", "Tight fit (>100%), not detected yet, warnings."),
        (f"DANGER {C['danger']}", C["danger"], "Cancel / delete", "Severe overflow, OCR failure, destructive action."),
    ]
    for a_name, a_hex, a_rule, a_desc in accents:
        acard = doc.create_frame(f"AC_{a_name}", a_row, 230.0, 95.0, fill=C["surface_card"], stroke=C["line"], stroke_width=1.0, corner_radius=8.0, layout_mode="vertical", gap=3.0, padding=(8.0, 12.0, 8.0, 12.0), sizing_h="fill", sizing_v="fixed")
        doc.create_text("AN", a_name, acard, font_size=11.0, font_weight="Bold", font_family=FONTS["mono"], color=a_hex)
        doc.create_text("AR", a_rule, acard, font_size=11.0, font_weight="Bold", color=C["text"])
        doc.create_text("AD", a_desc, acard, font_size=9.0, color=C["text_muted"])

    # 3. Three Elevation Levels & List Row Discipline (Issue #84 & #88)
    doc.create_text("E_Title", "3. THREE ELEVATION LEVELS & LIST ROW RULES (ISSUE #84 & #88)", ds_body, font_size=12.0, font_weight="Bold", font_family=FONTS["brand"], color=C["coral"])
    e_row = doc.create_frame("ERow", ds_body, 1216.0, 115.0, layout_mode="horizontal", gap=16.0, sizing_h="fill", sizing_v="fixed")

    # Elevation 3-tier box
    elev_card = doc.create_frame("ElevCard", e_row, 590.0, 115.0, fill=C["surface_card"], stroke=C["line"], corner_radius=8.0, layout_mode="vertical", gap=4.0, padding=(10.0, 14.0, 10.0, 14.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("EL_T", "Three elevation levels (strict, no level 4):", elev_card, font_size=11.0, font_weight="Bold", color=C["text"])
    doc.create_text("EL_1", "• Level 1: hairline border (--ks-line) — base canvas, panels, toolbar", elev_card, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    doc.create_text("EL_2", "• Level 2: shadow-xs + border (--ks-surface-card) — cards, outline controls, table cells", elev_card, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    doc.create_text("EL_3", "• Level 3: floating shadow (--ks-raised) — popovers, dropdowns, modal dialogs", elev_card, font_size=11.0, font_family=FONTS["mono"], color=C["coral"])

    # List row rule box
    row_card = doc.create_frame("RowRuleCard", e_row, 590.0, 115.0, fill=C["surface_card"], stroke=C["line"], corner_radius=8.0, layout_mode="vertical", gap=4.0, padding=(10.0, 14.0, 10.0, 14.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("RR_T", "List row rules (Bits-UI headless compatible):", row_card, font_size=11.0, font_weight="Bold", color=C["text"])
    doc.create_text("RR_1", "• Idle: transparent / bg-surface — clean, no thick border", row_card, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    doc.create_text("RR_2", "• Hover: --ks-hover — smooth 100ms transition", row_card, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    doc.create_text("RR_3", "• Keyboard cursor: neutral --ks-line-strong — arrow-key navigation", row_card, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    doc.create_text("RR_4", "• Active persistent: data-current=\"true\" + primary left-line accent", row_card, font_size=11.0, font_family=FONTS["mono"], color=C["coral"])

    # 4. Showcase Koleksi Primitif Headless Bits-UI / shadcn-svelte (Issue #83)
    doc.create_text("H_Title", "4. IMPLEMENTASI PRIMITIF HEADLESS BITS-UI / SHADCN-SVELTE (ISSUE #83)", ds_body, font_size=12.0, font_weight="Bold", font_family=FONTS["brand"], color=C["coral"])
    
    # Primitives Showcase Container (3 Columns of Real Headless Widgets)
    p_grid = doc.create_frame("PrimGrid", ds_body, 1216.0, 240.0, layout_mode="horizontal", gap=16.0, sizing_h="fill", sizing_v="fixed")

    # Col 1: Bits-UI Combobox (Expanded Dropdown State with Keyboard Navigation)
    c_combo = doc.create_frame("P_Combo", p_grid, 390.0, 240.0, fill=C["surface_card"], stroke=C["line"], corner_radius=8.0, layout_mode="vertical", gap=8.0, padding=(12.0, 14.0, 12.0, 14.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("PC_T", "Bits-UI Combobox (Pengganti Lov.svelte):", c_combo, font_size=11.0, font_weight="Bold", color=C["text"])
    
    cb_inp = doc.create_frame("CBInp", c_combo, 362.0, 32.0, fill=C["surface_2"], stroke=C["line_strong"], corner_radius=6.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 10.0, 0.0, 10.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("CBVal", "DeepSeek Chat (V3)", cb_inp, font_size=11.0, font_family=FONTS["mono"], color=C["text"])
    doc.create_text("CBChev", "▾", cb_inp, font_size=11.0, color=C["text_dim"])
    
    # Popover Listbox (Level 3 Floating)
    cb_list = doc.create_frame("CBList", c_combo, 362.0, 130.0, fill=C["surface_2"], stroke=C["line_strong"], corner_radius=6.0, layout_mode="vertical", gap=2.0, padding=(4.0, 4.0, 4.0, 4.0), sizing_h="fill", sizing_v="fixed")
    
    # Item 1 (Idle)
    it1 = doc.create_frame("It1", cb_list, 354.0, 28.0, layout_mode="horizontal", cross_align="center", padding=(0.0, 8.0, 0.0, 8.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("It1T", "Claude 3.5 Sonnet (Vision) · $3.00", it1, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    
    # Item 2 (Active Keyboard Cursor with subtle hover fill & quiet checkmark)
    it2 = doc.create_frame("It2", cb_list, 354.0, 28.0, fill=C["surface_hover"], stroke=C["line_strong"], corner_radius=4.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 8.0, 0.0, 8.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("It2T", "✓ DeepSeek Chat (V3) · $0.27", it2, font_size=11.0, font_weight="Bold", font_family=FONTS["mono"], color=C["text"])
    doc.create_text("It2B", "Selected", it2, font_size=9.0, color=C["text_dim"])

    # Item 3 (Idle)
    it3 = doc.create_frame("It3", cb_list, 354.0, 28.0, layout_mode="horizontal", cross_align="center", padding=(0.0, 8.0, 0.0, 8.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("It3T", "GPT-4o Mini (Vision) · $0.15", it3, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])

    # Col 2: Bits-UI DropdownMenu & Tooltip
    c_menu = doc.create_frame("P_Menu", p_grid, 390.0, 240.0, fill=C["surface_card"], stroke=C["line"], corner_radius=8.0, layout_mode="vertical", gap=8.0, padding=(12.0, 14.0, 12.0, 14.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("PM_T", "Bits-UI DropdownMenu & Tooltip:", c_menu, font_size=11.0, font_weight="Bold", color=C["text"])
    
    # Floating Tooltip sample
    tip_box = doc.create_frame("TipBox", c_menu, 220.0, 24.0, fill=C["bg"], stroke=C["line_strong"], corner_radius=4.0, layout_mode="horizontal", main_align="center", cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.create_text("TipTxt", "Tooltip: Tinjau Balon Kata (F3)", tip_box, font_size=10.0, font_family=FONTS["mono"], color=C["text"])

    # Dropdown Menu Items (Level 3 Floating)
    dm_box = doc.create_frame("DMBox", c_menu, 362.0, 140.0, fill=C["surface_2"], stroke=C["line_strong"], corner_radius=6.0, layout_mode="vertical", gap=2.0, padding=(4.0, 4.0, 4.0, 4.0), sizing_h="fill", sizing_v="fixed")
    
    m_i1 = doc.create_frame("MI1", dm_box, 354.0, 26.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 8.0, 0.0, 8.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("MI1_T", "Buka di Editor", m_i1, font_size=11.0, color=C["text"])
    doc.create_text("MI1_K", "Enter", m_i1, font_size=10.0, font_family=FONTS["mono"], color=C["text_dim"])

    m_i2 = doc.create_frame("MI2", dm_box, 354.0, 26.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 8.0, 0.0, 8.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("MI2_T", "Re-detect page", m_i2, font_size=11.0, color=C["text"])
    doc.create_text("MI2_K", "⌘D", m_i2, font_size=10.0, font_family=FONTS["mono"], color=C["text_dim"])

    # Hairline divider
    doc.create_frame("MDiv", dm_box, 354.0, 1.0, fill=C["line"], sizing_h="fill", sizing_v="fixed")

    m_i3 = doc.create_frame("MI3", dm_box, 354.0, 26.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 8.0, 0.0, 8.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("MI3_T", "Remove from project", m_i3, font_size=11.0, color=C["danger"])
    doc.create_text("MI3_K", "⌫", m_i3, font_size=10.0, font_family=FONTS["mono"], color=C["danger"])

    # Col 3: Svelte-Sonner Toast & Destructive Dialog Preview
    c_sonner = doc.create_frame("P_Sonner", p_grid, 390.0, 240.0, fill=C["surface_card"], stroke=C["line"], corner_radius=8.0, layout_mode="vertical", gap=8.0, padding=(12.0, 14.0, 12.0, 14.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("PS_T", "Svelte-Sonner Toast & Focus Trap Dialog:", c_sonner, font_size=11.0, font_weight="Bold", color=C["text"])

    # Svelte-Sonner Toast Card (Quiet hairline border)
    toast = doc.create_frame("SonnerToast", c_sonner, 362.0, 64.0, fill=C["surface_2"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=8.0, layout_mode="horizontal", gap=10.0, cross_align="center", padding=(10.0, 12.0, 10.0, 12.0), sizing_h="fill", sizing_v="fixed")
    doc.create_ellipse("SIco", toast, 20.0, C["success"])
    st_t = doc.create_frame("STT", toast, 230.0, 44.0, layout_mode="vertical", gap=2.0, sizing_h="fill", sizing_v="hug")
    doc.create_text("ST1", "Batch complete: 28 pages", st_t, font_size=11.0, font_weight="Bold", color=C["text"])
    doc.create_text("ST2", "13 pages skipped (31% quota saved)", st_t, font_size=10.0, color=C["text_muted"])
    doc.build_button("BtnUndo", "Urungkan", toast, variant="default", size="sm")

    # Mini Alert Dialog Confirmation (Focus trap)
    dia_box = doc.create_frame("DiaBox", c_sonner, 362.0, 110.0, fill=C["surface_2"], stroke=C["line_strong"], corner_radius=8.0, layout_mode="vertical", gap=6.0, padding=(10.0, 12.0, 10.0, 12.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("D1_T", "Delete confirmation dialog (Esc to close):", dia_box, font_size=11.0, font_weight="Bold", color=C["text"])
    doc.create_text("D1_M", "Delete Chapter 12? This action cannot be undone.", dia_box, font_size=10.0, color=C["text_muted"])
    d_acts = doc.create_frame("DActs", dia_box, 340.0, 28.0, layout_mode="horizontal", gap=8.0, main_align="max", cross_align="center", sizing_h="fill", sizing_v="fixed")
    doc.build_button("DBtnCancel", "Batal (Esc)", d_acts, variant="default", size="sm")
    doc.build_button("DBtnDel", "Delete", d_acts, variant="danger" if "danger" in C else "primary", size="sm")

    # 5. Command Palette ⌘K (Global Accessible Action Modal)
    doc.create_text("CP_Title", "5. COMMAND PALETTE (⌘K SPOTLIGHT MODAL)", ds_body, font_size=12.0, font_weight="Bold", font_family=FONTS["brand"], color=C["coral"])
    cmd_palette = doc.create_frame("CmdPalette", ds_body, 1216.0, 160.0, fill=C["surface_card"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=10.0, layout_mode="vertical", gap=6.0, padding=(12.0, 16.0, 12.0, 16.0), sizing_h="fill", sizing_v="fixed")
    
    cp_inp = doc.create_frame("CPInp", cmd_palette, 1184.0, 36.0, fill=C["surface_2"], stroke=C["line_strong"], corner_radius=6.0, layout_mode="horizontal", cross_align="center", padding=(0.0, 14.0, 0.0, 14.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("CPIco", "⌘", cp_inp, font_size=13.0, font_family=FONTS["mono"], color=C["text_dim"])
    doc.create_text("CPTxt", "Type a command or search pages...", cp_inp, font_size=12.0, color=C["text_dim"])
    
    cp_list = doc.create_frame("CPList", cmd_palette, 1184.0, 90.0, layout_mode="horizontal", gap=12.0, sizing_h="fill", sizing_v="fixed")
    
    cp_actions = [
        ("Translate this page", "⌘Enter", "Call the active AI provider"),
        ("Review bubble ledger", "F3", "Open the review table for all bubbles"),
        ("Export print-ready PDF", "⌘E", "Open the 300 DPI export dialog"),
        ("Provider and model settings", "⌘,", "Manage API keys and endpoints"),
    ]
    for act_name, act_key, act_desc in cp_actions:
        ac = doc.create_frame(f"CP_{act_key}", cp_list, 285.0, 84.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="vertical", gap=4.0, padding=(10.0, 12.0, 10.0, 12.0), sizing_h="fill", sizing_v="fixed")
        ac_h = doc.create_frame("ACH", ac, 260.0, 20.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
        doc.create_text("AT", act_name, ac_h, font_size=11.0, font_weight="Bold", color=C["text"])
        doc.create_text("AK", act_key, ac_h, font_size=10.0, font_family=FONTS["mono"], color=C["text_muted"])
        doc.create_text("AD", act_desc, ac, font_size=10.0, color=C["text_muted"])

    resolve_tree_layout(doc.doc["nodes"], s6)

    # =======================================================================
    # SCREEN 7: 07. BATCH TRANSLATE & AI QUOTA COST ESTIMATOR (ISSUE #67 & #83)
    # =======================================================================
    sp = screen_spec("batch")
    s7 = doc.create_frame(sp["name"], 1, sp["width"], sp["height"], x=sp["x"], y=sp["y"], fill=C["surface"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=16.0, layout_mode="none", clip=True)
    
    # 1. Render realistic Kuron Studio workbench grid in the background
    add_dimmed_app_background(doc, s7, _DARK["name"] + " — Chapter 12 (batch quota)")

    # 2. Translucent Dimmed Backdrop Overlay (Level 3 Floating Modal Pattern)
    overlay7 = doc.create_frame("DimOverlay7", s7, 1280.0, 960.0, x=0.0, y=0.0, fill=CONTENT["scrim_overlay"], layout_mode="vertical", main_align="center", cross_align="center", sizing_h="fixed", sizing_v="fixed")
    
    # 3. Bits-UI Headless Modal Card (Level 3 Floating Elevation)
    modal7 = doc.create_frame("DialogQuota", overlay7, 680.0, 780.0, fill=C["surface_raised"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=14.0, layout_mode="vertical", gap=16.0, padding=(24.0, 28.0, 24.0, 28.0), sizing_h="fixed", sizing_v="hug")

    # Dialog Header
    dh7 = doc.create_frame("DHeader7", modal7, 624.0, 42.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    dh7_l = doc.create_frame("DHL7", dh7, 480.0, 38.0, layout_mode="vertical", gap=2.0, sizing_h="hug", sizing_v="fixed")
    doc.create_text("DTitle7", "Batch translation (AI) — quota estimator", dh7_l, font_size=15.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text"])
    doc.create_text("DSub7", "Token quota preflight and deduplication (Issue #67 & #83)", dh7_l, font_size=11.0, color=C["text_muted"])
    doc.build_button("BtnClose7", "✕", dh7, variant="ghost", size="sm")

    # CARD 1: Scope & Filter Card (Segmented Selection & Auto-skip rules)
    scope_card = doc.create_frame("ScopeCard", modal7, 624.0, 160.0, fill=C["surface_card"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=10.0, layout_mode="vertical", gap=10.0, padding=(14.0, 16.0, 14.0, 16.0), sizing_h="fill", sizing_v="hug")
    
    sc_hdr = doc.create_frame("ScHdr", scope_card, 592.0, 20.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
    doc.create_text("ScTitle", "1. TRANSLATION SCOPE & PAGE FILTERS", sc_hdr, font_size=11.0, font_weight="Bold", font_family=FONTS["brand"], color=C["coral"])
    doc.create_text("ScCount", "28 of 41 pages selected", sc_hdr, font_size=10.0, font_family=FONTS["mono"], color=C["text_muted"])

    # Scope Radios Row
    sc_radios = doc.create_frame("ScRadios", scope_card, 592.0, 32.0, layout_mode="horizontal", gap=8.0, sizing_h="fill", sizing_v="fixed")
    
    r_sel1 = doc.create_frame("Rad1", sc_radios, 190.0, 32.0, fill=C["surface_2"], stroke=C["coral"], stroke_width=1.0, corner_radius=6.0, layout_mode="horizontal", gap=8.0, cross_align="center", padding=(0.0, 10.0, 0.0, 10.0), sizing_h="fill", sizing_v="fixed")
    doc.create_ellipse("rdot1", r_sel1, 8.0, C["coral"])
    doc.create_text("rtxt1", "Selected pages (28)", r_sel1, font_size=11.0, font_weight="Bold", color=C["text"])

    r_sel2 = doc.create_frame("Rad2", sc_radios, 190.0, 32.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", gap=8.0, cross_align="center", padding=(0.0, 10.0, 0.0, 10.0), sizing_h="fill", sizing_v="fixed")
    doc.create_ellipse("rdot2", r_sel2, 8.0, C["line_strong"])
    doc.create_text("rtxt2", "Active folder (41)", r_sel2, font_size=11.0, color=C["text_muted"])

    r_sel3 = doc.create_frame("Rad3", sc_radios, 190.0, 32.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", gap=8.0, cross_align="center", padding=(0.0, 10.0, 0.0, 10.0), sizing_h="fill", sizing_v="fixed")
    doc.create_ellipse("rdot3", r_sel3, 8.0, C["line_strong"])
    doc.create_text("rtxt3", "All chapters (182)", r_sel3, font_size=11.0, color=C["text_muted"])

    # Smart Skip Checkboxes Row
    sc_checks = doc.create_frame("ScChecks", scope_card, 592.0, 24.0, layout_mode="horizontal", gap=16.0, cross_align="center", sizing_h="fill", sizing_v="hug")
    doc.create_text("chk_skip0", "[x] Skip 0-bubble pages (3 pages · quota saved)", sc_checks, font_size=11.0, font_family=FONTS["mono"], color=C["text_muted"])
    doc.create_text("chk_tm", "[x] TM cache hits (6 pages · 0 requests)", sc_checks, font_size=11.0, font_family=FONTS["mono"], color=C["success"])
    doc.create_text("chk_done", "[x] Skip completed (4 pages)", sc_checks, font_size=11.0, font_family=FONTS["mono"], color=C["text_dim"])

    # Pipeline summary strip inside Card 1
    sc_strip = doc.create_frame("ScStrip", scope_card, 592.0, 30.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 12.0, 0.0, 12.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("Strip1", "Total: 41 pages", sc_strip, font_size=11.0, font_family=FONTS["mono"], color=C["text_dim"])
    doc.create_text("StripArr1", "→", sc_strip, font_size=11.0, color=C["line_strong"])
    doc.create_text("Strip2", "−13 automatically skipped", sc_strip, font_size=11.0, font_family=FONTS["mono"], color=C["warn"])
    doc.create_text("StripArr2", "→", sc_strip, font_size=11.0, color=C["line_strong"])
    doc.create_text("Strip3", "28 active requests (118 bubbles)", sc_strip, font_size=11.0, font_weight="Bold", font_family=FONTS["mono"], color=C["coral"])

    # CARD 2: Configuration Grid (2x2 Field Lov Pattern)
    cfg_card = doc.create_frame("ConfigCard", modal7, 624.0, 128.0, fill=C["surface_card"], stroke=C["line"], corner_radius=10.0, layout_mode="vertical", gap=8.0, padding=(12.0, 16.0, 12.0, 16.0), sizing_h="fill", sizing_v="hug")
    doc.create_text("CfgTitle", "2. AI PROVIDER AND LANGUAGE STYLE CONFIGURATION", cfg_card, font_size=11.0, font_weight="Bold", font_family=FONTS["brand"], color=C["text_muted"])
    
    cfg_grid = doc.create_frame("CfgGrid", cfg_card, 592.0, 78.0, layout_mode="vertical", gap=8.0, sizing_h="fill", sizing_v="hug")
    
    cfg_r1 = doc.create_frame("CfgR1", cfg_grid, 592.0, 36.0, layout_mode="horizontal", gap=12.0, sizing_h="fill", sizing_v="fixed")
    p_box = doc.create_frame("PBox", cfg_r1, 290.0, 36.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 10.0, 0.0, 10.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("PVal", "Provider: DeepSeek Official", p_box, font_size=11.0, color=C["text"])
    doc.create_text("PCh", "▾", p_box, font_size=10.0, color=C["text_dim"])
    
    m_box = doc.create_frame("MBox", cfg_r1, 290.0, 36.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 10.0, 0.0, 10.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("MVal", "Model: DeepSeek Chat (V3)", m_box, font_size=11.0, font_family=FONTS["mono"], color=C["text"])
    doc.create_text("MCh", "▾", m_box, font_size=10.0, color=C["text_dim"])

    cfg_r2 = doc.create_frame("CfgR2", cfg_grid, 592.0, 36.0, layout_mode="horizontal", gap=12.0, sizing_h="fill", sizing_v="fixed")
    l_box = doc.create_frame("LBox", cfg_r2, 290.0, 36.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 10.0, 0.0, 10.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("LVal", "Target: English (natural)", l_box, font_size=11.0, color=C["text"])
    doc.create_text("LCh", "▾", l_box, font_size=10.0, color=C["text_dim"])

    sty_box = doc.create_frame("StyBox", cfg_r2, 290.0, 36.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", padding=(0.0, 10.0, 0.0, 10.0), sizing_h="fill", sizing_v="fixed")
    doc.create_text("StyVal", "Style: manga dialogue (character)", sty_box, font_size=11.0, color=C["text"])
    doc.create_text("StyCh", "▾", sty_box, font_size=10.0, color=C["text_dim"])

    # CARD 3: Executive Quota & Cost Prediction Ledger (Craftsmanship-grade)
    pred_box = doc.create_frame("PredBox", modal7, 624.0, 160.0, fill=C["surface_card"], stroke=C["line_strong"], stroke_width=1.0, corner_radius=10.0, layout_mode="vertical", gap=10.0, padding=(14.0, 16.0, 14.0, 16.0), sizing_h="fill", sizing_v="hug")
    
    pred_hdr = doc.create_frame("PredHdr", pred_box, 592.0, 20.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    doc.create_text("PHTxt", "3. QUOTA ESTIMATE AND FINANCIAL PROTECTION", pred_hdr, font_size=11.0, font_weight="Bold", font_family=FONTS["brand"], color=C["coral"])
    doc.build_badge("BdgFailFast", "FAIL-FAST 3x AKTIF", pred_hdr, tone="ok")

    # 3-Column balanced metrics
    pred_grid = doc.create_frame("PredGrid", pred_box, 592.0, 56.0, layout_mode="horizontal", gap=12.0, sizing_h="fill", sizing_v="fixed")
    
    # Col A: Calls
    c_calls = doc.create_frame("C_Calls", pred_grid, 186.0, 56.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="vertical", main_align="center", padding=(4.0, 12.0, 4.0, 12.0), gap=2.0, sizing_h="fill", sizing_v="fixed")
    doc.create_text("V_Calls", "28 Request", c_calls, font_size=14.0, font_weight="Bold", font_family=FONTS["mono"], color=C["text"])
    doc.create_text("L_Calls", "1 request per active page", c_calls, font_size=9.5, color=C["text_muted"])

    # Col B: Tokens
    c_toks = doc.create_frame("C_Toks", pred_grid, 186.0, 56.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="vertical", main_align="center", padding=(4.0, 12.0, 4.0, 12.0), gap=2.0, sizing_h="fill", sizing_v="fixed")
    doc.create_text("V_Toks", "~42.7K Tok", c_toks, font_size=14.0, font_weight="Bold", font_family=FONTS["mono"], color=C["text"])
    doc.create_text("L_Toks", "34.2k input + 8.5k output", c_toks, font_size=9.5, color=C["text_muted"])

    # Col C: Cost
    c_cost = doc.create_frame("C_Cost", pred_grid, 186.0, 56.0, fill=C["surface_2"], stroke=C["line"], corner_radius=6.0, layout_mode="vertical", main_align="center", padding=(4.0, 12.0, 4.0, 12.0), gap=2.0, sizing_h="fill", sizing_v="fixed")
    doc.create_text("V_Cost", "< $0.01 USD", c_cost, font_size=14.0, font_weight="Bold", font_family=FONTS["mono"], color=C["success"])
    doc.create_text("L_Cost", "$0.004 saved by TM cache", c_cost, font_size=9.5, color=C["text_muted"])

    # Safety Notice Banner inside Card 3
    safe_banner = doc.create_frame("SafeBanner", pred_box, 592.0, 26.0, fill=C["surface_2"], stroke=C["line"], corner_radius=4.0, layout_mode="horizontal", gap=8.0, cross_align="center", padding=(0.0, 10.0, 0.0, 10.0), sizing_h="fill", sizing_v="fixed")
    doc.create_ellipse("sdot", safe_banner, 6.0, C["success"])
    doc.create_text("SafeTxt", "Balance protection: automatic execution stops when provider credit is exhausted or 429 repeats.", safe_banner, font_size=10.0, color=C["text_muted"])

    # Modal Action Buttons
    m7_foot = doc.create_frame("MFoot7", modal7, 624.0, 44.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="fixed")
    doc.build_button("BtnCancel7", "Batal (Esc)", m7_foot, variant="ghost", size="md")
    
    m7_actions = doc.create_frame("MActions7", m7_foot, 420.0, 36.0, layout_mode="horizontal", gap=10.0, main_align="max", cross_align="center", sizing_h="hug", sizing_v="fixed")
    doc.build_button("BtnSimulate", "Simulate quota (dry run)", m7_actions, variant="default", size="md")
    doc.build_button("BtnStartBatch", "Start batch translation (28 pages)", m7_actions, variant="primary", size="md")

    resolve_tree_layout(doc.doc["nodes"], s7)

    # Save to disk (generic, overridable output names)
    out_dir = os.environ.get("FIGCRAFT_OUT_DIR", "design")
    os.makedirs(out_dir, exist_ok=True)
    main_path = os.path.join(out_dir, "workbench.figcraft")
    clean_path = os.path.join(out_dir, "workbench-clean.figcraft")
    doc.save(main_path)
    doc.save(clean_path)
    print(f"Saved {main_path} and {clean_path} successfully!")
    return doc

if __name__ == "__main__":
    build_full_flow()
