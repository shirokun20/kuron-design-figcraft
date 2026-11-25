"""Linter S-01/S-02/S-03/S-08/S-09/S-10/S-11 tests, asserted via semantic roles."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from figcraft_tool import (FigcraftDocument, TOKENS, lint_design,  # noqa: E402
                           hex_to_rgba)

COLORS = TOKENS["colors"]
# Legacy aliases still exist, but the canonical roles are the contract.
ACTION = COLORS["action-primary"]
ACTION_FG = COLORS["action-primary-fg"]
TECHNICAL = COLORS["data-technical"]


def temp_path(suffix=".figcraft"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


class LintRuleTests(unittest.TestCase):
    def test_colour_aliases_map_to_semantic_roles(self):
        self.assertEqual(COLORS["coral"], ACTION)
        self.assertEqual(COLORS["coral_fg"], ACTION_FG)
        self.assertEqual(COLORS["cyan"], TECHNICAL)
        self.assertNotEqual(ACTION, TECHNICAL)

    def test_s01_colored_border_is_warned_neutral_is_clean(self):
        doc = FigcraftDocument("s01")
        doc.create_frame("Box", 1, 200.0, 100.0, fill=COLORS["raised"],
                         stroke=TECHNICAL)
        warnings = lint_design(doc)
        self.assertTrue(any("border" in m and "Box" in m for m in warnings))
        clean = FigcraftDocument("s01ok")
        clean.create_frame("Box", 1, 200.0, 100.0, fill=COLORS["raised"],
                           stroke=COLORS["line"])
        self.assertFalse([m for m in lint_design(clean)
                          if "border" in m and "Box" in m])

    def test_s02_long_technical_mono_title_warned_short_counter_clean(self):
        doc = FigcraftDocument("s02")
        doc.create_text("Lane", "MAIN FLOW — START HERE, FOLLOW THE ARROW", 1,
                        font_family=TOKENS["typography"]["font_mono"],
                        color=TECHNICAL)
        self.assertTrue(any("data-technical" in m for m in lint_design(doc)))
        clean = FigcraftDocument("s02ok")
        clean.create_text("Count", "12 BUBBLES", 1,
                          font_family=TOKENS["typography"]["font_mono"],
                          color=TECHNICAL)
        self.assertFalse([m for m in lint_design(clean)
                          if "data-technical" in m])

    def test_s08_overflowing_text_warned(self):
        doc = FigcraftDocument("s08")
        card = doc.create_frame("Card", 1, 190.0, 100.0, fill=COLORS["raised"],
                                stroke=COLORS["line"], layout_mode="vertical",
                                padding=(14.0, 16.0, 14.0, 16.0))
        doc.create_text("D", "Manage projects. Open a manga page.", card,
                        font_size=12.0, color=COLORS["text-2"], width=190.0)
        self.assertTrue(any("overflows" in m for m in lint_design(doc)))

    def test_s03_connector_spans_and_loopback_offset(self):
        doc = FigcraftDocument("s03")
        a = doc.create_frame("A", 1, 100.0, 60.0, x=0.0, y=0.0, fill=COLORS["raised"])
        b = doc.create_frame("B", 1, 100.0, 60.0, x=200.0, y=0.0, fill=COLORS["raised"])
        cid = doc.build_connector("lnk", a, b, 1)
        node = doc.doc["nodes"][str(cid)]
        xs = [v["x"] for v in node["network"]["vertices"]]
        self.assertEqual(min(xs), 100.0)
        self.assertEqual(max(xs), 200.0)
        self.assertEqual(len(node["network"]["segments"]), 3)

        c = doc.create_frame("C", 1, 100.0, 60.0, x=400.0, y=0.0, fill=COLORS["raised"])
        lid = doc.build_connector("loop", b, c, 1, from_side="top",
                                  to_side="top", style="dashed", offset=-30.0)
        loop = doc.doc["nodes"][str(lid)]
        ys = sorted({v["y"] for v in loop["network"]["vertices"]})
        self.assertEqual(ys[0], -30.0)

    def test_s08_default_width_is_honest_estimate(self):
        doc = FigcraftDocument("s08b")
        narrow = doc.create_frame("Narrow", 1, 80.0, 40.0, fill=COLORS["raised"],
                                  stroke=COLORS["line"], layout_mode="vertical",
                                  padding=(4.0, 6.0, 4.0, 6.0))
        text_id = doc.create_text("Lbl", "Import PDF", narrow, font_size=12.0,
                                  color=COLORS["text"])
        self.assertEqual(doc.doc["nodes"][str(text_id)]["width"], 0.0)
        path = temp_path()
        try:
            doc.save(path)
        finally:
            if os.path.exists(path):
                os.remove(path)
        width = doc.doc["nodes"][str(text_id)]["width"]
        self.assertFalse([m for m in lint_design(doc) if "overflows" in m])
        expected = len("Import PDF") * 12.0 * 0.52 + 2
        self.assertLess(abs(width - expected), 1.0)

    def test_s09_wrong_icon_colour_on_action_surface_warned(self):
        doc = FigcraftDocument("s09")
        button = doc.create_frame("Btn", 1, 120.0, 28.0, fill=ACTION)
        icon = doc.create_vector("Ico", ["M0 0H24"], button, stroke="#ffffff")
        warned = [m for m in lint_design(doc) if "action-primary-fg" in m]
        self.assertEqual(len(warned), 1)
        doc.doc["nodes"][str(icon)]["strokes"][0]["color"] = dict(hex_to_rgba(ACTION_FG))
        self.assertFalse([m for m in lint_design(doc) if "action-primary-fg" in m])

    def test_s10_vertical_overflow_warned(self):
        doc = FigcraftDocument("s10")
        frame = doc.create_frame("Card", 1, 200.0, 40.0, fill=COLORS["raised"],
                                 layout_mode="vertical", gap=4.0,
                                 padding=(10.0, 14.0, 10.0, 14.0))
        doc.create_text("T1", "Line one", frame, font_size=12.0)
        over = doc.create_text("T2", "Line two that is clipped", frame,
                               font_size=12.0, height=16.2)
        node = doc.doc["nodes"][str(over)]
        node["transform"][5] = 30.0  # 30 + 16.2 > 40 - 10 + 1
        self.assertEqual(len([m for m in lint_design(doc)
                              if "overflows vertically" in m]), 1)
        node["transform"][5] = 10.0
        self.assertFalse([m for m in lint_design(doc)
                          if "overflows vertically" in m])

    def test_s11_clip_false_on_screen_frame_warned(self):
        doc = FigcraftDocument("s11")
        screen = doc.create_frame("01. Screen", 1, 1280.0, 960.0,
                                  fill=COLORS["surface"], clip=False)
        doc.doc["pages"] = [1]
        doc.doc["nodes"]["1"]["children"] = [screen]
        self.assertTrue(any("clip is false" in m for m in lint_design(doc)))
        doc.prevent_clipping(screen)
        self.assertFalse([m for m in lint_design(doc) if "clip: false" in m])


if __name__ == "__main__":
    unittest.main()
