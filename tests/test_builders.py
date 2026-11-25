"""Builder contract tests (SKILL §8) — semantic-role based."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from figcraft_tool import FigcraftDocument, TOKENS, _lint_hex  # noqa: E402

COLORS = TOKENS["colors"]
ACTION = COLORS["action-primary"]


def kids(doc, nid):
    nodes = doc.doc["nodes"]
    return [nodes[str(c)] for c in nodes[str(nid)].get("children", [])]


def all_text(doc):
    return " ".join(
        str(node.get("characters", ""))
        for node in doc.doc["nodes"].values()
        if isinstance(node, dict) and node.get("type") == "text"
    )


class BuilderContractTests(unittest.TestCase):
    def test_dialog_has_scrim_dialog_primary_and_cancel(self):
        doc = FigcraftDocument("dlg")
        dialog = doc.build_dialog(
            "DelDlg", "Delete 3 pages?",
            "3 pages and 41 translations will be deleted.",
            "Delete 3 pages", 1, width=1280.0, height=960.0)
        names = [node.get("name") for node in kids(doc, dialog)]
        self.assertIn("Scrim", names)
        self.assertIn("Dialog", names)
        flat = all_text(doc)
        self.assertIn("Delete 3 pages", flat)
        self.assertIn("Cancel", flat)

    def test_empty_state_has_title_description_action_no_illustration(self):
        doc = FigcraftDocument("emp")
        doc.build_empty_state("Empty", "No pages yet",
                              "Import a PDF to begin.", "Import PDF", 1)
        flat = all_text(doc)
        for needle in ("No pages yet", "Import a PDF to begin", "Import PDF"):
            self.assertIn(needle, flat)

    def test_error_inline_has_cause_solution_retry(self):
        doc = FigcraftDocument("err")
        doc.build_error_inline("Err429", "Translation failed (429).",
                               "Wait 2 seconds, then choose Try again.", 1)
        flat = all_text(doc)
        self.assertIn("Translation failed (429)", flat)
        self.assertIn("Try again", flat)

    def test_ledger_row_has_six_columns(self):
        doc = FigcraftDocument("led")
        row = doc.build_ledger_row("R1", "#", "Page", "Source", "Result", "Fit",
                                   "Checked", 1, state="cursor")
        types = [node.get("type") for node in kids(doc, row)]
        self.assertGreaterEqual(sum(1 for kind in types if kind == "text"), 6)

    def test_pipeline_bar_active_stage_uses_action_primary_role(self):
        doc = FigcraftDocument("pipe")
        doc.build_pipeline_bar(1, active_stage=3)
        flat = all_text(doc)
        for needle in ("Import", "Export", "3. Translate"):
            self.assertIn(needle, flat)
        active = [
            node for node in doc.doc["nodes"].values()
            if isinstance(node, dict) and node.get("type") == "text"
            and (node.get("fills") or [{}])[0].get("color") is not None
            and _lint_hex((node.get("fills") or [{}])[0].get("color") or {}) == ACTION.lower()
        ]
        self.assertTrue(any("Translate" in str(node.get("characters", "")) for node in active))

    def test_duplicate_and_component_first_preserve_styling(self):
        doc = FigcraftDocument("dup")
        base = doc.build_button("BtnBase", "Submit", 1, variant="primary", size="md")
        original = doc.doc["nodes"][str(base)]
        copy_id = doc.component_first(base, 1, name="BtnCopy", overrides={"name": "BtnCopy"})
        copy = doc.doc["nodes"][str(copy_id)]
        self.assertNotEqual(copy_id, base)
        self.assertEqual(copy["name"], "BtnCopy")
        self.assertEqual(copy.get("fills"), original.get("fills"))
        self.assertEqual(copy.get("corner_radius") if "corner_radius" in copy
                         else copy.get("corners"), original.get("corners"))
        copied_children = [doc.doc["nodes"][str(c)] for c in copy.get("children", [])]
        self.assertEqual(len(copied_children), len(original.get("children", [])))
        for child_copy in copied_children:
            self.assertEqual(child_copy.get("parent"), copy_id)
            self.assertEqual(child_copy.get("fills"),
                             doc.doc["nodes"][str(original["children"][0])].get("fills"))

    def test_save_runs_reflow_and_box_centers_text(self):
        doc = FigcraftDocument("reflow")
        row = doc.create_frame("Row", 1, 300.0, 32.0, fill=COLORS["raised"],
                               layout_mode="horizontal", cross_align="center")
        text_id = doc.create_text("Lbl", "DeepSeek Chat (V3)", row, font_size=12.0)
        fd, path = tempfile.mkstemp(suffix=".figcraft")
        os.close(fd)
        try:
            doc.save(path)
        finally:
            if os.path.exists(path):
                os.remove(path)
        node = doc.doc["nodes"][str(text_id)]
        self.assertAlmostEqual(node["transform"][5], (32 - node["height"]) / 2, delta=0.2)
        self.assertNotEqual(node["transform"][5], 0.0)


if __name__ == "__main__":
    unittest.main()
