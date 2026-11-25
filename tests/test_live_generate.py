"""Live Generate and render-audit detection tests across style directions."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import audit_render  # noqa: E402
import design_manifest as dm  # noqa: E402
import quick_design as qd  # noqa: E402
from figcraft_tool import FigcraftDocument, TOKENS, lint_design  # noqa: E402

KINDS = ("components", "screen", "form")
DIRECTIONS = ("dense_operational", "bento_modular", "editorial",
              "clean_utility", "custom")


class LiveGenerateTests(unittest.TestCase):
    def test_all_kinds_build_for_every_style_direction(self):
        for style in DIRECTIONS:
            for kind in KINDS:
                with self.subTest(style=style, kind=kind):
                    doc = qd.generate_live(kind, "live-%s-%s" % (style, kind), style=style)
                    self.assertGreater(len(doc.doc["nodes"]), 5)
                    roots = [n for n in doc.doc["nodes"].values()
                             if isinstance(n, dict) and n.get("type") == "frame"
                             and (n.get("width") or 0) >= 900]
                    self.assertTrue(roots, "no screen-level frame generated")
                    self.assertTrue(any(n.get("clip") is True for n in roots),
                                    "screen frame must clip its content")

    def test_generated_output_has_no_overflow_or_clip_defects(self):
        for style in DIRECTIONS:
            for kind in KINDS:
                with self.subTest(style=style, kind=kind):
                    doc = qd.generate_live(kind, "audit-%s-%s" % (style, kind), style=style)
                    structural = [m for m in lint_design(doc)
                                  if any(tag in m for tag in (
                                      "overflows", "clip: false", "escapes"))]
                    self.assertEqual(structural, [])

    def test_style_direction_changes_topology(self):
        dense = qd.generate_live("screen", "dense", style="dense_operational")
        bento = qd.generate_live("screen", "bento", style="bento_modular")
        names_a = {n.get("name") for n in dense.doc["nodes"].values() if isinstance(n, dict)}
        names_b = {n.get("name") for n in bento.doc["nodes"].values() if isinstance(n, dict)}
        self.assertIn("Rail", names_a)
        self.assertIn("Inspector", names_a)
        self.assertNotIn("Rail", names_b)
        self.assertIn("Cards", names_b)

    def test_microcopy_follows_locale_and_copy_tone(self):
        doc = dm.load_design()
        self.assertEqual(qd.text("app_name"), doc["copy"][doc["locale"]]["app_name"])
        self.assertEqual(qd.LOCALE, doc["locale"])
        self.assertEqual(qd.COPY_TONE, doc["copy_tone"])

    def test_theme_override_resolves_both_themes(self):
        dark = dm.to_builder_tokens(dm.load_design(), "dark")["colors"]
        light = dm.to_builder_tokens(dm.load_design(), "light")["colors"]
        self.assertNotEqual(dark["action-primary"], light["action-primary"])
        qd.use_theme("light")
        self.addCleanup(qd.use_theme, None)
        self.assertEqual(qd.TOKENS["colors"]["action-primary"],
                         light["action-primary"])


class RenderAuditDetectionTests(unittest.TestCase):
    def test_contract_contrast_passes_for_both_themes(self):
        audit_render.FAIL.clear()
        audit_render.audit_contract_contrast()
        self.assertEqual(audit_render.FAIL, [])

    def test_audit_detects_overflow_clip_false_and_low_contrast(self):
        doc = FigcraftDocument("defects")
        screen = doc.create_frame("01. Defects", 1, 1280.0, 960.0,
                                  fill=TOKENS["colors"]["bg"], clip=False)
        doc.doc["nodes"]["1"]["children"] = [screen]
        card = doc.create_frame("Card", screen, 300.0, 60.0,
                                fill=TOKENS["colors"]["bg"],
                                layout_mode="vertical", padding=(4.0, 8.0, 4.0, 8.0))
        doc.create_text("TooWide", "A very long line that overflows its card", card,
                        font_size=13.0, color=TOKENS["colors"]["bg"], width=600.0)
        fd, path = tempfile.mkstemp(suffix=".figcraft")
        os.close(fd)
        try:
            doc.save(path)
            failures = audit_render.audit_file(path, str(screen))
        finally:
            if os.path.exists(path):
                os.remove(path)
        joined = " | ".join(failures)
        self.assertIn("clip: false", joined)
        self.assertIn("overflows horizontally", joined)
        self.assertIn("contrast", joined)

    def test_audit_passes_clean_generated_screen(self):
        doc = qd.generate_live("screen", "clean", style="clean_utility")
        fd, path = tempfile.mkstemp(suffix=".figcraft")
        os.close(fd)
        try:
            doc.save(path)
            failures = audit_render.audit_file(path)
        finally:
            if os.path.exists(path):
                os.remove(path)
        self.assertEqual(failures, [], "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
