"""Regression tests for the seven verified v3.2.3 tool defects."""

import contextlib
import io
import json
import math
import os
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import agent_terminal as at  # noqa: E402
import audit_render  # noqa: E402
import figcraft_tool as ft  # noqa: E402
import harness_detect as hd  # noqa: E402
import multi_agent_worker as mw  # noqa: E402

COLORS = ft.TOKENS["colors"]


def temp_figcraft():
    """Create an empty temporary archive path owned by the calling test."""
    fd, path = tempfile.mkstemp(suffix=".figcraft")
    os.close(fd)
    return path


def read_document(path):
    with zipfile.ZipFile(path, "r") as archive:
        return json.loads(archive.read("document.json").decode("utf-8"))


class StartStateFileTests(unittest.TestCase):
    """Defect 1: state files survive CLI exit and die only on stop/stale PID."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = tmp.name
        self.pid_file = os.path.join(root, ".figcraft.pid.9877")
        self.port_file = os.path.join(root, ".figcraft.port.9877")
        self.active_file = os.path.join(root, ".figcraft.active.9877.json")
        self.design = temp_figcraft()
        self.addCleanup(lambda: os.path.exists(self.design) and os.remove(self.design))
        self.patches = [
            mock.patch.object(at, "PID_FILE", self.pid_file),
            mock.patch.object(at, "PORT_FILE", self.port_file),
            mock.patch.object(at, "ACTIVE_FILE", self.active_file),
            mock.patch.object(at, "DEFAULT_APP_PATH", sys.executable),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.term = at.FigcraftTerminal(port=9877)
        self.proc = mock.Mock(pid=424242)

    def _start(self):
        with mock.patch.object(at.subprocess, "Popen", return_value=self.proc), \
                mock.patch.object(self.term, "is_port_listening",
                                  return_value=False), \
                mock.patch("atexit.register") as register, \
                contextlib.redirect_stdout(io.StringIO()):
            result = self.term.start_server(file_path=self.design,
                                            wait_ready=False)
        return result, register

    def test_start_registers_no_atexit_cleanup_and_keeps_state(self):
        result, register = self._start()
        self.assertTrue(result["ok"])
        self.assertEqual(result["pid"], 424242)
        register.assert_not_called()
        for path in (self.pid_file, self.port_file, self.active_file):
            self.assertTrue(os.path.exists(path), path)

    def test_explicit_stop_removes_all_state_files(self):
        self._start()
        with mock.patch.object(at.os, "kill", side_effect=ProcessLookupError), \
                mock.patch.object(self.term, "_terminate_proc") as terminate, \
                contextlib.redirect_stdout(io.StringIO()):
            result = self.term.stop_server()
        self.assertTrue(result["ok"])
        self.assertEqual(result["pid"], 424242)
        terminate.assert_called_once_with(self.proc)
        for path in (self.pid_file, self.port_file, self.active_file):
            self.assertFalse(os.path.exists(path), path)

    def test_dead_pid_detection_clears_state_but_live_pid_is_kept(self):
        for path, payload in ((self.pid_file, "99999999"),
                              (self.port_file, "9877"),
                              (self.active_file, '{"active_file": "x"}')):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(payload)
        self.assertTrue(self.term.cleanup_dead_pid_state())
        self.assertFalse(os.path.exists(self.pid_file))
        self.assertFalse(os.path.exists(self.port_file))
        self.assertFalse(os.path.exists(self.active_file))

        with open(self.pid_file, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        with open(self.port_file, "w", encoding="utf-8") as handle:
            handle.write("9877")
        self.assertFalse(self.term.cleanup_dead_pid_state())
        self.assertTrue(os.path.exists(self.pid_file))
        self.assertTrue(os.path.exists(self.port_file))


class FreeformLayoutTests(unittest.TestCase):
    """Defect 2: layout.mode == 'none' is never written to document.json."""

    def test_create_frame_omits_layout_for_freeform_frames(self):
        doc = ft.FigcraftDocument("freeform")
        frame_id = doc.create_frame("Freeform", 1, 300.0, 200.0)
        self.assertNotIn("layout", doc.doc["nodes"][str(frame_id)])
        auto_id = doc.create_frame("Auto", 1, 300.0, 200.0,
                                   layout_mode="vertical")
        self.assertEqual(doc.doc["nodes"][str(auto_id)]["layout"]["mode"],
                         "vertical")

    def test_save_strips_authored_mode_none_from_loaded_nodes(self):
        doc = ft.FigcraftDocument("freeform-save")
        authored = {
            "id": 9001, "name": "CoverArtFrame", "type": "frame",
            "parent": 1, "children": [], "width": 120.0, "height": 160.0,
            "transform": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            "layout": {"mode": "none", "gap": 0.0},
        }
        doc.add_node(authored)
        path = temp_figcraft()
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with contextlib.redirect_stderr(io.StringIO()):
            doc.save(path)
        payload = json.dumps(read_document(path), separators=(",", ":"))
        self.assertNotIn('"mode":"none"', payload)
        self.assertNotIn("layout", read_document(path)["nodes"]["9001"])


class MergeLayoutTests(unittest.TestCase):
    """Defect 3: ASTPartitionMerger.merge_subtrees resolves layout before save."""

    def test_merged_shards_have_sized_text_and_positioned_transforms(self):
        doc = ft.FigcraftDocument("master")
        doc.create_frame("Board", 1, 400.0, 300.0, fill=COLORS["bg"])
        path = temp_figcraft()
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with contextlib.redirect_stderr(io.StringIO()):
            doc.save(path)

        nodes = {
            "2001": {
                "id": 2001, "name": "MergedRow", "type": "frame",
                "parent": 1, "children": [2002],
                "transform": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
                "width": 320.0, "height": 48.0,
                "layout": {"mode": "horizontal", "gap": 8.0,
                           "padding": [10.0, 12.0, 10.0, 12.0],
                           "main_align": "min", "cross_align": "min"},
            },
            "2002": {
                "id": 2002, "name": "MergedLabel", "type": "text",
                "parent": 2001, "characters": "COMPLETED",
                "transform": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
                "width": 0.0, "height": 0.0,
                "fills": ft.make_solid_fill(COLORS["text"]),
                "style": {"font_size": 12.0, "font_family": "JetBrains Mono"},
                "child_layout": {"sizing_h": "hug", "sizing_v": "hug"},
            },
        }
        merger = mw.ASTPartitionMerger(path)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertTrue(merger.merge_subtrees(
                [{"page": 1, "root_id": 2001, "nodes": nodes}]))

        merged = read_document(path)
        text = merged["nodes"]["2002"]
        self.assertGreater(text["width"], 0.0)
        self.assertGreater(text["height"], 0.0)
        self.assertNotEqual(text["transform"][4:6], [0.0, 0.0])
        self.assertIn(2001, merged["nodes"]["1"]["children"])
        self.assertFalse(os.path.exists(path + ".lock"))


class TextWidthAndAlignmentTests(unittest.TestCase):
    """Defect 4: calibrated glyph widths and align_h serialization."""

    def test_estimate_matches_measured_engine_glyph_widths(self):
        self.assertAlmostEqual(ft.estimate_text_width("Left to right", 13.0),
                               73.0, delta=1.0)
        self.assertAlmostEqual(ft.estimate_text_width("COMPLETED", 12.0,
                                                      "JetBrains Mono"),
                               60.0, delta=1.0)
        self.assertLess(ft.TEXT_WIDTH_RATIO_SANS, 0.52)
        self.assertLess(ft.TEXT_WIDTH_RATIO_MONO, 0.62)

    def test_align_h_is_serialized_and_text_align_alias_is_normalized(self):
        doc = ft.FigcraftDocument("alignment")
        panel = doc.create_frame("Panel", 1, 300.0, 90.0)
        right = doc.create_text("RightValue", "Left to right", panel,
                                font_size=13.0, align_h="right")
        centered = doc.create_text("CenteredValue", "COMPLETED", panel,
                                   font_size=11.0, text_align="center")
        aliased = doc.create_text("AliasValue", "ON", panel,
                                  font_size=11.0, text_align="start")
        self.assertEqual(doc.doc["nodes"][str(right)]["align_h"], "right")
        self.assertEqual(doc.doc["nodes"][str(centered)]["align_h"], "center")
        self.assertEqual(doc.doc["nodes"][str(aliased)]["align_h"], "left")

        authored = {
            "id": 9100, "name": "RawValue", "type": "text", "parent": panel,
            "characters": "85%", "transform": [1, 0, 0, 1, 0, 0],
            "width": 0.0, "height": 0.0,
            "text_align": "right",
            "child_layout": {"sizing_h": "hug", "sizing_v": "hug"},
        }
        doc.add_node(authored)
        path = temp_figcraft()
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with contextlib.redirect_stderr(io.StringIO()):
            doc.save(path)
        raw = json.dumps(read_document(path), separators=(",", ":"))
        self.assertNotIn('"text_align"', raw)
        self.assertEqual(read_document(path)["nodes"]["9100"]["align_h"],
                         "right")


class EllipseSeamTests(unittest.TestCase):
    """Defect 5: full circles omit arc fields; partial arcs keep them."""

    def test_full_circles_omit_sweep_and_start(self):
        doc = ft.FigcraftDocument("circles")
        for name, kwargs in (
            ("DiscDefault", {}),
            ("DiscTau", {"sweep": math.tau}),
            ("DiscLegacy", {"sweep": 6.2831853}),
        ):
            nid = doc.create_ellipse(name, 1, 20.0, COLORS["action-primary"],
                                     **kwargs)
            node = doc.doc["nodes"][str(nid)]
            self.assertNotIn("sweep", node)
            self.assertNotIn("start", node)

    def test_partial_arc_keeps_arc_fields(self):
        doc = ft.FigcraftDocument("arc")
        nid = doc.create_ellipse("Arc", 1, 20.0, COLORS["action-primary"],
                                 start=0.5, sweep=math.pi)
        node = doc.doc["nodes"][str(nid)]
        self.assertAlmostEqual(node["start"], 0.5)
        self.assertAlmostEqual(node["sweep"], math.pi)

    def test_save_normalizes_legacy_full_circle_arc_fields(self):
        doc = ft.FigcraftDocument("circle-save")
        doc.add_node({
            "id": 9200, "name": "LegacyCircle", "type": "ellipse",
            "parent": 1, "width": 24.0, "height": 24.0,
            "transform": [1, 0, 0, 1, 0, 0], "start": 0.0,
            "sweep": 6.2831853, "fills": ft.make_solid_fill(COLORS["action-primary"]),
        })
        doc.add_node({
            "id": 9201, "name": "RealArc", "type": "ellipse",
            "parent": 1, "width": 24.0, "height": 24.0,
            "transform": [1, 0, 0, 1, 0, 0], "start": 0.25,
            "sweep": 1.5, "fills": ft.make_solid_fill(COLORS["action-primary"]),
        })
        path = temp_figcraft()
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with contextlib.redirect_stderr(io.StringIO()):
            doc.save(path)
        nodes = read_document(path)["nodes"]
        self.assertNotIn("sweep", nodes["9200"])
        self.assertNotIn("start", nodes["9200"])
        self.assertAlmostEqual(nodes["9201"]["sweep"], 1.5)


class AuditHardeningTests(unittest.TestCase):
    """Defect 6: explicit failure on broken boards and safe typography."""

    def audit(self, doc):
        path = temp_figcraft()
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with contextlib.redirect_stderr(io.StringIO()):
            doc.save(path)
        return audit_render.audit_file(path)

    def test_page_with_no_children_fails_explicitly(self):
        doc = ft.FigcraftDocument("empty-page")
        failures = self.audit(doc)
        self.assertTrue(any("page has 0 children" in item
                            for item in failures))
        self.assertTrue(any("Page 'Page 1': 0 children" in item
                            for item in ft.lint_design(doc)))

    def test_zero_size_and_zero_child_boards_fail_explicitly(self):
        doc = ft.FigcraftDocument("empty-boards")
        doc.create_frame("00_ZeroSize", 1, 0.0, 0.0, fill=COLORS["bg"])
        doc.create_frame("01_NoChildren", 1, 320.0, 240.0, fill=COLORS["bg"])
        failures = self.audit(doc)
        warnings = ft.lint_design(doc)
        self.assertTrue(any("non-positive size" in item for item in failures))
        self.assertTrue(any("non-positive" in item for item in warnings))
        self.assertTrue(any("0 children" in item for item in failures))
        self.assertTrue(any("0 children" in item for item in warnings))

    def test_duplicate_child_ids_are_reported(self):
        doc = ft.FigcraftDocument("duplicates")
        board = doc.create_frame("02_Duplicates", 1, 320.0, 240.0,
                                 fill=COLORS["bg"])
        child = doc.create_rect("Swatch", board, 40.0, 40.0,
                                fill=COLORS["action-primary"])
        doc.doc["nodes"][str(board)]["children"] = [child, child]
        failures = self.audit(doc)
        warnings = ft.lint_design(doc)
        self.assertTrue(any("duplicate child id" in item for item in failures))
        self.assertTrue(any("duplicate child id" in item for item in warnings))

    def test_piled_freeform_siblings_are_reported_but_autolayout_is_not(self):
        doc = ft.FigcraftDocument("pileup")
        freeform = doc.create_frame("03_Freeform", 1, 320.0, 240.0,
                                    fill=COLORS["bg"])
        doc.create_rect("TileOne", freeform, 40.0, 40.0,
                        fill=COLORS["action-primary"])
        doc.create_rect("TileTwo", freeform, 40.0, 40.0,
                        fill=COLORS["action-primary"])
        auto = doc.create_frame("04_Auto", 1, 320.0, 240.0,
                                fill=COLORS["bg"], layout_mode="vertical")
        doc.create_rect("AutoTileOne", auto, 40.0, 40.0,
                        fill=COLORS["action-primary"])
        doc.create_rect("AutoTileTwo", auto, 40.0, 40.0,
                        fill=COLORS["action-primary"])
        failures = self.audit(doc)
        warnings = ft.lint_design(doc)
        self.assertTrue(any("03_Freeform" in item and "piled at (0,0)" in item
                            for item in failures))
        self.assertTrue(any("03_Freeform" in item and "piled at (0,0)" in item
                            for item in warnings))
        self.assertFalse(any("04_Auto" in item and "piled at (0,0)" in item
                             for item in failures + warnings))

    def test_typographic_punctuation_is_safe_but_foreign_text_is_flagged(self):
        doc = ft.FigcraftDocument("typography")
        board = doc.create_frame("05_Typography", 1, 420.0, 320.0,
                                 fill=COLORS["bg"], clip=True)
        for index, caption in enumerate((
            "Slide · 280ms",
            "Quiet reading mode — ON",
            "★ 4.8 | 12.4K",
        )):
            doc.create_text("Caption%d" % index, caption, board,
                            font_size=11.0, color=COLORS["text"])
        self.assertFalse([item for item in self.audit(doc)
                          if "S-15" in item])
        # Build the non-English fixture from a code point so the test source
        # itself stays plain English.
        foreign = chr(0x653B) + " Reading"
        doc.create_text("ForeignCaption", foreign, board,
                        font_size=11.0, color=COLORS["text"])
        self.assertTrue(any("S-15" in item and foreign in item
                            for item in self.audit(doc)))


class FrameExportAndHarnessTests(unittest.TestCase):
    """Defect 7: frames excludes pages; Orca/Antigravity are detected."""

    @staticmethod
    def inspect_payload():
        return {"result": {"pages": [{
            "id": 1, "name": "00_Foundations", "type": "page",
            "children": [
                {"id": 10, "name": "foundations-token-guide", "type": "FRAME",
                 "x": 0, "y": 0, "width": 1280, "height": 960},
            ],
        }]}}

    def test_extract_frames_and_list_frames_skip_page_containers(self):
        frames, _ = at.extract_frames(self.inspect_payload())
        self.assertEqual([frame["name"] for frame in frames],
                         ["foundations-token-guide"])
        term = at.FigcraftTerminal(port=9998)
        with mock.patch.object(term, "send_rpc",
                               return_value=self.inspect_payload()):
            result = term.list_frames()
        self.assertTrue(result["ok"])
        self.assertEqual([frame["name"] for frame in result["frames"]],
                         ["foundations-token-guide"])

    def test_export_all_never_exports_a_page_named_duplicate(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        term = at.FigcraftTerminal(port=9998)
        page_frame = {"id": 1, "name": "00_Foundations", "type": "page",
                      "x": None, "y": None, "w": None, "h": None}
        screen = {"id": 10, "name": "foundations-token-guide", "type": "frame",
                  "x": 0.0, "y": 0.0, "w": 1280.0, "h": 960.0}
        with mock.patch.object(term, "list_frames", return_value={
                "ok": True, "frames": [page_frame, screen], "page_index": 0}), \
                mock.patch.object(term, "projected_page") as projected, \
                mock.patch.object(term, "export_frame",
                                  return_value={"ok": True, "path": "x.png"}) as export:
            projected.return_value.__enter__.return_value = False
            result = term.export_all(tmp.name)
        self.assertEqual(result["count"], 1)
        self.assertEqual([item["name"] for item in result["exported"]],
                         ["foundations-token-guide"])
        self.assertTrue(any("page container" in str(item.get("reason"))
                            for item in result["skipped"]))
        self.assertEqual(export.call_count, 1)

    def test_orca_and_antigravity_markers_are_detected(self):
        for key in ("ORCA_CLI_COMMAND", "ORCA_SESSION_ID",
                    "ORCA_ENVIRONMENT", "ORCA_TERMINAL_HANDLE"):
            with self.subTest(marker=key):
                self.assertEqual(hd.detect_harness({key: "1"}), "orca")
        for key in ("ANTIGRAVITY_SESSION_ID", "GEMINI", "GEMINI_SESSION_ID"):
            with self.subTest(marker=key):
                self.assertEqual(hd.detect_harness({key: "1"}), "antigravity")
        self.assertEqual(hd.detect_harness({"TERM_PROGRAM": "Orca"}), "orca")
        self.assertEqual(hd.detect_harness(
            {"ORCA_SESSION_ID": "1", "CLAUDECODE": "1"}), "orca")
        self.assertEqual(hd.detect_harness({}), "unknown")

    def test_harness_info_reports_orca_runtime(self):
        with mock.patch.dict(os.environ, {"ORCA_SESSION_ID": "session"},
                             clear=True), \
                mock.patch.object(sys, "argv",
                                  ["agent_terminal.py", "harness-info"]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            at.main()
        self.assertEqual(json.loads(output.getvalue())["runtime_harness"],
                         "orca")


if __name__ == "__main__":
    unittest.main()
