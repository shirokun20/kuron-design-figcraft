#!/usr/bin/env python3
"""FigCraft QuickDesign — token-driven rapid UI generator (3.1.0).

Every colour, font size, spacing step, component size, and microcopy string is
resolved from the project's ``DESIGN.md`` through ``design_manifest.py``. The
``--generate`` flag builds Components, Screen, or Form nodes for Live Generate
sessions, and the layout is driven by ``style_direction``.

All network operations use timeouts; the preview worker is always terminated.
"""

import argparse
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import figcraft_tool as ft  # noqa: E402
from design_manifest import STYLE_DIRECTIONS, DesignManifestError  # noqa: E402
from figcraft_tool import (  # noqa: E402
    COMPONENT,
    CONTENT,
    DESIGN_DOC,
    FONTS,
    GEOMETRY,
    SPACE,
    TYPE,
    TOKENS,
    FigcraftClient,
    FigcraftDocument,
    get_tokens,
    lint_design,
)

STYLE = DESIGN_DOC["style_direction"]
LOCALE = DESIGN_DOC["locale"]
COPY_TONE = DESIGN_DOC["copy_tone"]
SCREEN = GEOMETRY.get("screen", {})
SCREEN_W = float(SCREEN.get("width", 1280))
SCREEN_H = float(SCREEN.get("height", 960))
BLOCKS = GEOMETRY.get("blocks", {})
COPY = DESIGN_DOC.get("copy", {}).get(LOCALE, {})


def text(key: str) -> str:
    """Return project microcopy; fall back to a neutral title-cased key."""
    value = COPY.get(key)
    return value if value else key.replace("_", " ").title()


def use_theme(theme: Optional[str]) -> None:
    """Rebind the shared builder tokens for an explicit theme override."""
    global TOKENS, FONTS, CONTENT
    chosen = theme or DESIGN_DOC.get("default_theme", "dark")
    ft.TOKENS = get_tokens(chosen)
    TOKENS = ft.TOKENS
    FONTS = TOKENS["typography"]
    CONTENT = TOKENS["content"]


STYLE_LEVERS: Dict[str, Dict[str, Any]] = {
    "dense_operational": {"gap": SPACE["xs"], "pad": SPACE["sm"], "columns": 3,
                          "rail": True, "inspector": True, "elevation": 2},
    "bento_modular": {"gap": SPACE["lg"], "pad": SPACE["md"], "columns": 2,
                      "rail": False, "inspector": False, "elevation": 3},
    "editorial": {"gap": SPACE["xl"], "pad": SPACE["lg"], "columns": 1,
                  "rail": False, "inspector": False, "elevation": 1},
    "clean_utility": {"gap": SPACE["md"], "pad": SPACE["md"], "columns": 1,
                      "rail": False, "inspector": False, "elevation": 1},
    "custom": {"gap": SPACE["md"], "pad": SPACE["md"], "columns": 2,
               "rail": False, "inspector": False, "elevation": 2},
}


def levers(style: Optional[str] = None) -> Dict[str, Any]:
    """Return token-derived layout levers for a style direction."""
    chosen = style or STYLE
    if chosen not in STYLE_LEVERS:
        raise DesignManifestError(
            "Unknown style direction %r. Expected one of %s."
            % (chosen, ", ".join(sorted(STYLE_DIRECTIONS)))
        )
    return STYLE_LEVERS[chosen]


# ---------------------------------------------------------------------------
# RAPID BLOCK COMPONENT FACTORY
# ---------------------------------------------------------------------------
class DesignBlocks:
    """Reusable blocks built only from DESIGN.md tokens and project copy."""

    @staticmethod
    def add_app_header(doc: FigcraftDocument, parent_id: int,
                       title: Optional[str] = None, chapter: Optional[str] = None,
                       page_info: Optional[str] = None,
                       actions: Optional[List[Dict[str, str]]] = None) -> int:
        """Top toolbar: brand, context, and a single primary action."""
        header_id = doc.create_frame(
            "AppHeader", parent_id, SCREEN_W, TOKENS["sizes"]["header"],
            fill=TOKENS["colors"]["surface-2"], stroke=TOKENS["colors"]["line"],
            layout_mode="horizontal", gap=SPACE["md"],
            padding=(0.0, SPACE["lg"], 0.0, SPACE["lg"]),
            main_align="spaceBetween", cross_align="center",
            sizing_h="fill", sizing_v="fixed",
        )
        left = doc.create_frame("BrandGroup", header_id, SPACE["xl"] * 10,
                                TOKENS["sizes"]["header"], layout_mode="horizontal",
                                gap=SPACE["sm"], cross_align="center",
                                sizing_h="hug", sizing_v="fixed")
        doc.create_rect("AppLogo", left, SPACE["lg"], SPACE["lg"],
                        fill=TOKENS["colors"]["text"], corner_radius=FONTS["sizes"]["badge"])
        doc.create_text("AppName", title or text("app_name"), left,
                        font_size=TYPE["body"], font_weight="Bold",
                        font_family=FONTS["font_brand"], color=TOKENS["colors"]["text"])
        doc.create_text("Sep", "—", left, font_size=TYPE["control"],
                        color=TOKENS["colors"]["text-2"])
        doc.create_text("Context", chapter or text("project_dashboard"), left,
                        font_size=TYPE["control"], font_weight="Medium",
                        color=TOKENS["colors"]["text-2"])
        doc.build_badge("BadgePages", (page_info or text("project_dashboard")).upper(),
                        left, tone="data-technical")

        right = doc.create_frame("HeaderActions", header_id, SPACE["xl"] * 10,
                                 TOKENS["sizes"]["header"], layout_mode="horizontal",
                                 gap=SPACE["sm"], cross_align="center",
                                 sizing_h="hug", sizing_v="fixed")
        if actions:
            for action in actions:
                doc.build_button(
                    name="Btn_" + action.get("key", "action"),
                    label=text(action.get("key", "action")),
                    parent_id=right,
                    variant=action.get("variant", "default"),
                    size=action.get("size", "md"),
                    icon_name=action.get("icon"),
                )
        else:
            doc.build_button("BtnDetect", text("detect_bubbles"), right,
                             variant="default", size="md")
            doc.build_button("BtnTranslate", text("translate_all"), right,
                             variant="primary", size="md")
        return header_id

    @staticmethod
    def add_stats_grid(doc: FigcraftDocument, parent_id: int,
                       stats: List[Dict[str, Any]]) -> int:
        """Dense metric row; card geometry comes from the manifest."""
        card = BLOCKS.get("statCard", {})
        row_id = doc.create_frame(
            "StatsRow", parent_id, SCREEN_W, card.get("height", SPACE["xl"] * 4),
            layout_mode="horizontal", gap=SPACE["md"],
            sizing_h="fill", sizing_v="hug",
        )
        for stat in stats:
            card_id = doc.create_frame(
                "StatCard_" + str(stat.get("key", "item")), row_id,
                card.get("width", SPACE["xl"] * 10), card.get("height", SPACE["xl"] * 4),
                fill=TOKENS["colors"]["raised"], stroke=TOKENS["colors"]["line"],
                corner_radius=tokr("card"), layout_mode="vertical", gap=SPACE["xs"],
                padding=(SPACE["sm"], SPACE["md"], SPACE["sm"], SPACE["md"]),
                sizing_h="fill", sizing_v="fixed",
            )
            top = doc.create_frame("TopLine", card_id, SPACE["xl"] * 8, TYPE["body"],
                                   layout_mode="horizontal", main_align="spaceBetween",
                                   cross_align="center", sizing_h="fill", sizing_v="hug")
            doc.create_text("Label", text(stat.get("key", "item")).upper(), top,
                            font_size=TYPE["caption"], font_weight="Bold",
                            color=TOKENS["colors"]["text-3"])
            if "tone" in stat:
                doc.build_badge("Badge", text(stat.get("badge", "status")), top,
                                tone=stat["tone"])
            bottom = doc.create_frame("BottomLine", card_id, SPACE["xl"] * 8,
                                      SPACE["xl"], layout_mode="horizontal",
                                      gap=SPACE["sm"], cross_align="baseline",
                                      sizing_h="fill", sizing_v="hug")
            doc.create_text("Value", str(stat.get("value", "")), bottom,
                            font_size=TYPE["display"], font_weight="Bold",
                            font_family=FONTS["font_mono"], color=TOKENS["colors"]["text"])
            if "desc" in stat:
                doc.create_text("Desc", stat["desc"], bottom, font_size=TYPE["caption"],
                                color=TOKENS["colors"]["text-2"])
        return row_id

    @staticmethod
    def add_project_cards_grid(doc: FigcraftDocument, parent_id: int,
                               projects: List[Dict[str, Any]]) -> int:
        """Project card grid with component-first progress bars."""
        card_spec = BLOCKS.get("projectCard", {})
        grid_id = doc.create_frame(
            "ProjectsGrid", parent_id, SCREEN_W,
            card_spec.get("height", SPACE["xl"] * 12),
            layout_mode="horizontal", gap=BLOCKS.get("screenGap", SPACE["lg"]),
            sizing_h="fill", sizing_v="hug",
        )
        for project in projects:
            card = doc.create_frame(
                "Project_" + str(project.get("key", "card")), grid_id,
                card_spec.get("width", SPACE["xl"] * 10),
                card_spec.get("height", SPACE["xl"] * 12),
                fill=TOKENS["colors"]["raised"],
                stroke=TOKENS["colors"]["action-primary"] if project.get("active")
                else TOKENS["colors"]["line"],
                stroke_width=1.5 if project.get("active") else 1.0,
                corner_radius=tokr("card"), layout_mode="vertical", gap=SPACE["sm"],
                padding=(SPACE["sm"], SPACE["sm"], SPACE["sm"], SPACE["sm"]),
                sizing_h="fixed", sizing_v="fixed",
            )
            cover = doc.create_frame(
                "CoverBox", card, card_spec.get("width", 300) - SPACE["md"] * 2,
                card_spec.get("coverHeight", SPACE["xl"] * 8),
                fill=TOKENS["colors"]["hover"], corner_radius=FONTS["sizes"]["badge"],
                layout_mode="vertical", main_align="spaceBetween",
                padding=(SPACE["sm"], SPACE["sm"], SPACE["sm"], SPACE["sm"]),
                sizing_h="fill", sizing_v="fixed",
            )
            tag_row = doc.create_frame("TagRow", cover, SPACE["xl"] * 10, TYPE["body"],
                                       layout_mode="horizontal",
                                       main_align="spaceBetween", sizing_h="fill",
                                       sizing_v="hug")
            doc.build_badge("ModeBadge", text(project.get("mode", "status")), tag_row,
                            tone="action-primary" if project.get("active") else "data-technical")
            doc.build_badge("StatusBadge", text(project.get("status", "status")), tag_row,
                            tone="status-success" if project.get("done") else "status-warn")
            doc.create_text("CoverText", text("new_project"), cover,
                            font_size=TYPE["body"], font_weight="Bold",
                            color=TOKENS["colors"]["text-3"])

            info = doc.create_frame("InfoBlock", card, SPACE["xl"] * 10, SPACE["xl"] * 4,
                                    layout_mode="vertical", gap=SPACE["xs"],
                                    sizing_h="fill", sizing_v="hug")
            doc.create_text("Title", text(project.get("key", "card")), info,
                            font_size=TYPE["heading"], font_weight="Bold",
                            font_family=FONTS["font_brand"], color=TOKENS["colors"]["text"])
            doc.create_text("Meta", "%s · %s" % (project.get("pages", 0),
                                                 project.get("bubbles", 0)),
                            info, font_size=TYPE["caption"],
                            font_family=FONTS["font_mono"],
                            color=TOKENS["colors"]["data-technical"])

            pct = float(project.get("progress", 0))
            bar = doc.create_frame("ProgressBar", card, SPACE["xl"] * 10,
                                   SPACE["xs"], fill=TOKENS["colors"]["surface-2"],
                                   corner_radius=SPACE["xs"] / 2.0,
                                   sizing_h="fill", sizing_v="fixed")
            doc.create_rect("ProgressFill", bar, SPACE["xl"] * 10 * (pct / 100.0),
                            SPACE["xs"],
                            fill=TOKENS["colors"]["action-primary" if pct >= 100
                                                  else "data-technical"],
                            corner_radius=SPACE["xs"] / 2.0)
            footer = doc.create_frame("CardFooter", card, SPACE["xl"] * 10, TYPE["body"],
                                      layout_mode="horizontal",
                                      main_align="spaceBetween", cross_align="center",
                                      sizing_h="fill", sizing_v="hug")
            doc.create_text("ProgressText", "%s%%" % pct, footer,
                            font_size=TYPE["caption"], font_family=FONTS["font_mono"],
                            color=TOKENS["colors"]["text-2"])
            doc.create_text("Updated", text("status"), footer,
                            font_size=TYPE["caption"], color=TOKENS["colors"]["text-3"])
        return grid_id

    @staticmethod
    def add_ledger_table(doc: FigcraftDocument, parent_id: int,
                         rows_data: List[Dict[str, Any]]) -> int:
        """Dense ledger table built from cell frames (no overlapping columns)."""
        spec = BLOCKS.get("ledger", {})
        table = doc.create_frame(
            "LedgerTable", parent_id, SCREEN_W, spec.get("height", SPACE["xl"] * 20),
            fill=TOKENS["colors"]["raised"], stroke=TOKENS["colors"]["line"],
            corner_radius=tokr("card"), layout_mode="vertical", gap=0.0,
            clip=True, sizing_h="fill", sizing_v="hug",
        )
        head = doc.create_frame("TableHeader", table, SCREEN_W,
                                spec.get("header", SPACE["xl"] * 2),
                                fill=TOKENS["colors"]["surface-2"],
                                stroke=TOKENS["colors"]["line"],
                                layout_mode="horizontal",
                                padding=(0.0, SPACE["md"], 0.0, SPACE["md"]),
                                cross_align="center", sizing_h="fill", sizing_v="fixed")
        for key, width in (("index", SPACE["xl"]), ("page", SPACE["xl"] * 2),
                           ("original", SPACE["xl"] * 12), ("result", SPACE["xl"] * 15),
                           ("fit", SPACE["xl"] * 3), ("status", SPACE["xl"] * 5)):
            doc.create_text("H_" + key, text(key).upper(), head,
                            font_size=TYPE["caption"], font_weight="Bold",
                            color=TOKENS["colors"]["text-3"], width=width, max_w=width)

        for index, row in enumerate(rows_data):
            row_frame = doc.create_frame(
                "Row_%02d" % (index + 1), table, SCREEN_W,
                spec.get("row", SPACE["xl"] * 2),
                fill=TOKENS["colors"]["hover"] if index % 2 else TOKENS["colors"]["raised"],
                stroke=TOKENS["colors"]["line"], layout_mode="horizontal",
                padding=(0.0, SPACE["md"], 0.0, SPACE["md"]),
                cross_align="center", sizing_h="fill", sizing_v="fixed",
            )
            doc.create_text("Idx", "%02d" % (index + 1), row_frame,
                            font_size=TYPE["caption"], font_family=FONTS["font_mono"],
                            color=TOKENS["colors"]["text-3"],
                            width=SPACE["xl"], max_w=SPACE["xl"])
            doc.create_text("Page", "P.%02d" % row.get("page", 1), row_frame,
                            font_size=TYPE["caption"], font_family=FONTS["font_mono"],
                            color=TOKENS["colors"]["data-technical"],
                            width=SPACE["xl"] * 2, max_w=SPACE["xl"] * 2)
            doc.create_text("Orig", row.get("original", "—"), row_frame,
                            font_size=TYPE["body"], color=TOKENS["colors"]["text-2"],
                            width=SPACE["xl"] * 12, max_w=SPACE["xl"] * 12)
            doc.create_text("Trans", row.get("result", "—"), row_frame,
                            font_size=TYPE["body"], font_weight="SemiBold",
                            color=TOKENS["colors"]["text"],
                            width=SPACE["xl"] * 15, max_w=SPACE["xl"] * 15)
            doc.create_text("Fit", "%s%%" % row.get("fit", 95), row_frame,
                            font_size=TYPE["caption"], font_family=FONTS["font_mono"],
                            color=TOKENS["colors"]["status-success"],
                            width=SPACE["xl"] * 3, max_w=SPACE["xl"] * 3)
            doc.build_badge("Status", text(row.get("status", "status")), row_frame,
                            tone="status-success" if row.get("done") else "status-warn")
        return table

    @staticmethod
    def add_mobile_drawer_sheet(doc: FigcraftDocument, parent_id: int,
                                title: Optional[str] = None,
                                items: Optional[List[Dict[str, str]]] = None) -> int:
        """Bottom drawer composed from the same field/button components."""
        spec = BLOCKS.get("drawer", {})
        sheet = doc.create_frame(
            "MobileDrawerSheet", parent_id, spec.get("width", SPACE["xl"] * 14),
            spec.get("height", SPACE["xl"] * 18),
            fill=TOKENS["colors"]["surface-2"], stroke=TOKENS["colors"]["line"],
            corner_radius=tokr("window"), layout_mode="vertical", gap=SPACE["sm"],
            padding=(SPACE["sm"], SPACE["lg"], SPACE["lg"], SPACE["lg"]),
            sizing_h="fixed", sizing_v="hug",
        )
        doc.create_rect("GrabHandle", sheet, SPACE["xl"] * 2, SPACE["xs"],
                        fill=TOKENS["colors"]["data-technical"],
                        corner_radius=SPACE["xs"] / 2.0)
        head = doc.create_frame("DrawerHeader", sheet, SPACE["xl"] * 14, TYPE["display"],
                                layout_mode="horizontal", main_align="spaceBetween",
                                cross_align="center", sizing_h="fill", sizing_v="hug")
        doc.create_text("DrawerTitle", title or text("quick_settings"), head,
                        font_size=TYPE["heading"], font_weight="Bold",
                        font_family=FONTS["font_brand"], color=TOKENS["colors"]["text"])
        doc.build_badge("BadgeMbl", text("mobile"), head, tone="action-primary")
        for item in items or []:
            frame = doc.create_frame(
                "Item_" + str(item.get("key", "action")), sheet,
                SPACE["xl"] * 14, spec.get("item", SPACE["xl"] * 3),
                fill=TOKENS["colors"]["raised"], stroke=TOKENS["colors"]["line"],
                corner_radius=tokr("control"), layout_mode="horizontal",
                padding=(SPACE["sm"], SPACE["md"], SPACE["sm"], SPACE["md"]),
                main_align="spaceBetween", cross_align="center",
                sizing_h="fill", sizing_v="fixed",
            )
            doc.create_text("Label", text(item.get("key", "action")), frame,
                            font_size=TYPE["body"], font_weight="SemiBold",
                            color=TOKENS["colors"]["text"])
            doc.build_button("CTA", text(item.get("cta", "submit")), frame,
                             variant=item.get("variant", "default"), size="sm")
        return sheet


def tokr(role_or_scale: str) -> float:
    """Resolve a radius token by semantic role or primitive scale name."""
    if role_or_scale in TOKENS["radii"]:
        return TOKENS["radii"][role_or_scale]
    radii = DESIGN_DOC["tokens"]["primitive"]["radius"]
    return radii.get(role_or_scale, radii["xs"])


# ---------------------------------------------------------------------------
# LIVE GENERATE — Components / Screen / Form, driven by style_direction
# ---------------------------------------------------------------------------
def generate_components(doc: FigcraftDocument, parent_id: int = 1,
                        style: Optional[str] = None) -> int:
    """Build a component library by duplicating base components (refine, not rebuild)."""
    lever = levers(style)
    root = doc.create_frame(
        "Components", parent_id, SCREEN_W, SCREEN_H,
        fill=TOKENS["colors"]["surface"], corner_radius=tokr("window"),
        layout_mode="vertical", gap=lever["gap"],
        padding=(lever["pad"], lever["pad"], lever["pad"], lever["pad"]),
        clip=True, sizing_h="fill", sizing_v="fill",
    )
    doc.create_text("LibraryTitle", text("components"), root,
                    font_size=TYPE["display"], font_weight="Bold",
                    font_family=FONTS["font_brand"], color=TOKENS["colors"]["text"])

    row = doc.create_frame("ButtonVariants", root, SCREEN_W - SPACE["xl"] * 2,
                           TOKENS["sizes"]["btn_lg"] + SPACE["md"],
                           layout_mode="horizontal", gap=lever["gap"],
                           cross_align="center", sizing_h="fill", sizing_v="hug")
    base = doc.build_button("BtnBase", text("submit"), row, variant="primary", size="md")
    doc.component_first(base, row, name="BtnSecondary",
                        overrides={"fills": ft.make_solid_fill(TOKENS["colors"]["surface-2"])})
    doc.component_first(base, row, name="BtnGhost",
                        overrides={"fills": []})
    doc.build_badge("BadgeTechnical", "ID 42", row, tone="data-technical")
    doc.build_badge("BadgePrimary", text("status"), row, tone="action-primary")
    doc.build_badge("BadgeSuccess", text("status"), row, tone="status-success")
    doc.prevent_clipping(root)
    return root


def generate_form(doc: FigcraftDocument, parent_id: int = 1,
                  style: Optional[str] = None, fields: Optional[List[str]] = None,
                  width: Optional[float] = None, height: Optional[float] = None) -> int:
    """Build a form from component.field / component.button tokens."""
    lever = levers(style)
    form_w = width or SCREEN_W
    form_h = height or SCREEN_H
    root = doc.create_frame(
        "Form", parent_id, form_w, form_h,
        fill=TOKENS["colors"]["surface"], corner_radius=tokr("window"),
        layout_mode="vertical", gap=lever["gap"],
        padding=(lever["pad"], lever["pad"], lever["pad"], lever["pad"]),
        clip=True, sizing_h="fill", sizing_v="fill",
    )
    doc.create_text("FormTitle", text("submit"), root,
                    font_size=TYPE["display"], font_weight="Bold",
                    color=TOKENS["colors"]["text"])
    for key in fields or ["field_name", "field_email", "field_notes"]:
        field = doc.create_frame(
            "Field_" + key, root, max(SPACE["xl"] * 4, form_w - SPACE["xl"] * 2),
            COMPONENT["field"]["height"], fill=TOKENS["colors"]["surface-2"],
            stroke=TOKENS["colors"]["line"], corner_radius=tokr("control"),
            layout_mode="horizontal", cross_align="center",
            padding=(0.0, SPACE["sm"], 0.0, SPACE["sm"]),
            sizing_h="fill", sizing_v="fixed",
        )
        doc.create_text("Label", text(key), field, font_size=TYPE["body"],
                        color=TOKENS["colors"]["text-2"])
    actions = doc.create_frame("FormActions", root,
                               max(SPACE["xl"] * 4, form_w - SPACE["xl"] * 2),
                               TOKENS["sizes"]["btn_md"] + SPACE["sm"],
                               layout_mode="horizontal", gap=lever["gap"],
                               main_align="max", cross_align="center",
                               sizing_h="fill", sizing_v="hug")
    doc.build_button("BtnCancel", text("cancel"), actions, variant="ghost", size="md")
    doc.build_button("BtnSubmit", text("submit"), actions, variant="primary", size="md")
    doc.prevent_clipping(root)
    return root


def generate_screen(doc: FigcraftDocument, x: float = 0.0, y: float = 0.0,
                    style: Optional[str] = None, name: Optional[str] = None) -> int:
    """Build one screen whose topology follows the selected style direction."""
    lever = levers(style)
    screen_id = doc.create_frame(
        name or text("screen"), 1, SCREEN_W, SCREEN_H, x=x, y=y,
        fill=TOKENS["colors"]["surface"], corner_radius=tokr("window"),
        layout_mode="vertical", gap=0.0, clip=True,
    )
    DesignBlocks.add_app_header(doc, screen_id)

    body = doc.create_frame("Body", screen_id, SCREEN_W, SCREEN_H - TOKENS["sizes"]["header"],
                            layout_mode="horizontal", gap=0.0,
                            sizing_h="fill", sizing_v="fill")
    if lever["rail"]:
        rail = doc.create_frame("Rail", body, BLOCKS.get("railWidth", SPACE["xl"] * 8),
                                SCREEN_H - TOKENS["sizes"]["header"],
                                fill=TOKENS["colors"]["surface-2"],
                                stroke=TOKENS["colors"]["line"],
                                layout_mode="vertical", gap=lever["gap"],
                                padding=(SPACE["sm"], SPACE["sm"], SPACE["sm"], SPACE["sm"]),
                                sizing_h="fixed", sizing_v="fill")
        for index in range(lever["columns"]):
            doc.create_text("RailItem_%d" % index, "%s %d" % (text("page"), index + 1),
                            rail, font_size=TYPE["caption"],
                            color=TOKENS["colors"]["text-2"])
    if lever["inspector"]:
        inspector = doc.create_frame("Inspector", body,
                                     BLOCKS.get("inspectorWidth", SPACE["xl"] * 12),
                                     SCREEN_H - TOKENS["sizes"]["header"],
                                     fill=TOKENS["colors"]["surface-2"],
                                     stroke=TOKENS["colors"]["line"],
                                     layout_mode="vertical", gap=lever["gap"],
                                     padding=(SPACE["sm"], SPACE["sm"], SPACE["sm"], SPACE["sm"]),
                                     sizing_h="fixed", sizing_v="fill")
        doc.create_text("InspectorTitle", text("status"), inspector,
                        font_size=TYPE["heading"], font_weight="Bold",
                        color=TOKENS["colors"]["text"])

    rail_w = BLOCKS.get("railWidth", SPACE["xl"] * 8) if lever["rail"] else 0
    inspector_w = BLOCKS.get("inspectorWidth", SPACE["xl"] * 12) if lever["inspector"] else 0
    canvas_w = SCREEN_W - rail_w - inspector_w
    canvas = doc.create_frame("Canvas", body, canvas_w,
                              SCREEN_H - TOKENS["sizes"]["header"],
                              fill=TOKENS["colors"]["bg"],
                              layout_mode="vertical", gap=lever["gap"],
                              padding=(lever["pad"], lever["pad"], lever["pad"], lever["pad"]),
                              sizing_h="fill", sizing_v="fill")
    if style in ("clean_utility", "custom"):
        generate_form(doc, canvas, style=style,
                      width=canvas_w - lever["pad"] * 2,
                      height=SCREEN_H - TOKENS["sizes"]["header"] - lever["pad"] * 2)
    elif style == "editorial":
        doc.create_text("ArticleTitle", text("screen"), canvas,
                        font_size=TYPE["display"], font_weight="Bold",
                        font_family=FONTS["font_brand"], color=TOKENS["colors"]["text"])
        doc.create_text("ArticleBody", text("empty_desc"), canvas,
                        font_size=TYPE["body"], color=TOKENS["colors"]["text-2"],
                        width=SCREEN_W / 2.0, max_w=SCREEN_W / 2.0)
    else:
        grid = doc.create_frame("Cards", canvas,
                                max(SPACE["xl"] * 4, canvas_w - lever["pad"] * 2),
                                SCREEN_H / 2.0, layout_mode="horizontal",
                                gap=lever["gap"], sizing_h="fill", sizing_v="hug")
        for index in range(lever["columns"]):
            card_w = max(SPACE["xl"] * 4,
                         (canvas_w - lever["pad"] * 2 - lever["gap"]
                          * (lever["columns"] - 1)) / lever["columns"])
            card = doc.create_frame("Card_%d" % index, grid, card_w,
                                    SCREEN_H / 3.0,
                                    fill=TOKENS["colors"]["raised"],
                                    stroke=TOKENS["colors"]["line"],
                                    corner_radius=tokr("card"),
                                    layout_mode="vertical", gap=lever["gap"],
                                    padding=(lever["pad"], lever["pad"], lever["pad"], lever["pad"]),
                                    sizing_h="fill", sizing_v="fixed")
            doc.create_text("CardTitle", text("card"), card,
                            font_size=TYPE["heading"], font_weight="Bold",
                            color=TOKENS["colors"]["text"])
            doc.create_text("CardBody", text("empty_desc"), card,
                            font_size=TYPE["caption"], color=TOKENS["colors"]["text-2"],
                            width=max(SPACE["xl"] * 2, card_w - lever["pad"] * 2),
                            max_w=max(SPACE["xl"] * 2, card_w - lever["pad"] * 2))
    doc.prevent_clipping(screen_id)
    return screen_id


def generate_live(kind: str, doc_name: str, style: Optional[str] = None,
                  theme: Optional[str] = None) -> FigcraftDocument:
    """Create a document containing one Live Generate artifact."""
    use_theme(theme)
    doc = FigcraftDocument(doc_name)
    if kind == "components":
        generate_components(doc, style=style)
    elif kind == "form":
        generate_form(doc, style=style)
    elif kind == "screen":
        generate_screen(doc, style=style)
    else:
        raise DesignManifestError("Unknown Live Generate kind %r." % kind)
    return doc


# ---------------------------------------------------------------------------
# PRESET GENERATORS
# ---------------------------------------------------------------------------
def generate_preset(preset_name: str, doc_name: str = "QuickDesign") -> FigcraftDocument:
    """Generate a complete preset document from tokens."""
    doc = FigcraftDocument(doc_name)
    if preset_name == "dashboard":
        screen = doc.create_frame(text("project_dashboard"), 1, SCREEN_W, SCREEN_H,
                                  fill=TOKENS["colors"]["surface"],
                                  corner_radius=tokr("window"), layout_mode="vertical",
                                  gap=BLOCKS.get("screenGap", SPACE["lg"]),
                                  padding=(0.0, 0.0, SPACE["lg"], 0.0), clip=True)
        doc.build_window_bar(screen, title=text("app_name"))
        DesignBlocks.add_app_header(doc, screen, page_info=text("status"))
        content = doc.create_frame("ContentArea", screen, SCREEN_W, SCREEN_H - SPACE["xl"] * 6,
                                   layout_mode="vertical",
                                   gap=BLOCKS.get("contentGap", SPACE["lg"]),
                                   padding=(0.0, SPACE["lg"], 0.0, SPACE["lg"]),
                                   sizing_h="fill", sizing_v="fill")
        stats = [
            {"key": "total", "value": "128", "desc": text("status"),
             "badge": "status", "tone": "data-technical"},
            {"key": "detected", "value": "3,420", "desc": text("status"),
             "badge": "status", "tone": "data-technical"},
            {"key": "duration", "value": "4.2m", "desc": text("status"),
             "badge": "status", "tone": "status-success"},
            {"key": "ready", "value": "6", "desc": text("status"),
             "badge": "status", "tone": "action-primary"},
        ]
        DesignBlocks.add_stats_grid(doc, content, stats)
        doc.create_text("SecTitle", text("new_project").upper(), content,
                        font_size=TYPE["body"], font_weight="Bold",
                        color=TOKENS["colors"]["action-primary"])
        projects = [
            {"key": "project_one", "pages": 41, "bubbles": 218, "mode": "status",
             "status": "status", "progress": 82, "active": True},
            {"key": "project_two", "pages": 28, "bubbles": 142, "mode": "status",
             "status": "status", "progress": 45},
            {"key": "project_three", "pages": 34, "bubbles": 190, "mode": "status",
             "status": "status", "progress": 100, "done": True},
        ]
        DesignBlocks.add_project_cards_grid(doc, content, projects)
    elif preset_name == "ledger":
        screen = doc.create_frame(text("translation_ledger"), 1, SCREEN_W, SCREEN_H,
                                  fill=TOKENS["colors"]["surface"],
                                  corner_radius=tokr("window"), layout_mode="vertical",
                                  gap=BLOCKS.get("screenGap", SPACE["lg"]),
                                  padding=(0.0, 0.0, SPACE["lg"], 0.0), clip=True)
        doc.build_window_bar(screen, title=text("app_name"))
        DesignBlocks.add_app_header(doc, screen, page_info=text("status"))
        content = doc.create_frame("ContentArea", screen, SCREEN_W, SCREEN_H - SPACE["xl"] * 6,
                                   layout_mode="vertical", gap=SPACE["sm"],
                                   padding=(0.0, SPACE["lg"], 0.0, SPACE["lg"]),
                                   sizing_h="fill", sizing_v="fill")
        search = doc.create_frame("SearchBox", content, SCREEN_W / 4.0,
                                  TOKENS["sizes"]["field"],
                                  fill=TOKENS["colors"]["raised"],
                                  stroke=TOKENS["colors"]["line"],
                                  corner_radius=tokr("control"),
                                  layout_mode="horizontal",
                                  padding=(0.0, SPACE["sm"], 0.0, SPACE["sm"]),
                                  cross_align="center", sizing_h="hug", sizing_v="fixed")
        doc.create_text("SearchTxt", text("search"), search,
                        font_size=TYPE["caption"], color=TOKENS["colors"]["text-3"])
        DesignBlocks.add_ledger_table(doc, content, [
            {"page": 4, "original": "—", "result": "—", "fit": 94, "status": "status", "done": True},
            {"page": 4, "original": "—", "result": "—", "fit": 88, "status": "status"},
            {"page": 5, "original": "—", "result": "—", "fit": 90, "status": "status"},
        ])
    elif preset_name == "drawer":
        screen = doc.create_frame(text("mobile"), 1,
                                  BLOCKS.get("drawer", {}).get("width", SCREEN_W / 3),
                                  BLOCKS.get("drawer", {}).get("height", SCREEN_H),
                                  fill=CONTENT.get("scrim", TOKENS["colors"]["bg"]),
                                  corner_radius=tokr("window"), clip=True)
        DesignBlocks.add_mobile_drawer_sheet(doc, screen, items=[
            {"key": "detect_bubbles", "cta": "retry"},
            {"key": "translate_all", "cta": "submit", "variant": "primary"},
        ])
    else:
        from figcraft_tool import build_workbench_screen
        build_workbench_screen(doc, x=SPACE["xl"] * 2, y=SPACE["xl"] * 2)
    return doc


# ---------------------------------------------------------------------------
# CLI + AUTO-RENDER PREVIEW
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="FigCraft QuickDesign: token-driven UI generator with PNG previews"
    )
    parser.add_argument("prompt", nargs="?", default="", help="Design brief (free text)")
    parser.add_argument("-p", "--preset",
                        choices=["workbench", "dashboard", "ledger", "drawer"],
                        default="workbench", help="Template preset")
    parser.add_argument("--generate", choices=["components", "screen", "form"],
                        help="Live Generate artifact to build inside the document")
    parser.add_argument("--style", choices=sorted(STYLE_DIRECTIONS),
                        help="Override style_direction for this generation")
    parser.add_argument("--theme", choices=["dark", "light"],
                        help="Override theme for this generation")
    parser.add_argument("-o", "--output", required=True, help="Output .figcraft path")
    parser.add_argument("--preview", action="store_true", help="Render a PNG preview")
    parser.add_argument("--port", type=int, default=9880,
                        help="Control port (default 9880, shared with agent_terminal)")
    args = parser.parse_args()

    if args.generate:
        selected = args.generate
        print("\n[QuickDesign] Live Generate: %s (style=%s, locale=%s, tone=%s)"
              % (selected.upper(), args.style or STYLE, LOCALE, COPY_TONE))
        doc = generate_live(selected, args.prompt or text("screen"),
                            style=args.style, theme=args.theme)
    else:
        prompt = args.prompt.lower()
        selected = args.preset
        if "dash" in prompt or "project" in prompt or "card" in prompt:
            selected = "dashboard"
        elif "ledger" in prompt or "table" in prompt or "review" in prompt:
            selected = "ledger"
        elif "drawer" in prompt or "sheet" in prompt or "mobile" in prompt:
            selected = "drawer"
        elif "workbench" in prompt or "editor" in prompt:
            selected = "workbench"
        print("\n[QuickDesign] Generating: %s (style=%s)" % (selected.upper(), STYLE))
        use_theme(args.theme)
        doc = generate_preset(selected, args.prompt or text("app_name"))

    for warning in lint_design(doc):
        print("[lint] %s" % warning, file=sys.stderr)
    doc.save(args.output)
    print("Created .figcraft file: %s" % args.output)

    if args.preview:
        out_base, _ = os.path.splitext(args.output)
        preview_png = out_base + "_preview.png"
        app_bin = os.environ.get("FIGCRAFT_APP", "/Applications/FigCraft.app/Contents/MacOS/FigCraft")
        if not os.path.exists(app_bin):
            print("Preview skipped: FigCraft binary not found at %s "
                  "(set FIGCRAFT_APP to override)." % app_bin)
        else:
            abs_fig = os.path.abspath(args.output)
            abs_png = os.path.abspath(preview_png)
            work_dir = os.path.dirname(abs_fig)
            cmd = [app_bin, "--control", str(args.port),
                   "--automation-read-root", work_dir,
                   "--automation-write-root", work_dir, abs_fig]
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            client = FigcraftClient(port=args.port)
            rendered = False
            try:
                time.sleep(1.2)
                if client.connect(timeout=2.0):
                    info = client.document_inspect()
                    pages = info.get("result", {}).get("pages", [])
                    if pages and pages[0].get("children"):
                        node_id = pages[0]["children"][0].get("id")
                        if node_id:
                            rendered = bool(client.export_frame(
                                node_id, abs_png, format="png", scale=1.0).get("ok"))
            except Exception as exc:  # preview is best-effort
                print("Warning: render error: %s" % exc)
            finally:
                client.close()
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except Exception:
                    proc.kill()
            print("Preview exported: %s" % preview_png if rendered
                  else "Preview unavailable; open the file in FigCraft.")

    print("Done. Ready to inspect or iterate.\n")


if __name__ == "__main__":
    main()
