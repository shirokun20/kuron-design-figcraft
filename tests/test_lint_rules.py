"""Linter S-01/S-02/S-03/S-08/S-09/S-10 tests — converted to unittest."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from figcraft_tool import (FigcraftDocument, TOKENS, lint_design,  # noqa: E402
                           hex_to_rgba)

C = TOKENS["colors"]


def temp_path(suffix=".figcraft"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


class LintRuleTests(unittest.TestCase):
    def test_s01_colored_border_is_warned_neutral_is_clean(self):
        doc = FigcraftDocument("s01")
        doc.create_frame("Box", 1, 200.0, 100.0, fill=C["surface_card"],
                         stroke=C["cyan"])
        warnings = lint_design(doc)
        self.assertTrue(any("border" in m and "Box" in m for m in warnings))

        doc2 = FigcraftDocument("s01ok")
        doc2.create_frame("Box", 1, 200.0, 100.0, fill=C["surface_card"],
                          stroke=C["border"])
        self.assertFalse([m for m in lint_design(doc2)
                          if "border" in m and "Box" in m])

    def test_s02_long_cyan_mono_title_warned_short_counter_clean(self):
        doc = FigcraftDocument("s02")
        doc.create_text("Lane", "MAIN FLOW — MULAI DARI SINI, IKUTI PANAH", 1,
                        font_family=TOKENS["typography"]["font_mono"],
                        color=C["cyan"])
        self.assertTrue(any("cyan" in m for m in lint_design(doc)))

        doc2 = FigcraftDocument("s02ok")
        doc2.create_text("Count", "12 BUBBLES", 1,
                         font_family=TOKENS["typography"]["font_mono"],
                         color=C["cyan"])
        self.assertFalse([m for m in lint_design(doc2) if "cyan" in m])

    def test_s08_overflowing_text_warned(self):
        doc = FigcraftDocument("s08")
        card = doc.create_frame("Card", 1, 190.0, 100.0, fill=C["surface_card"],
                                stroke=C["border"], layout_mode="vertical",
                                padding=(14.0, 16.0, 14.0, 16.0))
        doc.create_text("D", "Kelola proyek. Buka halaman manga.", card,
                        font_size=12.0, color=C["ink_secondary"], width=190.0)
        self.assertTrue(any("meluber" in m for m in lint_design(doc)))

    def test_s03_connector_spans_and_loopback_offset(self):
        doc = FigcraftDocument("s03")
        a = doc.create_frame("A", 1, 100.0, 60.0, x=0.0, y=0.0, fill=C["surface_card"])
        b = doc.create_frame("B", 1, 100.0, 60.0, x=200.0, y=0.0, fill=C["surface_card"])
        cid = doc.build_connector("lnk", a, b, 1)
        node = doc.doc["nodes"][str(cid)]
        xs = [v["x"] for v in node["network"]["vertices"]]
        self.assertEqual(min(xs), 100.0)
        self.assertEqual(max(xs), 200.0)
        self.assertEqual(len(node["network"]["segments"]), 3)

        c = doc.create_frame("C", 1, 100.0, 60.0, x=400.0, y=0.0, fill=C["surface_card"])
        lid = doc.build_connector("loop", b, c, 1, from_side="top",
                                  to_side="top", style="dashed", offset=-30.0)
        loop = doc.doc["nodes"][str(lid)]
        ys = sorted({v["y"] for v in loop["network"]["vertices"]})
        self.assertEqual(ys[0], -30.0)

    def test_s08_default_width_is_honest_estimate(self):
        doc = FigcraftDocument("s08b")
        narrow = doc.create_frame("Narrow", 1, 80.0, 40.0, fill=C["surface_card"],
                                  stroke=C["border"], layout_mode="vertical",
                                  padding=(4.0, 6.0, 4.0, 6.0))
        t = doc.create_text("Lbl", "Impor PDF", narrow, font_size=12.0,
                            color=C["ink_primary"])
        self.assertEqual(doc.doc["nodes"][str(t)]["width"], 0.0)
        path = temp_path()
        try:
            doc.save(path)
        finally:
            if os.path.exists(path):
                os.remove(path)
        width = doc.doc["nodes"][str(t)]["width"]
        self.assertFalse([m for m in lint_design(doc) if "meluber" in m])
        wants = len("Impor PDF") * 12.0 * 0.52 + 2
        self.assertLess(abs(width - wants), 1.0)

    def test_s09_white_icon_on_coral_warned_coral_fg_clean(self):
        doc = FigcraftDocument("s09")
        btn_id = doc.create_frame("Btn", 1, 120.0, 28.0, fill=C["coral"])
        v = doc.create_vector("Ico", ["M0 0H24"], btn_id, stroke="#ffffff")
        warned = [m for m in lint_design(doc)
                  if "coral_fg" in m or "permukaan coral" in m]
        self.assertEqual(len(warned), 1)
        doc.doc["nodes"][str(v)]["strokes"][0]["color"] = dict(hex_to_rgba(C["coral_fg"]))
        self.assertFalse([m for m in lint_design(doc)
                          if "coral_fg" in m or "permukaan coral" in m])

    def test_s10_vertical_overflow_warned(self):
        doc = FigcraftDocument("s10")
        frame = doc.create_frame("Card", 1, 200.0, 40.0, fill=C["surface_card"],
                                 layout_mode="vertical", gap=4.0,
                                 padding=(10.0, 14.0, 10.0, 14.0))
        doc.create_text("T1", "Baris satu", frame, font_size=12.0)
        over = doc.create_text("T2", "Baris dua yang kepotong", frame,
                               font_size=12.0, height=16.2)
        node = doc.doc["nodes"][str(over)]
        node["transform"][5] = 30.0  # 30 + 16.2 > 40 - 10 + 1
        self.assertEqual(len([m for m in lint_design(doc)
                              if "meluber vertikal" in m]), 1)
        node["transform"][5] = 10.0
        self.assertFalse([m for m in lint_design(doc) if "meluber vertikal" in m])


if __name__ == "__main__":
    unittest.main()
