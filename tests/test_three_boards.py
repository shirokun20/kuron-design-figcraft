"""Three-board layout, smart reuse, and board-scoped render audit tests."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import audit_render  # noqa: E402
import figcraft_tool as ft  # noqa: E402
import quick_design as qd  # noqa: E402
from figcraft_tool import FigcraftDocument, TOKENS  # noqa: E402


def save_temp(doc):
    """Save a document to a temporary file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".figcraft")
    os.close(fd)
    doc.save(path)
    return path


class ThreeBoardLayoutTests(unittest.TestCase):
    def test_generation_creates_three_separated_boards_on_pages_zero(self):
        doc = qd.generate_preset("three-board", "three-board-layout")
        page = doc.doc["nodes"][str(doc.doc["pages"][0])]
        boards = [doc.doc["nodes"][str(child_id)] for child_id in page["children"]]

        self.assertEqual([board["name"] for board in boards],
                         ["00_Foundations", "01_Components", "02_Screens"])
        self.assertTrue(all(board["type"] == "frame" for board in boards))
        self.assertTrue(all(board.get("clip") is True for board in boards))
        xs = [board["transform"][4] for board in boards]
        for left, right in zip(xs, xs[1:]):
            gap = right - (left + boards[0]["width"])
            self.assertAlmostEqual(gap, qd.BOARD_GAP, places=4)
            self.assertGreater(gap, 0)

    def test_foundations_use_manifest_tokens(self):
        doc = qd.generate_preset("three-board", "foundations")
        nodes = doc.doc["nodes"]
        names = {node.get("name") for node in nodes.values() if isinstance(node, dict)}
        for expected in ("Swatch_action-primary", "Type_display",
                         "Space_xl", "Radius_card", "FoundationTitle"):
            self.assertIn(expected, names, "missing foundation node: %s" % expected)
        row = next(node for node in nodes.values()
                   if isinstance(node, dict) and node.get("name") == "Swatch_action-primary")
        swatch = nodes[str(row["children"][0])]
        label = next(node for node in nodes.values()
                     if isinstance(node, dict) and node.get("name") == "SwatchLabel")
        colors = TOKENS["colors"]
        self.assertEqual(ft._lint_hex(swatch["fills"][0]["color"]),
                         ft._lint_hex(ft.make_solid_fill(colors["action-primary"])[0]["color"]))
        self.assertIn("#", label["characters"])

    def test_screens_duplicate_components_instead_of_rebuilding(self):
        doc = qd.generate_preset("three-board", "reuse-screen")
        nodes = doc.doc["nodes"]
        for name in ("BtnPrimary", "BadgeSuccess", "Card"):
            template = next(node for node in nodes.values()
                            if isinstance(node, dict) and node.get("name") == name)
            copies = [node for node in nodes.values()
                      if isinstance(node, dict)
                      and node.get("name", "").startswith("Reused")
                      and node.get("type") == template.get("type")]
            self.assertTrue(copies, "no screen copy made from %s" % name)


class SmartReuseTests(unittest.TestCase):
    def test_ensure_board_reuses_existing_board(self):
        doc = FigcraftDocument("reuse-board")
        first = ft.ensure_board(doc, "00_Foundations", x=0, y=0, width=800, height=900)
        count = len(doc.doc["nodes"])
        second = ft.ensure_board(doc, "00_Foundations", x=999, y=999,
                                 width=1, height=1)
        self.assertEqual(first, second)
        self.assertEqual(len(doc.doc["nodes"]), count)
        self.assertEqual(doc.doc["nodes"][str(first)]["transform"][4], 0)

    def test_find_or_reuse_component_builds_once_and_reuses(self):
        doc = FigcraftDocument("reuse-component")
        board = ft.ensure_board(doc, "01_Components", x=0, y=0)
        calls = []

        def builder():
            calls.append(1)
            return doc.build_button("BtnPrimary", "Submit", board,
                                    variant="primary", size="md")

        found = ft.find_or_reuse_component(doc, "BtnPrimary",
                                           parent_id=board, builder=builder)
        again = ft.find_or_reuse_component(doc, "BtnPrimary",
                                           parent_id=board, builder=builder)
        self.assertEqual(found, again)
        self.assertEqual(calls, [1])

    def test_duplicate_node_uses_fresh_unique_ids(self):
        doc = FigcraftDocument("unique-ids")
        board = ft.ensure_board(doc, "01_Components", x=0, y=0)
        base = doc.build_button("BtnPrimary", "Submit", board,
                                variant="primary", size="md")
        original_ids = set(doc.doc["nodes"].keys())
        copy_id = doc.duplicate_node(base, parent_id=board, name="BtnCopy")
        self.assertIsNotNone(copy_id)
        self.assertNotIn(str(copy_id), original_ids)
        for node_id in original_ids:
            self.assertNotEqual(str(copy_id), node_id)
        self.assertGreater(doc.doc["next_id"], max(int(i) for i in original_ids))

    def test_alloc_id_skips_stale_collisions(self):
        doc = FigcraftDocument("stale-next-id")
        doc.doc["next_id"] = 10
        doc.doc["nodes"]["10"] = {"id": 10, "name": "Existing", "type": "frame",
                                  "children": [], "parent": 1}
        allocated = doc.alloc_id()
        self.assertEqual(allocated, 11)
        self.assertEqual(doc.doc["next_id"], 12)

    def test_regeneration_is_idempotent(self):
        doc = qd.generate_preset("three-board", "idempotent")
        before = set(doc.doc["nodes"].keys())
        qd.generate_three_boards(doc)
        self.assertEqual(set(doc.doc["nodes"].keys()), before)
        page = doc.doc["nodes"][str(doc.doc["pages"][0])]
        self.assertEqual(len(page["children"]), 3)


class MultiBoardAuditTests(unittest.TestCase):
    def test_clean_three_board_file_passes(self):
        path = save_temp(qd.generate_preset("three-board", "audit-clean"))
        try:
            self.assertEqual(audit_render.audit_file(path), [])
        finally:
            os.remove(path)

    def test_defect_in_any_board_is_caught_and_scoped(self):
        doc = qd.generate_preset("three-board", "audit-defect")
        boards = [doc.doc["nodes"][str(child_id)]
                  for child_id in doc.doc["nodes"]["1"]["children"]]
        # Break clipping on the middle board only.
        boards[1]["clip"] = False
        path = save_temp(doc)
        try:
            failures = audit_render.audit_file(path)
        finally:
            os.remove(path)
        clipped = [item for item in failures if "clip: false" in item]
        self.assertEqual(len(clipped), 1)
        self.assertIn("01_Components", clipped[0])
        self.assertFalse(any("00_Foundations" in item for item in clipped))
        self.assertFalse(any("02_Screens" in item for item in clipped))

    def test_adjacent_boards_do_not_create_contrast_false_positives(self):
        doc = FigcraftDocument("board-contrast")
        left = ft.ensure_board(doc, "00_Foundations", x=0, y=0,
                               width=1100, height=900,
                               fill=TOKENS["colors"]["bg"], clip=True)
        right = ft.ensure_board(doc, "01_Components", x=1220, y=0,
                                width=1100, height=900,
                                fill=TOKENS["colors"]["surface"], clip=True)
        for board, color in ((left, TOKENS["colors"]["text"]),
                             (right, TOKENS["colors"]["text"])):
            wrapper = doc.create_frame("UnfilledWrapper", board, 900, 700)
            doc.create_text("Label", "readable label", wrapper,
                            font_size=13.0, width=400.0, color=color)
        path = save_temp(doc)
        try:
            failures = audit_render.audit_file(path)
        finally:
            os.remove(path)
        self.assertFalse([item for item in failures if "S-12" in item], failures)

    def test_overlapping_boards_are_reported(self):
        doc = FigcraftDocument("board-overlap")
        ft.ensure_board(doc, "00_Foundations", x=0, y=0,
                        width=1100, height=900, fill=TOKENS["colors"]["bg"], clip=True)
        ft.ensure_board(doc, "01_Components", x=1000, y=0,
                        width=1100, height=900, fill=TOKENS["colors"]["bg"], clip=True)
        path = save_temp(doc)
        try:
            failures = audit_render.audit_file(path)
        finally:
            os.remove(path)
        self.assertTrue(any("S-14" in item and "overlap" in item for item in failures),
                        failures)


if __name__ == "__main__":
    unittest.main()
