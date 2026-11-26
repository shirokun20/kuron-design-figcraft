#!/usr/bin/env python3
"""FigCraft QuickDesign — token-driven rapid UI generator (3.2.3).

Every colour, font size, spacing step, component size, and microcopy string is
resolved from the project's ``DESIGN.md`` through ``design_manifest.py``. The
``--generate`` flag builds Components, Screen, or Form nodes for Live Generate
sessions, and the layout is driven by ``style_direction``. The ``three-pages``
preset puts ``00_Foundations``, ``01_Components``, and ``02_Screens`` on their
own pages; the legacy ``three-board`` preset keeps them adjacent on the selected
page of ``pages[0..N]``. Screens duplicate existing components across pages
instead of rebuilding them.

Every generated node gets a descriptive English name and visible label, and
wrapper cards fit their content with proportional padding (audit rules S-15/S-16).
All network operations use timeouts; the preview worker is always terminated.
"""

import argparse
import os
import sys
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

# Board-level constants: the horizontal gap is derived from the token scale,
# not hardcoded, so a different DESIGN.md keeps the same rhythm automatically.
BOARD_GAP = SPACE["xl"] * 5
BOARD_X = SPACE["xl"] * 2
BOARD_Y = SPACE["xl"] * 2
BOARD_NAMES = ("00_Foundations", "01_Components", "02_Screens")


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
def retarget_duplicate_label(doc: FigcraftDocument, node_id: Optional[int],
                             label: str, color: Optional[str] = None) -> None:
    """Update the text label inside a duplicated button/badge subtree.

    Only the fresh copy is touched; the source template is never mutated. The
    text keeps hug sizing so save-time auto-layout measures the new copy and
    resizes the duplicated control to fit it.
    """
    if node_id is None:
        return
    root = doc.doc["nodes"].get(str(node_id), {})
    for child_id in root.get("children", []) or []:
        child = doc.doc["nodes"].get(str(child_id), {})
        if child.get("type") != "text" or child.get("name") not in (
                "label", "text", "BadgeLabel"):
            continue
        child["characters"] = label
        # The node keeps its hug sizing; save-time reflow measures the new copy
        # and resizes the parent control, so no pre-emptive width is stored.
        if color:
            child["fills"] = ft.make_solid_fill(color)
        return


def generate_components(doc: FigcraftDocument, parent_id: int = 1,
                        style: Optional[str] = None) -> int:
    """Build a component library by duplicating base components (refine, not rebuild)."""
    lever = levers(style)
    content_w = SCREEN_W - SPACE["xl"] * 2
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

    buttons = doc.create_frame(
        "ButtonVariants", root, content_w, TOKENS["sizes"]["btn_lg"] + SPACE["md"],
        layout_mode="horizontal", gap=lever["gap"], main_align="spaceBetween",
        cross_align="center", sizing_h="fill", sizing_v="fixed")
    primary = doc.build_button("BtnPrimary", text("submit"), buttons,
                               variant="primary", size="md")
    secondary = doc.component_first(
        primary, buttons, name="BtnSecondary",
        overrides={"fills": ft.make_solid_fill(TOKENS["colors"]["surface-2"])})
    retarget_duplicate_label(doc, secondary, text("save_changes"),
                             TOKENS["colors"]["text"])
    ghost = doc.component_first(primary, buttons, name="BtnGhost",
                                overrides={"fills": []})
    retarget_duplicate_label(doc, ghost, text("cancel"),
                             TOKENS["colors"]["text-2"])

    badges = doc.create_frame(
        "BadgeVariants", root, content_w,
        float(COMPONENT["badge"]["height"]) + SPACE["md"],
        layout_mode="horizontal", gap=lever["gap"], main_align="spaceBetween",
        cross_align="center", sizing_h="fill", sizing_v="fixed")
    success = doc.build_badge("BadgeSuccess", text("status_ready"), badges,
                              tone="status-success")
    danger = doc.component_first(
        success, badges, name="BadgeDanger",
        overrides={"fills": ft.make_solid_fill(TOKENS["colors"]["status-danger-soft"])})
    retarget_duplicate_label(doc, danger, text("status_error"),
                             TOKENS["colors"]["status-danger"])

    # A fill spacer pushes the specimen footer to the bottom so real content
    # (not an empty wrapper) spans the whole canvas.
    doc.create_frame("LibrarySpacer", root, content_w, SPACE["xs"],
                     sizing_h="fill", sizing_v="fill")
    footer = doc.create_frame(
        "LibraryFooter", root, content_w, TYPE["body"] + SPACE["md"],
        layout_mode="horizontal", gap=lever["gap"], main_align="spaceBetween",
        cross_align="center", sizing_h="fill", sizing_v="fixed")
    doc.create_text("FooterBrand", text("app_name"), footer,
                    font_size=TYPE["caption"], color=TOKENS["colors"]["text-2"])
    doc.create_text("FooterContext", text("project_dashboard"), footer,
                    font_size=TYPE["caption"], color=TOKENS["colors"]["text-2"])
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
    # Fill spacer keeps the actions near the bottom so visible leaf content
    # spans the canvas instead of clustering under the title.
    doc.create_frame("FormSpacer", root,
                     max(SPACE["xl"] * 4, form_w - SPACE["xl"] * 2), SPACE["xs"],
                     sizing_h="fill", sizing_v="fill")
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
    inner_w = max(SPACE["xl"] * 4, canvas_w - lever["pad"] * 2)
    canvas_h = SCREEN_H - TOKENS["sizes"]["header"]
    grid_h = canvas_h - lever["pad"] * 2
    if style in ("clean_utility", "custom"):
        generate_form(doc, canvas, style=style, width=inner_w,
                      height=SCREEN_H - TOKENS["sizes"]["header"] - lever["pad"] * 2)
    elif style == "editorial":
        doc.create_text("ArticleTitle", text("screen"), canvas,
                        font_size=TYPE["display"], font_weight="Bold",
                        font_family=FONTS["font_brand"], color=TOKENS["colors"]["text"])
        article_w = min(SCREEN_W / 2.0, inner_w)
        doc.create_text("ArticleBody", text("empty_desc"), canvas,
                        font_size=TYPE["body"], color=TOKENS["colors"]["text-2"],
                        width=article_w, max_w=article_w)
        doc.create_frame("ArticleSpacer", canvas, inner_w, SPACE["xs"],
                         sizing_h="fill", sizing_v="fill")
        footer = doc.create_frame(
            "ArticleFooter", canvas, inner_w, TYPE["body"] + SPACE["md"],
            layout_mode="horizontal", gap=lever["gap"], main_align="spaceBetween",
            cross_align="center", sizing_h="fill", sizing_v="fixed")
        doc.create_text("FooterBrand", text("app_name"), footer,
                        font_size=TYPE["caption"], color=TOKENS["colors"]["text-2"])
        doc.create_text("FooterContext", text("project_dashboard"), footer,
                        font_size=TYPE["caption"], color=TOKENS["colors"]["text-2"])
    else:
        grid = doc.create_frame(
            "Cards", canvas, inner_w, grid_h, layout_mode="horizontal",
            gap=lever["gap"], main_align="spaceBetween",
            sizing_h="fill", sizing_v="fixed")
        for index in range(lever["columns"]):
            card_w = max(SPACE["xl"] * 4,
                         (inner_w - lever["gap"] * (lever["columns"] - 1))
                         / lever["columns"])
            card = doc.create_frame(
                "Card_%d" % index, grid, card_w, grid_h,
                fill=TOKENS["colors"]["raised"], stroke=TOKENS["colors"]["line"],
                corner_radius=tokr("card"), layout_mode="vertical", gap=lever["gap"],
                padding=(lever["pad"], lever["pad"], lever["pad"], lever["pad"]),
                sizing_h="fill", sizing_v="fixed")
            doc.create_text("CardTitle", text("card"), card,
                            font_size=TYPE["heading"], font_weight="Bold",
                            color=TOKENS["colors"]["text"])
            body_w = max(SPACE["xl"] * 2, card_w - lever["pad"] * 2)
            doc.create_text("CardBody", text("empty_desc"), card,
                            font_size=TYPE["caption"], color=TOKENS["colors"]["text-2"],
                            width=body_w, max_w=body_w)
            doc.create_frame("CardSpacer", card,
                             max(SPACE["xs"], card_w - lever["pad"] * 2), SPACE["xs"],
                             sizing_h="fill", sizing_v="fill")
            doc.create_text(
                "CardFooter",
                text("status_ready") if index % 2 == 0 else text("status_error"),
                card, font_size=TYPE["caption"], color=TOKENS["colors"]["text-2"])
    doc.prevent_clipping(screen_id)
    return screen_id


# ---------------------------------------------------------------------------
# THREE-BOARD DESIGN SYSTEM (00_Foundations / 01_Components / 02_Screens)
# ---------------------------------------------------------------------------
def hex_of(color: str) -> str:
    """Return the canonical hex of a token colour for a swatch caption."""
    return ft._lint_hex(ft.make_solid_fill(color)[0]["color"])


def build_foundations(doc: FigcraftDocument, board_id: int,
                      width: Optional[float] = None,
                      height: Optional[float] = None) -> int:
    """Fill a Foundations board with colour, type, spacing, and radius tokens.

    Every value is resolved from DESIGN.md through the shared builder tokens.
    The board is a normal top-level frame on whichever page the caller chose,
    so it stays visible alongside its sibling boards in every tool.
    """
    board = doc.doc["nodes"][str(board_id)]
    board_w = float(width or board.get("width", SCREEN_W))
    board_h = float(height or board.get("height", SCREEN_H))
    pad = SPACE["xl"]
    inner = board_w - pad * 2
    col_w = inner / 2.0
    right_x = pad + inner / 2 + SPACE["lg"]
    colors = TOKENS["colors"]

    doc.create_text(
        "FoundationTitle", "00_Foundations", board_id,
        font_size=TYPE["display"], font_weight="Bold",
        font_family=FONTS["font_brand"], color=colors["text"],
        x=pad, y=pad, width=inner,
    )
    y = pad * 3
    doc.create_text(
        "ColorRolesTitle", "COLOR ROLES", board_id,
        font_size=TYPE["caption"], font_weight="Bold",
        color=colors["text-2"], x=pad, y=y, width=col_w,
    )
    y += TYPE["caption"] + SPACE["sm"]

    # Semantic roles only: primitive hex values are shown through the role
    # that consumes them, keeping the board a contract rather than a palette dump.
    roles = (
        "bg", "surface", "raised", "line", "text", "text-2",
        "action-primary", "action-primary-fg", "data-technical",
        "status-success", "status-warn", "status-danger",
    )
    row_h = TYPE["caption"] + SPACE["xs"]
    for role in roles:
        fill = colors[role]
        row = doc.create_frame(
            "Swatch_" + role, board_id, col_w, row_h,
            x=pad, y=y, layout_mode="horizontal", gap=SPACE["sm"],
            cross_align="center", sizing_h="fill", sizing_v="fixed",
        )
        doc.create_rect(
            "SwatchPaint", row, SPACE["xl"] * 2, TYPE["caption"] + SPACE["xs"],
            fill=fill, stroke=colors["line"], stroke_width=1.0,
            corner_radius=tokr("control"),
        )
        doc.create_text(
            "SwatchLabel", "%s  %s" % (role, hex_of(fill)), row,
            font_size=TYPE["caption"], font_family=FONTS["font_mono"],
            color=colors["text-2"], width=col_w - SPACE["xl"] * 3,
        )
        y += row_h + SPACE["xxs"]

    # The right column starts level with COLOR ROLES and uses the same token
    # rhythm, so the two columns read as one balanced composition.
    right_y = pad * 3
    doc.create_text(
        "TypeScaleTitle", "TYPOGRAPHY SCALE", board_id,
        font_size=TYPE["caption"], font_weight="Bold",
        color=colors["text-2"], x=right_x, y=right_y, width=col_w,
    )
    right_y += TYPE["caption"] + SPACE["sm"]
    for key in ("display", "heading", "body", "caption", "mono"):
        size = TYPE[key]
        family = FONTS["font_mono"] if key == "mono" else FONTS["font_ui"]
        doc.create_text(
            "Type_" + key, "%s  %dpx" % (key.upper(), size), board_id,
            font_size=size, font_family=family,
            font_weight="Bold" if key in ("display", "heading") else "Regular",
            color=colors["text"], x=right_x, y=right_y, width=col_w,
        )
        right_y += max(size + SPACE["xs"], TYPE["body"] + SPACE["sm"])

    right_y += SPACE["sm"]
    doc.create_text(
        "TokenTitle", "SPACING & RADIUS TOKENS", board_id,
        font_size=TYPE["caption"], font_weight="Bold",
        color=colors["text-2"], x=right_x, y=right_y, width=col_w,
    )
    right_y += TYPE["caption"] + SPACE["sm"]
    token_w = max(SPACE["xl"] * 4, col_w / 8.0)
    for key in ("xxs", "xs", "sm", "md", "lg", "xl"):
        doc.create_rect(
            "Space_" + key, board_id, SPACE[key], SPACE["xs"],
            fill=colors["selected"], corner_radius=SPACE["xxs"] / 2.0,
            x=right_x, y=right_y + (TYPE["caption"] - SPACE["xs"]) / 2.0,
        )
        doc.create_text(
            "SpaceLabel_" + key, "space.%s = %d" % (key, SPACE[key]), board_id,
            font_size=TYPE["caption"], font_family=FONTS["font_mono"],
            color=colors["text-2"], x=right_x + token_w, y=right_y,
            width=col_w - token_w,
        )
        right_y += TYPE["caption"] + SPACE["xxs"]
    for role, radius in TOKENS["radii"].items():
        doc.create_rect(
            "Radius_" + role, board_id,
            min(token_w / 2.0, SPACE["xl"] * 3), max(TYPE["caption"], SPACE["xl"]),
            fill=colors["surface-2"], corner_radius=float(radius),
            x=right_x, y=right_y,
        )
        doc.create_text(
            "RadiusLabel_" + role, "radius.%s = %s" % (role, radius), board_id,
            font_size=TYPE["caption"], font_family=FONTS["font_mono"],
            color=colors["text-2"], x=right_x + token_w, y=right_y,
            width=col_w - token_w,
        )
        right_y += max(TYPE["caption"], SPACE["xl"]) + SPACE["xxs"]

    footer_h = TYPE["caption"] + SPACE["sm"]
    doc.create_text(
        "FoundationFooter", "source: DESIGN.md / design-contract/v1", board_id,
        font_size=TYPE["caption"], color=colors["text-2"],
        x=pad, y=max(max(y, right_y) + SPACE["sm"], board_h - pad - footer_h),
        width=inner, height=footer_h,
    )
    return board_id


def generate_screen_from_components(doc: FigcraftDocument, screen_id: int,
                                    components_board: int,
                                    style: Optional[str] = None) -> int:
    """Build a screen whose repeated controls are duplicates of board 01."""
    lever = levers(style)
    colors = TOKENS["colors"]
    DesignBlocks.add_app_header(doc, screen_id)
    header_h = TOKENS["sizes"]["header"]
    inner = SCREEN_W - lever["pad"] * 2
    body = doc.create_frame(
        "Body", screen_id, SCREEN_W, SCREEN_H - header_h,
        layout_mode="vertical", gap=lever["gap"],
        padding=(lever["pad"], lever["pad"], lever["pad"], lever["pad"]),
        sizing_h="fill", sizing_v="fill",
    )
    doc.create_text(
        "ReuseTitle", text("components"), body,
        font_size=TYPE["heading"], font_weight="Bold", color=colors["text"],
    )
    strip = doc.create_frame(
        "ReusedComponents", body, inner, SCREEN_H / 2.0,
        layout_mode="horizontal", gap=lever["gap"], main_align="spaceBetween",
        cross_align="center", sizing_h="fill", sizing_v="fixed",
    )
    for template, label in (
        ("BtnPrimary", "ReusedPrimary"),
        ("BtnSecondary", "ReusedSecondary"),
        ("BadgeSuccess", "ReusedBadge"),
        ("Card", "ReusedCard"),
    ):
        source = ft.find_or_reuse_component(doc, template, parent_id=components_board)
        if source is not None:
            doc.duplicate_node(source, parent_id=strip, name=label)
    # A fill spacer pushes real content to the bottom of the screen so the
    # whole board is utilised rather than leaving a hollow lower half.
    doc.create_frame("ReuseSpacer", body, inner, SPACE["xs"],
                     sizing_h="fill", sizing_v="fill")
    footer = doc.create_frame(
        "ReuseFooter", body, inner, TYPE["body"] + SPACE["md"],
        layout_mode="horizontal", gap=lever["gap"], main_align="spaceBetween",
        cross_align="center", sizing_h="fill", sizing_v="fixed",
    )
    doc.create_text("ReuseNote", text("app_name"), footer,
                    font_size=TYPE["caption"], color=colors["text-2"])
    doc.create_text("ReuseSource", BOARD_NAMES[1], footer,
                    font_size=TYPE["caption"], color=colors["text-2"])
    doc.prevent_clipping(screen_id)
    return screen_id


def generate_three_boards(doc: FigcraftDocument, style: Optional[str] = None,
                          page_index: Optional[int] = 0,
                          page_name: Optional[str] = None) -> Dict[str, int]:
    """Create the three adjacent design-system boards on a selected page.

    ``page_index`` defaults to 0 so the live canvas shows the result first, but
    any page in ``pages[0..N]`` can be targeted by index or name. Existing
    boards and components are reused, never rebuilt. Screens duplicate
    component nodes from ``01_Components`` so a change there propagates through
    every instance created by this generator.
    """
    board_w = SCREEN_W + SPACE["xl"] * 4
    board_h = SCREEN_H + SPACE["xl"] * 4
    positions = [BOARD_X + index * (board_w + BOARD_GAP) for index in range(3)]
    boards = {}
    for name, x in zip(BOARD_NAMES, positions):
        boards[name] = ft.ensure_board(
            doc, name, x=x, y=BOARD_Y, width=board_w, height=board_h,
            fill=TOKENS["colors"]["surface"], corner_radius=tokr("window"),
            clip=True, page_index=page_index, page_name=page_name,
        )

    foundations = boards[BOARD_NAMES[0]]
    if ft.find_or_reuse_component(doc, "FoundationTitle",
                                  parent_id=foundations) is None:
        build_foundations(doc, foundations, width=board_w, height=board_h)

    components = boards[BOARD_NAMES[1]]
    library = ft.find_or_reuse_component(
        doc, "Components", parent_id=components,
        builder=lambda: generate_components(doc, components, style=style),
        page_index=page_index, page_name=page_name,
    )
    if library is not None:
        # Base specimens let screens duplicate Card/Input/Row, not rebuild them.
        if ft.find_or_reuse_component(doc, "BaseSpecimens",
                                      parent_id=library) is None:
            add_base_specimens(doc, library, style)
    boards["components_library"] = int(library) if library is not None else 0

    screens = boards[BOARD_NAMES[2]]
    if ft.find_or_reuse_component(doc, "QuickDesign_Screen",
                                  parent_id=screens) is None:
        screen = doc.create_frame(
            "QuickDesign_Screen", screens, SCREEN_W, SCREEN_H,
            x=SPACE["xl"], y=SPACE["xl"] * 3,
            fill=TOKENS["colors"]["bg"], corner_radius=tokr("window"), clip=True,
        )
        generate_screen_from_components(doc, screen, components, style=style)
    return boards


def generate_three_pages(doc: FigcraftDocument, style: Optional[str] = None,
                         include_reference: bool = False) -> Dict[str, int]:
    """Create the three-board design system on three dedicated pages.

    ``pages[0]`` / ``pages[1]`` / ``pages[2]`` are named ``00_Foundations``,
    ``01_Components``, and ``02_Screens``; an optional ``01_Reference`` page
    follows at ``pages[3]``. Board ids stay stable and components are found
    across pages, so ``02_Screens`` duplicates templates from ``01_Components``
    instead of rebuilding them.
    """
    names = list(BOARD_NAMES)
    if include_reference:
        names.append("01_Reference")
    page_ids = doc.ensure_named_pages(names)
    boards: Dict[str, int] = {}
    for name, page_id in zip(BOARD_NAMES, page_ids):
        boards[name] = ft.ensure_board(
            doc, name, x=BOARD_X, y=BOARD_Y,
            width=SCREEN_W + SPACE["xl"] * 4,
            height=SCREEN_H + SPACE["xl"] * 4,
            fill=TOKENS["colors"]["surface"], corner_radius=tokr("window"),
            clip=True, page_index=page_ids.index(page_id),
        )

    foundations = boards[BOARD_NAMES[0]]
    if ft.find_or_reuse_component(doc, "FoundationTitle",
                                  parent_id=foundations) is None:
        build_foundations(doc, foundations,
                          width=SCREEN_W + SPACE["xl"] * 4,
                          height=SCREEN_H + SPACE["xl"] * 4)

    components = boards[BOARD_NAMES[1]]
    library = ft.find_or_reuse_component(
        doc, "Components", parent_id=components,
        builder=lambda: generate_components(doc, components, style=style),
        page_name=BOARD_NAMES[1],
    )
    if library is not None and ft.find_or_reuse_component(
            doc, "BaseSpecimens", parent_id=library) is None:
        add_base_specimens(doc, library, style)
    boards["components_library"] = int(library) if library is not None else 0

    screens = boards[BOARD_NAMES[2]]
    if ft.find_or_reuse_component(doc, "QuickDesign_Screen",
                                  parent_id=screens) is None:
        screen = doc.create_frame(
            "QuickDesign_Screen", screens, SCREEN_W, SCREEN_H,
            x=SPACE["xl"], y=SPACE["xl"] * 3,
            fill=TOKENS["colors"]["bg"], corner_radius=tokr("window"), clip=True,
        )
        generate_screen_from_components(doc, screen, components, style=style)
    return boards


def add_base_specimens(doc: FigcraftDocument, parent_id: int,
                       style: Optional[str] = None) -> int:
    """Add Card, Input, and Row templates available for direct duplication."""
    lever = levers(style)
    colors = TOKENS["colors"]
    width = SCREEN_W - SPACE["xl"] * 2
    specimens = doc.create_frame(
        "BaseSpecimens", parent_id, width,
        TOKENS["sizes"]["btn_lg"] + SPACE["md"],
        layout_mode="horizontal", gap=lever["gap"], main_align="spaceBetween",
        cross_align="center", sizing_h="fill", sizing_v="fixed",
    )
    card_w = SPACE["xl"] * 6
    card = doc.create_frame(
        "Card", specimens, card_w, TOKENS["sizes"]["btn_lg"] + SPACE["sm"],
        fill=colors["raised"], stroke=colors["line"],
        corner_radius=tokr("card"), clip=True,
        sizing_h="fixed", sizing_v="fixed",
    )
    doc.create_text("CardLabel", text("card"), card,
                    font_size=TYPE["caption"], color=colors["text"])
    field = doc.create_frame(
        "Input", specimens, card_w, COMPONENT["field"]["height"],
        fill=colors["surface-2"], stroke=colors["line"],
        corner_radius=tokr("control"), layout_mode="horizontal",
        cross_align="center", padding=(0.0, SPACE["sm"], 0.0, SPACE["sm"]),
        sizing_h="fixed", sizing_v="fixed",
    )
    doc.create_text("InputLabel", text("field_name"), field,
                    font_size=TYPE["caption"], color=colors["text-2"])
    row = doc.create_frame(
        "Row", specimens, card_w, TOKENS["sizes"]["btn_lg"],
        layout_mode="horizontal", gap=SPACE["sm"], cross_align="center",
        sizing_h="fixed", sizing_v="fixed",
    )
    doc.create_text("RowLabel", text("status"), row,
                    font_size=TYPE["caption"], color=colors["text-2"])
    return specimens


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
def generate_preset(preset_name: str, doc_name: str = "QuickDesign",
                    page_index: Optional[int] = 0,
                    page_name: Optional[str] = None) -> FigcraftDocument:
    """Generate a complete preset document from tokens."""
    doc = FigcraftDocument(doc_name)
    if preset_name == "three-board":
        generate_three_boards(doc, page_index=page_index, page_name=page_name)
        return doc
    if preset_name == "three-pages":
        generate_three_pages(doc)
        return doc
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
def preview_app_binary() -> str:
    """Return the FigCraft binary used for headless preview rendering."""
    return os.environ.get("FIGCRAFT_APP",
                          "/Applications/FigCraft.app/Contents/MacOS/FigCraft")


def select_inspect_page(info: Dict[str, Any], page_index: Optional[int] = 0,
                        page_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Pick a page from a live ``document.inspect`` payload by index or name."""
    pages = (info.get("result", {}).get("pages", []) or [])
    if page_name is not None:
        for page in pages:
            if isinstance(page, dict) and str(page.get("name")) == page_name:
                return page
        return None
    index = 0 if page_index is None else int(page_index)
    if 0 <= index < len(pages) and isinstance(pages[index], dict):
        return pages[index]
    return None


def export_preview(output_path: str, port: int = 9880,
                   page_index: Optional[int] = 0,
                   page_name: Optional[str] = None) -> bool:
    """Render ``<name>_preview.png`` through the live FigCraft bridge.

    Returns True only when a PNG was actually written. Every path — missing
    binary, failed launch, bad RPC, failed export — ends with an honest status
    line. A process started here is always stopped and the socket always
    closed, so no child or connection is leaked. ``page_index`` / ``page_name``
    select the page whose first board is exported.
    """
    out_base, _ = os.path.splitext(output_path)
    preview_png = out_base + "_preview.png"
    abs_fig = os.path.abspath(output_path)
    abs_png = os.path.abspath(preview_png)
    app_bin = preview_app_binary()
    if not os.path.exists(app_bin):
        print("Preview not generated: FigCraft binary unavailable at %s "
              "(set FIGCRAFT_APP). The .figcraft file is ready; no PNG was "
              "rendered." % app_bin)
        return False

    from agent_terminal import FigcraftTerminal  # lazy, stdlib-only sibling

    term = FigcraftTerminal(port=port)
    started = False
    if term.is_port_listening():
        # Reuse an existing bridge, but make sure it shows THIS document.
        opened = term.open_file(abs_fig)
        if not opened.get("ok"):
            print("Preview not generated: %s"
                  % opened.get("error", "could not open the generated file"))
            return False
    else:
        launch = term.start_server(file_path=abs_fig, wait_ready=True)
        if not launch.get("ok"):
            term.stop_server()  # a process may have been spawned before the timeout
            print("Preview not generated: %s"
                  % launch.get("error", "could not start FigCraft"))
            return False
        started = True

    client = FigcraftClient(port=port)
    rendered = False
    try:
        if client.connect(timeout=2.0):
            info = client.document_inspect()
            page = select_inspect_page(info, page_index=page_index,
                                       page_name=page_name)
            children = page.get("children", []) if page else []
            node_id = children[0].get("id") if children else None
            if node_id:
                res = client.export_frame(node_id, abs_png, format="png", scale=1.0)
                rendered = bool(res.get("ok")) and os.path.exists(abs_png)
    except Exception as exc:  # preview is best-effort, never fatal
        print("Preview not generated: render error: %s" % exc)
    finally:
        client.close()
        if started:
            term.stop_server()
    if rendered:
        print("Preview exported: %s" % preview_png)
    else:
        print("Preview not generated: no frame was exported; open the .figcraft "
              "file in FigCraft to inspect it.")
    return rendered


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FigCraft QuickDesign: token-driven UI generator with PNG previews"
    )
    parser.add_argument("prompt", nargs="?", default="", help="Design brief (free text)")
    parser.add_argument("-p", "--preset",
                        choices=["workbench", "dashboard", "ledger", "drawer",
                                 "three-board", "three-pages"],
                        default="workbench",
                        help="Template preset (three-pages = 00/01/02 on dedicated pages)")
    parser.add_argument("--generate", choices=["components", "screen", "form"],
                        help="Live Generate artifact to build inside the document")
    parser.add_argument("--style", choices=sorted(STYLE_DIRECTIONS),
                        help="Override style_direction for this generation")
    parser.add_argument("--theme", choices=["dark", "light"],
                        help="Override theme for this generation")
    parser.add_argument("-o", "--output", required=True, help="Output .figcraft path")
    parser.add_argument("--preview", action="store_true",
                        help="Render a PNG preview via the live bridge when available "
                             "(otherwise report that no PNG was generated)")
    parser.add_argument("--port", type=int, default=9880,
                        help="Control port (default 9880, shared with agent_terminal)")
    parser.add_argument("--page-index", type=int, default=0,
                        help="Target page index for generated boards (default: 0)")
    parser.add_argument("--page-name",
                        help="Target page name (overrides --page-index)")
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
        if "board" in prompt or "foundation" in prompt or "design system" in prompt:
            selected = "three-board"
        elif "dash" in prompt or "project" in prompt or "card" in prompt:
            selected = "dashboard"
        elif "ledger" in prompt or "table" in prompt or "review" in prompt:
            selected = "ledger"
        elif "drawer" in prompt or "sheet" in prompt or "mobile" in prompt:
            selected = "drawer"
        elif "workbench" in prompt or "editor" in prompt:
            selected = "workbench"
        print("\n[QuickDesign] Generating: %s (style=%s)" % (selected.upper(), STYLE))
        use_theme(args.theme)
        doc = generate_preset(selected, args.prompt or text("app_name"),
                              page_index=args.page_index, page_name=args.page_name)

    for warning in lint_design(doc):
        print("[lint] %s" % warning, file=sys.stderr)
    doc.save(args.output)
    print("Created .figcraft file: %s" % args.output)

    if args.preview:
        export_preview(args.output, port=args.port,
                       page_index=args.page_index, page_name=args.page_name)

    print("Done. Ready to inspect or iterate.\n")


if __name__ == "__main__":
    main()
