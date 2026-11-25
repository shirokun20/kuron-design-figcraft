"""Component-first overrides are applied to real node properties only."""

import json
import os
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import figcraft_tool as ft  # noqa: E402
import quick_design as qd  # noqa: E402
from figcraft_tool import FigcraftDocument, TOKENS  # noqa: E402


def document_json(path):
    with zipfile.ZipFile(path) as archive:
        return archive.read("document.json").decode("utf-8")


class ComponentOverrideTests(unittest.TestCase):
    def test_override_key_is_never_written_to_serialized_document(self):
        doc = FigcraftDocument("override")
        base = doc.build_button("BtnBase", "Submit", 1,
                                variant="primary", size="md")
        source = doc.doc["nodes"][str(base)]
        original_fills = json.loads(json.dumps(source["fills"]))
        danger = ft.make_solid_fill(TOKENS["colors"]["status-danger"])

        copy_id = doc.component_first(
            base, 1, name="BtnCopy",
            overrides={"fills": danger, "characters": "Delete"})
        copy = doc.doc["nodes"][str(copy_id)]

        self.assertEqual(copy["name"], "BtnCopy")
        self.assertEqual(copy["fills"], danger)
        self.assertEqual(copy["characters"], "Delete")
        self.assertNotIn("overrides", copy)
        # The source template is untouched: no mutation and no leak of the key.
        self.assertEqual(source["fills"], original_fills)
        self.assertNotIn("characters", source)
        self.assertNotIn("overrides", source)

        fd, path = tempfile.mkstemp(suffix=".figcraft")
        os.close(fd)
        try:
            doc.save(path)
            self.assertNotIn('"overrides"', document_json(path))
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_override_mapping_and_residual_keys_are_sanitized(self):
        doc = FigcraftDocument("nested")
        base = doc.build_badge("BadgeBase", "Ready", 1, tone="status-success")
        copy_id = doc.component_first(
            base, 1, overrides={"fills": []}, name="BadgeCopy")
        copy = doc.doc["nodes"][str(copy_id)]
        self.assertEqual(copy["name"], "BadgeCopy")
        self.assertEqual(copy["fills"], [])
        self.assertNotIn("overrides", copy)

        # A residual ``overrides`` key supplied to the low-level API is
        # stripped instead of being written into the duplicated node.
        residual_id = doc.duplicate_node(
            base, 1, overrides={"overrides": {"fills": []}, "name": "BadgeResidual"})
        residual = doc.doc["nodes"][str(residual_id)]
        self.assertEqual(residual["name"], "BadgeResidual")
        self.assertNotIn("overrides", residual)

    def test_generated_components_have_distinct_variations_and_no_override_keys(self):
        doc = qd.generate_live("components", "library")
        nodes = doc.doc["nodes"]
        by_name = {node.get("name"): node for node in nodes.values()
                   if isinstance(node, dict)}
        for expected in ("BtnPrimary", "BtnSecondary", "BtnGhost",
                         "BadgeSuccess", "BadgeDanger"):
            self.assertIn(expected, by_name)

        labels = {node.get("characters") for node in nodes.values()
                  if isinstance(node, dict) and node.get("type") == "text"}
        for key in ("submit", "save_changes", "cancel",
                    "status_ready", "status_error"):
            self.assertIn(qd.text(key), labels)

        primary_fill = by_name["BtnPrimary"]["fills"]
        secondary_fill = by_name["BtnSecondary"]["fills"]
        ghost_fill = by_name["BtnGhost"]["fills"]
        self.assertNotEqual(primary_fill, secondary_fill)
        self.assertNotEqual(primary_fill, ghost_fill)
        self.assertNotEqual(secondary_fill, ghost_fill)
        self.assertEqual(ghost_fill, [])
        self.assertNotEqual(by_name["BadgeSuccess"]["fills"],
                            by_name["BadgeDanger"]["fills"])

        fd, path = tempfile.mkstemp(suffix=".figcraft")
        os.close(fd)
        try:
            doc.save(path)
            self.assertNotIn('"overrides"', document_json(path))
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
