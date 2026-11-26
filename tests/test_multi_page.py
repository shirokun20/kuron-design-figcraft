"""Multi-page (pages[0..N]) support: selectors, reuse, reflow, and audit."""

import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import agent_terminal  # noqa: E402
import audit_render  # noqa: E402
import figcraft_tool as ft  # noqa: E402
import quick_design as qd  # noqa: E402
from figcraft_tool import FigcraftDocument, TOKENS  # noqa: E402


def add_valid_board(doc, page_id, name):
    """Add a small, audit-clean board with visible leaf content to a page."""
    board = doc.create_frame(
        name, page_id, 1200.0, 900.0, x=40.0, y=40.0,
        fill=TOKENS["colors"]["bg"], clip=True,
    )
    doc.create_rect("Content", board, 1100.0, 820.0, x=50.0, y=40.0,
                    fill=TOKENS["colors"]["raised"])
    return board


def save_temp(doc):
    """Save a document to a temporary .figcraft path."""
    fd, path = tempfile.mkstemp(suffix=".figcraft")
    os.close(fd)
    doc.save(path)
    return path


class PageSelectionTests(unittest.TestCase):
    def test_resolve_page_by_index_and_name(self):
        doc = FigcraftDocument("pages")
        second = doc.add_page("01_Archive")
        self.assertEqual(doc.resolve_page(0), doc.doc["pages"][0])
        self.assertEqual(doc.resolve_page(1), second)
        self.assertEqual(doc.resolve_page(page_name="01_Archive"), second)

    def test_invalid_page_selectors_raise_actionable_errors(self):
        doc = FigcraftDocument("pages")
        doc.add_page("01_Archive")
        with self.assertRaises(ValueError) as caught:
            doc.resolve_page(7)
        self.assertIn("out of range", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            doc.resolve_page(page_name="Missing")
        self.assertIn("available pages", str(caught.exception))

    def test_ensure_board_targets_selected_page(self):
        doc = FigcraftDocument("pages")
        second = doc.add_page("01_Archive")
        first_board = ft.ensure_board(doc, "00_Foundations", x=0, y=0,
                                      width=800, height=800)
        second_board = ft.ensure_board(doc, "00_Foundations", x=0, y=0,
                                       width=800, height=800,
                                       page_name="01_Archive")
        self.assertNotEqual(first_board, second_board)
        self.assertIn(first_board, doc.doc["nodes"]["1"]["children"])
        self.assertIn(second_board, doc.doc["nodes"][str(second)]["children"])
        self.assertEqual(ft.ensure_board(doc, "00_Foundations",
                                         page_index=1), second_board)

    def test_add_page_rejects_duplicate_name(self):
        doc = FigcraftDocument("pages")
        doc.add_page("01_Archive")
        with self.assertRaises(ValueError):
            doc.add_page("01_Archive")


class CrossPageReuseTests(unittest.TestCase):
    def test_find_or_reuse_component_searches_all_pages_by_default(self):
        doc = FigcraftDocument("cross-page")
        archive = doc.add_page("01_Archive")
        board = add_valid_board(doc, archive, "01_Components")
        button = doc.build_button("BtnPrimary", "Submit", board,
                                  variant="primary", size="md")
        self.assertEqual(ft.find_or_reuse_component(doc, "BtnPrimary"), button)
        self.assertEqual(ft.find_or_reuse_component(
            doc, "BtnPrimary", page_name="01_Archive"), button)
        self.assertIsNone(ft.find_or_reuse_component(
            doc, "BtnPrimary", page_index=0))

    def test_duplicate_node_can_target_another_page(self):
        doc = FigcraftDocument("cross-page")
        source_page = doc.doc["pages"][0]
        archive = doc.add_page("01_Archive")
        board = add_valid_board(doc, source_page, "01_Components")
        button = doc.build_button("BtnPrimary", "Submit", board,
                                  variant="primary", size="md")
        original_ids = set(doc.doc["nodes"].keys())

        copy = doc.duplicate_node(button, name="BtnCopy", page_name="01_Archive")
        self.assertIsNotNone(copy)
        self.assertNotIn(str(copy), original_ids)
        self.assertEqual(doc.doc["nodes"][str(copy)]["parent"], archive)
        self.assertNotIn(copy, doc.doc["nodes"][str(source_page)]["children"])
        self.assertIn(copy, doc.doc["nodes"][str(archive)]["children"])

    def test_three_boards_can_be_generated_on_a_later_page(self):
        doc = FigcraftDocument("later-page")
        archive = doc.add_page("01_Archive")
        boards = qd.generate_three_boards(doc, page_name="01_Archive")
        page = doc.doc["nodes"][str(archive)]
        self.assertEqual([doc.doc["nodes"][str(c)]["name"]
                          for c in page["children"]],
                         ["00_Foundations", "01_Components", "02_Screens"])
        self.assertEqual(len(boards), 4)  # three boards + the library id


class SaveReflowTests(unittest.TestCase):
    def test_save_and_reload_preserve_every_page(self):
        doc = FigcraftDocument("preserve")
        archive = doc.add_page("01_Archive")
        first = add_valid_board(doc, doc.doc["pages"][0], "00_Foundations")
        second = add_valid_board(doc, archive, "02_Screens")
        original_ids = set(doc.doc["nodes"].keys())
        original_pages = list(doc.doc["pages"])

        path = save_temp(doc)
        try:
            reloaded = FigcraftDocument.load(path)
        finally:
            os.remove(path)
        self.assertEqual(list(reloaded.doc["pages"]), original_pages)
        self.assertEqual(set(reloaded.doc["nodes"].keys()), original_ids)
        self.assertEqual(reloaded.doc["nodes"][str(first)]["name"], "00_Foundations")
        self.assertEqual(reloaded.doc["nodes"][str(second)]["name"], "02_Screens")
        self.assertEqual(reloaded.doc["nodes"][str(archive)]["name"], "01_Archive")
        self.assertGreaterEqual(reloaded.doc["next_id"], doc.doc["next_id"])


class MultiPageAuditTests(unittest.TestCase):
    def make_two_page_doc(self):
        doc = FigcraftDocument("audit-pages")
        archive = doc.add_page("01_Archive")
        add_valid_board(doc, doc.doc["pages"][0], "00_Foundations")
        add_valid_board(doc, archive, "02_Screens")
        return doc, archive

    def test_all_pages_audited_and_no_false_positives(self):
        doc, _ = self.make_two_page_doc()
        path = save_temp(doc)
        try:
            self.assertEqual(audit_render.audit_file(path), [])
            self.assertEqual(audit_render.audit_file(path, page_index=0), [])
        finally:
            os.remove(path)

    def test_defect_on_later_page_is_detected_and_filtered(self):
        doc, archive = self.make_two_page_doc()
        board = doc.doc["nodes"][str(archive)]["children"][0]
        doc.doc["nodes"][str(board)]["clip"] = False
        path = save_temp(doc)
        try:
            # audit_file reuses a shared list, so snapshot each result.
            failures = list(audit_render.audit_file(path))
            first_page = list(audit_render.audit_file(path, page_index=0))
            named = list(audit_render.audit_file(path, page_name="01_Archive"))
            invalid = None
            try:
                audit_render.audit_file(path, page_index=9)
            except ValueError as exc:
                invalid = str(exc)
        finally:
            os.remove(path)
        self.assertEqual(len(failures), 1)
        self.assertIn("01_Archive", failures[0])
        self.assertIn("clip: false", failures[0])
        self.assertEqual(first_page, [])
        self.assertEqual(named, failures)
        self.assertIsNotNone(invalid)
        self.assertIn("out of range", invalid)


class TerminalPageSelectorTests(unittest.TestCase):
    def payload(self):
        return {"result": {"pages": [
            {"id": 1, "name": "Main", "children": [
                {"id": 10, "name": "MainBoard", "type": "FRAME",
                 "x": 0, "y": 0, "width": 100, "height": 100}]},
            {"id": 2, "name": "Archive", "children": [
                {"id": 20, "name": "ArchiveBoard", "type": "FRAME",
                 "x": 0, "y": 0, "width": 100, "height": 100}]},
        ]}}

    def test_select_inspect_page_by_index_and_name(self):
        payload = self.payload()
        page, index = agent_terminal.select_inspect_page(payload, page_index=1)
        self.assertEqual(index, 1)
        self.assertEqual(page["name"], "Archive")
        page, index = agent_terminal.select_inspect_page(
            payload, page_name="Archive")
        self.assertEqual(index, 1)
        self.assertEqual(page["name"], "Archive")
        self.assertEqual(agent_terminal.select_inspect_page(
            payload, page_name="Missing"), (None, None))

    def test_list_frames_honors_page_name(self):
        term = agent_terminal.FigcraftTerminal(port=9999)
        with mock.patch.object(term, "send_rpc", return_value=self.payload()):
            result = term.list_frames(page_name="Archive")
        self.assertTrue(result["ok"])
        self.assertEqual(result["page_index"], 1)
        # The page container itself is not a frame: exporting it would
        # duplicate every screen under a page-named PNG.
        self.assertEqual([frame["name"] for frame in result["frames"]],
                         ["ArchiveBoard"])


if __name__ == "__main__":
    unittest.main()
