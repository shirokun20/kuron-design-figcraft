"""Stage 5 remediation: swatch borders, dedicated pages, and page export."""

import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import agent_terminal  # noqa: E402
import audit_render  # noqa: E402
import figcraft_tool as ft  # noqa: E402
import quick_design as qd  # noqa: E402
from figcraft_tool import FigcraftDocument, TOKENS  # noqa: E402

BOARD_W = 1376.0
BOARD_H = 976.0


def save_temp(doc):
    """Save a document to a temporary .figcraft path."""
    fd, path = tempfile.mkstemp(suffix=".figcraft")
    os.close(fd)
    doc.save(path)
    return path


def digest(path):
    """Read a file's bytes hash for a no-mutation assertion."""
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def named_node(doc, name):
    """Return the first node with this name, or None."""
    for node in doc.doc["nodes"].values():
        if isinstance(node, dict) and node.get("name") == name:
            return node
    return None


class FoundationsLayoutTests(unittest.TestCase):
    def build_board(self):
        doc = FigcraftDocument("foundations-layout")
        board = ft.ensure_board(doc, "00_Foundations", width=BOARD_W, height=BOARD_H)
        qd.build_foundations(doc, board, width=BOARD_W, height=BOARD_H)
        return doc, board

    def test_all_twelve_swatches_have_a_one_pixel_line_stroke(self):
        doc, _ = self.build_board()
        swatches = [node for node in doc.doc["nodes"].values()
                    if isinstance(node, dict) and node.get("name") == "SwatchPaint"]
        self.assertEqual(len(swatches), 12)
        expected = ft._lint_hex(ft.make_solid_stroke(TOKENS["colors"]["line"])[0]["color"])
        for swatch in swatches:
            self.assertTrue(swatch.get("strokes"))
            self.assertEqual(ft._lint_hex(swatch["strokes"][0]["color"]), expected)
            self.assertEqual(swatch.get("stroke_weight"), 1.0)

    def test_two_columns_fill_over_65_percent_of_board_width(self):
        doc, board = self.build_board()
        bounds = audit_render.content_bounds(doc.doc["nodes"], board)
        self.assertIsNotNone(bounds)
        coverage = (bounds[2] - bounds[0]) / BOARD_W
        self.assertGreaterEqual(coverage, 0.65)
        inner = BOARD_W - qd.SPACE["xl"] * 2
        right_x = qd.SPACE["xl"] + inner / 2 + qd.SPACE["lg"]
        title = named_node(doc, "TypeScaleTitle")
        self.assertEqual(title["transform"][4], right_x)
        token_title = named_node(doc, "TokenTitle")
        self.assertEqual(token_title["transform"][4], right_x)
        self.assertEqual(named_node(doc, "ColorRolesTitle")["transform"][4],
                         qd.SPACE["xl"])


class DedicatedPagesTests(unittest.TestCase):
    def test_three_boards_live_on_three_dedicated_named_pages(self):
        doc = qd.generate_preset("three-pages", "dedicated-pages")
        names = [doc.doc["nodes"][str(pid)]["name"] for pid in doc.page_ids()]
        self.assertEqual(names, ["00_Foundations", "01_Components", "02_Screens"])
        for pid, name in zip(doc.page_ids(), names):
            children = doc.doc["nodes"][str(pid)]["children"]
            self.assertEqual([doc.doc["nodes"][str(c)]["name"] for c in children],
                             [name])

    def test_cross_page_reuse_copies_a_component_to_another_page(self):
        doc = qd.generate_preset("three-pages", "cross-page")
        template = ft.find_or_reuse_component(doc, "Card")
        self.assertIsNotNone(template)
        page_id = doc.resolve_page(page_name="02_Screens")
        screens = doc.doc["nodes"][str(page_id)]["children"][0]
        copy = doc.duplicate_node(template, parent_id=screens, name="CardCopy")
        self.assertIsNotNone(copy)
        self.assertEqual(doc.doc["nodes"][str(copy)]["parent"], screens)
        self.assertIn(copy, doc.doc["nodes"][str(screens)]["children"])
        self.assertEqual(ft.find_or_reuse_component(
            doc, "CardCopy", page_name="02_Screens"), copy)

    def test_separate_pages_audit_without_false_positives(self):
        doc = qd.generate_preset("three-pages", "audit-pages")
        path = save_temp(doc)
        try:
            self.assertEqual(audit_render.audit_file(path), [])
            self.assertEqual(audit_render.audit_file(path, page_name="01_Components"), [])
        finally:
            os.remove(path)


class PageProjectionTests(unittest.TestCase):
    def two_page_file(self):
        doc = FigcraftDocument("projection-source")
        doc.add_page("01_Components")
        ft.ensure_board(doc, "00_Foundations", width=900, height=700,
                        fill=TOKENS["colors"]["bg"])
        ft.ensure_board(doc, "01_Components", width=900, height=700,
                        fill=TOKENS["colors"]["bg"], page_name="01_Components",
                        x=1100)
        return save_temp(doc)

    def test_projection_promotes_target_page_without_touching_source(self):
        path = self.two_page_file()
        before = digest(path)
        temp_path = None
        try:
            temp_path, page_id = agent_terminal.project_page(path, page_index=1)
            self.assertNotEqual(temp_path, path)
            self.assertTrue(os.path.exists(temp_path))
            with zipfile.ZipFile(temp_path) as archive:
                projected = json.load(archive.open("document.json"))
            self.assertEqual(projected["pages"], [page_id])
            self.assertEqual(projected["current_page"], page_id)
            self.assertEqual(digest(path), before)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            os.remove(path)

    def test_export_all_non_zero_page_restores_source_and_removes_projection(self):
        path = self.two_page_file()
        before = digest(path)
        out_dir = tempfile.mkdtemp()
        term = agent_terminal.FigcraftTerminal(port=9999)
        opened, closed = [], []

        def fake_execute(command, params=None):
            if command == "file.open":
                opened.append(params["path"])
            elif command == "file.close":
                closed.append(params.get("force"))
            return {"ok": True}

        def fake_export(node_id, out_path, **kwargs):
            with open(out_path, "wb") as handle:
                handle.write(b"png")
            return {"ok": True, "path": out_path}

        try:
            with mock.patch.object(agent_terminal, "effective_design_path",
                                   return_value=path), \
                 mock.patch.object(agent_terminal, "write_active_file"), \
                 mock.patch.object(term, "execute_command", side_effect=fake_execute), \
                 mock.patch.object(term, "list_frames", return_value={
                     "ok": True, "count": 1, "page_index": 1,
                     "frames": [{"id": 99, "name": "01_Components"}]}), \
                 mock.patch.object(term, "export_frame", side_effect=fake_export):
                result = term.export_all(out_dir, page_index=1)
            self.assertTrue(result["ok"])
            self.assertTrue(result["projected_page"])
            self.assertEqual(len(opened), 2)
            self.assertNotEqual(opened[0], path)
            self.assertEqual(opened[1], path)
            self.assertEqual(closed, [True, True])
            self.assertEqual(digest(path), before)
            self.assertFalse(os.path.exists(opened[0]))
        finally:
            for name in os.listdir(out_dir):
                os.remove(os.path.join(out_dir, name))
            os.rmdir(out_dir)
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
