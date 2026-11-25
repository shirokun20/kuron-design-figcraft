"""Builder contract tests (anatomi SKILL §8) — converted to unittest.

Jalankan: python3 -m unittest discover -s tests -p 'test_*.py' -v
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from figcraft_tool import FigcraftDocument, TOKENS, _lint_hex  # noqa: E402

C = TOKENS["colors"]


def kids(doc, nid):
    nodes = doc.doc["nodes"]
    return [nodes[str(c)] for c in nodes[str(nid)].get("children", [])]


def all_text(doc):
    return " ".join(
        str(t.get("characters", ""))
        for t in doc.doc["nodes"].values()
        if isinstance(t, dict) and t.get("type") == "text"
    )


class BuilderContractTests(unittest.TestCase):
    def test_dialog_has_scrim_dialog_primary_and_cancel(self):
        doc = FigcraftDocument("dlg")
        d = doc.build_dialog(
            "DelDlg", "Hapus 3 halaman?",
            "3 halaman dan 41 terjemahan ikut terhapus.",
            "Hapus 3 halaman", 1, width=1280.0, height=960.0)
        names = [n.get("name") for n in kids(doc, d)]
        self.assertIn("Scrim", names)
        self.assertIn("Dialog", names)
        flat = all_text(doc)
        self.assertIn("Hapus 3 halaman", flat)
        self.assertIn("Batal", flat)

    def test_empty_state_has_title_description_action_no_illustration(self):
        doc = FigcraftDocument("emp")
        doc.build_empty_state("Empty", "Belum ada halaman",
                              "Impor PDF untuk mulai.", "Impor PDF", 1)
        flat = all_text(doc)
        for needle in ("Belum ada halaman", "Impor PDF untuk mulai", "Impor PDF"):
            self.assertIn(needle, flat)

    def test_error_inline_has_cause_solution_retry(self):
        doc = FigcraftDocument("err")
        doc.build_error_inline("Err429", "Terjemahan gagal (429).",
                               "Tunggu 2 detik lalu pilih Coba lagi.", 1)
        flat = all_text(doc)
        self.assertIn("Terjemahan gagal (429)", flat)
        self.assertIn("Coba lagi", flat)

    def test_ledger_row_has_six_columns(self):
        doc = FigcraftDocument("led")
        row = doc.build_ledger_row("R1", "#", "Hlm", "Asli", "Hasil", "Muat",
                                   "Dicek", 1, state="cursor")
        types = [n.get("type") for n in kids(doc, row)]
        self.assertGreaterEqual(sum(1 for t in types if t == "text"), 6)

    def test_pipeline_bar_five_stages_active_coral(self):
        doc = FigcraftDocument("pipe")
        doc.build_pipeline_bar(1, active_stage=3)
        flat = all_text(doc)
        for needle in ("Import", "Export", "3. Translate"):
            self.assertIn(needle, flat)
        corals = [
            t for t in doc.doc["nodes"].values()
            if isinstance(t, dict) and t.get("type") == "text"
            and (t.get("fills") or [{}])[0].get("color") is not None
            and _lint_hex((t.get("fills") or [{}])[0].get("color") or {}) == "#ff6b5a"
        ]
        self.assertTrue(any("Translate" in str(t.get("characters", "")) for t in corals))

    def test_save_runs_reflow_and_box_centers_text(self):
        doc = FigcraftDocument("reflow")
        row = doc.create_frame("Row", 1, 300.0, 32.0, fill=C["surface_card"],
                               layout_mode="horizontal", cross_align="center")
        tg = doc.create_text("Lbl", "DeepSeek Chat (V3)", row, font_size=12.0)
        fd, path = tempfile.mkstemp(suffix=".figcraft")
        os.close(fd)
        try:
            doc.save(path)
        finally:
            if os.path.exists(path):
                os.remove(path)
        node = doc.doc["nodes"][str(tg)]
        self.assertAlmostEqual(node["transform"][5], (32 - node["height"]) / 2, delta=0.2)
        self.assertNotEqual(node["transform"][5], 0.0)


if __name__ == "__main__":
    unittest.main()
