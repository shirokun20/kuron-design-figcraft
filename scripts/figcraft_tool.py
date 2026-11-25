#!/usr/bin/env python3
"""
FigCraft CLI & Automation Toolkit
Provides live control over FigCraft.app (via JSON-RPC TCP socket)
and offline programmatic manipulation of .figcraft design files.
Designed for Antigravity, Claude Code, Muse Code, and OMP.
"""

import sys
import os
import json
import zipfile
import socket
import subprocess
import time
import argparse
from typing import Dict, List, Optional, Any, Union, Tuple

# Make sibling modules (e.g. build_artistic_flow) importable from any cwd.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# ---------------------------------------------------------------------------
# DESIGN TOKENS (Kuron Studio Design System)
# ---------------------------------------------------------------------------
TOKENS = {
    "colors": {
        # Surfaces — 1:1 dengan token --ks-* di references/design-tokens.css (dark default)
        "bg_app": "#0d0d10",            # Canvas / frame terdalam (--ks-bg)
        "surface": "#141418",           # Latar utama halaman (--ks-surface)
        "surface_2": "#1a1a20",         # Panel, sidebar, toolbar (--ks-surface-2)
        "surface_card": "#22222a",       # Kartu, container raised (--ks-raised)
        "surface_active": "#2a2a33",     # Hover / state aktif (--ks-hover)
        "border": "#26262e",             # Separator 1px (--ks-line)
        "border_subtle": "#26262e",      # Garis halus (--ks-line)
        "border_accent": "#35353f",      # Border tegas dialog / jendela (--ks-line-strong)

        # Inks (tipografi)
        "ink_primary": "#ececf1",    # Judul, teks utama (--ks-text)
        "ink_secondary": "#a5a6b0",  # Teks tubuh, metadata (--ks-text-2)
        "ink_muted": "#71727d",      # Placeholder, non-aktif (--ks-text-3)

        # Aksen coral = aksi utama SAJA
        "coral": "#ff6b5a",          # Primary CTA (--ks-accent)
        "coral_hover": "#ff8272",    # Hover aksi utama (--ks-accent-hover)
        "coral_fg": "#1a0a08",       # Teks di atas coral (--ks-accent-fg)
        "coral_subtle": "#2e1614",   # Latar soft badge coral (--ks-accent-soft)
        # Cyan = info teknis saja. DILARANG memakai neon #00e5ff — pakai #35e7f5.
        "cyan": "#35e7f5",           # Info teknis (--ks-cyan)
        "cyan_subtle": "#0e2a2e",    # Latar soft cyan (--ks-cyan-soft)
        "success": "#5fd99a",        # Selesai / online (--ks-success)
        "success_subtle": "#10281d",  # Latar badge selesai (--ks-success-soft)
        "warning": "#ffc15e",        # Berjalan / perlu cek (--ks-warn)
        "warning_subtle": "#2b2110",  # Latar badge berjalan (--ks-warn-soft)
        "danger": "#ff5c5c",         # Destruktif / error (--ks-danger)
        "danger_subtle": "#2e1416",   # Latar badge error (--ks-danger-soft)
        "info": "#6ba6ff",           # Status info netral (--ks-info)
        "info_subtle": "#111e33",    # Latar badge info (--ks-info-soft)

        # Seleksi & fokus — BUKAN dekorasi, BUKAN border statis.
        "ring": "#9a9aa8",          # Cincin fokus keyboard + halo seleksi (--ks-ring; light #55555f)
        "selected": "#34343f",      # Latar baris terpilih persisten (--ks-selected; light #d8d7d1)
    },
    "typography": {
        "font_ui": "Inter",
        "font_brand": "Space Grotesk",
        "font_mono": "JetBrains Mono",
        "sizes": {
            "hero": 28.0,
            "title": 20.0,
            "heading": 15.0,
            "body": 13.0,
            "caption": 11.0,
            "badge": 10.0,
        }
    },
    "radii": {
        "control": 6.0,   # Buttons, inputs, small tags
        "badge": 9999.0,  # Pills / round badges
        "card": 12.0,     # Cards, modals, dialogs
        "window": 16.0,   # Outer application windows / screens
    },
    "sizes": {
        "btn_sm": 28.0,
        "btn_md": 32.0,   # Default button height
        "btn_lg": 40.0,
        "field": 36.0,    # Input field height
        "icon_sm": 16.0,  # DESIGN.md: ikon sm
        "icon_md": 20.0,  # DESIGN.md: ikon md (default)
        "icon_lg": 24.0,  # DESIGN.md: ikon lg
        "header": 32.0,   # App header = 32px (patterns.md Window Bar; bukan 44)
        "window_bar": 32.0,
    }
}

def hex_to_rgba(hex_str: str, alpha: float = 1.0) -> Dict[str, float]:
    """Convert hex color (#RRGGBB or #RRGGBBAA) to FigCraft RGBA float dict (0.0 - 1.0)."""
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 8:
        r = int(hex_str[0:2], 16) / 255.0
        g = int(hex_str[2:4], 16) / 255.0
        b = int(hex_str[4:6], 16) / 255.0
        a = (int(hex_str[6:8], 16) / 255.0) * alpha
    elif len(hex_str) == 6:
        r = int(hex_str[0:2], 16) / 255.0
        g = int(hex_str[2:4], 16) / 255.0
        b = int(hex_str[4:6], 16) / 255.0
        a = alpha
    elif len(hex_str) == 3:
        r = int(hex_str[0]*2, 16) / 255.0
        g = int(hex_str[1]*2, 16) / 255.0
        b = int(hex_str[2]*2, 16) / 255.0
        a = alpha
    else:
        r, g, b, a = 1.0, 1.0, 1.0, alpha
    return {"r": round(r, 4), "g": round(g, 4), "b": round(b, 4), "a": round(a, 4)}

def make_solid_fill(hex_str: str, opacity: float = 1.0) -> List[Dict[str, Any]]:
    return [{
        "type": "solid",
        "color": hex_to_rgba(hex_str),
        "opacity": opacity,
        "visible": True,
        "blend": "normal"
    }]

def make_solid_stroke(hex_str: str, opacity: float = 1.0) -> List[Dict[str, Any]]:
    return [{
        "type": "solid",
        "color": hex_to_rgba(hex_str),
        "opacity": opacity,
        "visible": True,
        "blend": "normal"
    }]

# ---------------------------------------------------------------------------
# TEKS & IKON (estimasi + Lucide; dipakai create_text/build_button)
# ---------------------------------------------------------------------------
def estimate_text_width(text: str, font_size: float, font_family: str = "Inter") -> float:
    """Estimasi lebar teks px (sama rumus dengan test_layout_engine.py).

    Mono ~0.62*size, Space Grotesk ~0.58*size, lainnya ~0.52*size, +2 padding.
    Dipakai create_text/build_button supaya headless tidak meluap.
    Kalibrasi 2026-11-08: median engine/app = 0.94x estimasi lama
    (0.55) utk Latin; CJK ~0.98 (tak diubah). Estimasi sengaja sedikit
    konservatif (box >= glyph) supaya tak terpotong.
    """
    if "Mono" in font_family:
        return len(text) * font_size * 0.62 + 2
    if "Space" in font_family or "Grotesk" in font_family:
        return len(text) * font_size * 0.58 + 2
    return len(text) * font_size * 0.52 + 2


# Path ikon Lucide v0.469.0 (grid 24, stroke round) untuk tombol.
# Skala = icon_dim/24. Jangan gambar ikon sebagai rect outline.
ICON_PATHS = {
    "x": ["M18 6 6 18", "m6 6 12 12"],
    "check": ["M20 6 9 17l-5-5"],
    "chevron-down": ["m6 9 6 6 6-6"],
    "chevron-right": ["m9 18 6-6-6-6"],
    "chevron-left": ["m15 18-6-6 6-6"],
    "plus": ["M5 12h14", "M12 5v14"],
    "minus": ["M5 12h14"],
    "arrow-right": ["M5 12h14", "m12 5 7 7-7 7"],
    "arrow-left": ["M19 12H5", "m12 19-7-7 7-7"],
}


# ---------------------------------------------------------------------------
# FIGCRAFT DOCUMENT OBJECT (OFFLINE FILE BUILDER)
# ---------------------------------------------------------------------------
class FigcraftDocument:
    """Represents a .figcraft design document (ZIP archive containing document.json)."""

    def __init__(self, name: str = "Untitled"):
        self.name = name
        self.doc: Dict[str, Any] = {
            "format": "figcraft",
            "version": 1,
            "imageIndex": [],
            "name": name,
            "pages": [1],
            "current_page": 1,
            "next_id": 10,
            "styles": [],
            "variables": {"collections": [], "variables": []},
            "document_colors": [],
            "comments": [],
            "nodes": {}
        }
        # Create default Page 1
        self.doc["nodes"]["1"] = {
            "id": 1,
            "name": "Page 1",
            "type": "page",
            "background": hex_to_rgba(TOKENS["colors"]["bg_app"]),
            "children": [],
            "flows": [],
            "guides": [],
            "prototype": {
                "device": "None",
                "background": hex_to_rgba(TOKENS["colors"]["bg_app"]),
                "rotation": "portrait"
            },
            "width": 0.0,
            "height": 0.0
        }
        self.file_path: Optional[str] = None

    @classmethod
    def load(cls, file_path: str) -> "FigcraftDocument":
        """Load an existing .figcraft file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        inst = cls()
        inst.file_path = file_path
        with zipfile.ZipFile(file_path, "r") as z:
            with z.open("document.json") as f:
                inst.doc = json.load(f)
        inst.name = inst.doc.get("name", os.path.splitext(os.path.basename(file_path))[0])
        return inst

    def resolve_layout(self):
        """Recursively resolves two-pass AutoLayout for all pages and screens."""
        try:
            from build_artistic_flow import resolve_tree_layout
        except ImportError as exc:
            raise RuntimeError(
                "build_artistic_flow.py wajib ada di direktori scripts/ yang sama "
                "dengan figcraft_tool.py (resolve_tree_layout)"
            ) from exc
        for pid in self.doc.get("pages", [1]):
            page = self.doc["nodes"].get(str(pid))
            if page:
                for sid in page.get("children", []):
                    resolve_tree_layout(self.doc["nodes"], sid)

    def save(self, output_path: Optional[str] = None):
        """Save the document to .figcraft file."""
        try:
            self.resolve_layout()
        except Exception as e:
            # Dulu except-pass diam: menutupi mistake reflow. Sekarang
            # warn-only ke stderr (build tetap jalan, SKILL §2).
            print(f"figcraft_tool: resolve_layout gagal ({e}) — save tanpa reflow.",
                  file=sys.stderr)

        # Guard multi-page (SKILL §7.4): engine live + export hanya
        # memuat subtree pages[0]; page kedua tak terlihat walau valid.
        if len(self.doc.get("pages", [1])) > 1:
            print("figcraft_tool: dokumen multi-page — engine hanya memuat "
                  f"pages[0] {self.doc.get('pages')}. Pindahkan diagram ke "
                  "file terpisah bila page non-pertama tak ter-render.",
                  file=sys.stderr)

        path = output_path or self.file_path
        if not path:
            raise ValueError("No file path specified for save.")
        
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        
        # 1x1 transparent PNG thumbnail placeholder if not already there
        png_1x1 = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        
        existing_thumb = None
        if self.file_path and os.path.exists(self.file_path):
            try:
                with zipfile.ZipFile(self.file_path, "r") as z:
                    if "thumbnail.png" in z.namelist():
                        existing_thumb = z.read("thumbnail.png")
            except Exception:
                pass

        temp_path = path + ".tmp"
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            # Compact seperti engine (SKILL §7.3: skema dari save-live):
            # indent=2 menggembungkan document.json 2x lipat tanpa manfaat.
            z.writestr("document.json", json.dumps(self.doc, separators=(",", ":")))
            z.writestr("thumbnail.png", existing_thumb or png_1x1)
        
        os.replace(temp_path, path)
        self.file_path = path

    def alloc_id(self) -> int:
        cur = self.doc.get("next_id", 10)
        self.doc["next_id"] = cur + 1
        return cur

    def add_node(self, node: Dict[str, Any], parent_id: int = 1) -> int:
        nid = node.get("id")
        if not nid:
            nid = self.alloc_id()
            node["id"] = nid
        
        node["parent"] = parent_id
        self.doc["nodes"][str(nid)] = node

        # Append to parent's children list
        parent = self.doc["nodes"].get(str(parent_id))
        if parent:
            if "children" not in parent:
                parent["children"] = []
            if nid not in parent["children"]:
                parent["children"].append(nid)

        return nid

    # --- Node Creation Helpers ---

    def create_frame(
        self,
        name: str,
        parent_id: int = 1,
        width: float = 100.0,
        height: float = 100.0,
        x: float = 0.0,
        y: float = 0.0,
        fill: Optional[str] = None,
        stroke: Optional[str] = None,
        stroke_width: float = 1.0,
        corner_radius: float = 0.0,
        layout_mode: str = "none",  # "none" | "horizontal" | "vertical" | "grid"
        gap: float = 0.0,
        padding: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
        main_align: str = "min",    # "min" | "center" | "max" | "spaceBetween"
        cross_align: str = "min",   # "min" | "center" | "max"
        sizing_h: str = "fixed",    # "fixed" | "hug" | "fill"
        sizing_v: str = "fixed",    # "fixed" | "hug" | "fill"
        clip: bool = False
    ) -> int:
        nid = self.alloc_id()
        frame_node = {
            "id": nid,
            "name": name,
            "type": "frame",
            "parent": parent_id,
            "children": [],
            "transform": [1.0, 0.0, 0.0, 1.0, float(x), float(y)],
            "width": float(width),
            "height": float(height),
            "clip": clip,
        }
        if fill:
            frame_node["fills"] = make_solid_fill(fill)
        else:
            frame_node["fills"] = []

        if stroke:
            frame_node["strokes"] = make_solid_stroke(stroke)
            frame_node["stroke_weight"] = float(stroke_width)

        if corner_radius > 0:
            frame_node["corners"] = {
                "radii": [corner_radius, corner_radius, corner_radius, corner_radius],
                "smoothing": 0.0
            }

        if layout_mode != "none":
            t, r, b, l = padding
            frame_node["layout"] = {
                "mode": layout_mode,
                "wrap": False,
                "gap": float(gap),
                "cross_gap": float(gap),
                "padding": [float(t), float(r), float(b), float(l)],
                "main_align": main_align,
                "cross_align": cross_align,
                "content_align": "auto",
                "grid_columns": 2,
                "grid_rows": 2,
                "column_tracks": [],
                "row_tracks": [],
                "strokes_included": True,
                "reverse_z": False
            }

        # Child sizing inside parent layout
        if parent_id != 1:
            frame_node["child_layout"] = {
                "sizing_h": sizing_h,
                "sizing_v": sizing_v,
                "absolute": False,
                "min_w": None, "max_w": None,
                "min_h": None, "max_h": None,
                "grid_column": None, "grid_row": None,
                "grid_column_span": 0, "grid_row_span": 0
            }

        return self.add_node(frame_node, parent_id)

    def create_text(
        self,
        name: str,
        text: str,
        parent_id: int,
        font_size: float = 13.0,
        font_weight: str = "Regular", # "Regular" | "Medium" | "SemiBold" | "Bold"
        font_family: str = "Inter",
        color: str = "#ffffff",
        x: float = 0.0,
        y: float = 0.0,
        width: Optional[float] = None,
        height: Optional[float] = None,
        sizing_h: str = "hug",
        sizing_v: str = "hug",
        max_w: Optional[float] = None,
    ) -> int:
        # R1: lawan text-overflow (node 1020 279px meluap dari card 233.6px).
        # Paritas engine 2026-11-08: reflow TIDAK menimpa ukuran teks yang
        # sudah terukur (save app memakai metrik font asli). Karena itu
        # create menyimpan 0 (kosong) bila pemanggil tak memberi eksplisit;
        # reflow mengisi via estimasi HANYA saat kosong. S-08 tetap hijau
        # karena lint melihat hasil pasca-save, bukan angka lahir.
        # Truncation visual urusan renderer; width tersimpan harus jujur.
        estimated = estimate_text_width(text, font_size, font_family)
        if width is None:
            width = 0.0
        elif estimated > width:
            width = min(estimated, max_w) if max_w else estimated
        if height is None:
            height = 0.0
        nid = self.alloc_id()
        text_node = {
            "id": nid,
            "name": name,
            "type": "text",
            "parent": parent_id,
            "characters": text,
            "transform": [1.0, 0.0, 0.0, 1.0, float(x), float(y)],
            "width": float(width),
            "height": float(height),
            "fills": make_solid_fill(color),
            "style": {
                "font_family": font_family,
                "font_style": font_weight,
                "font_size": float(font_size),
                "line_height": {"unit": "auto"},
                "letter_spacing": {"unit": "pixels", "value": 0.0},
                "decoration": "none",
                "case": "original",
                "fills": None,
                "link": None
            },
            "child_layout": {
                "sizing_h": sizing_h,
                "sizing_v": sizing_v,
                "absolute": False,
                "min_w": None, "max_w": None,
                "min_h": None, "max_h": None,
                "grid_column": None, "grid_row": None,
                "grid_column_span": 0, "grid_row_span": 0
            }
        }
        return self.add_node(text_node, parent_id)

    def create_vector(
        self,
        name: str,
        path_data: List[str],
        parent_id: int,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 12.0,
        height: float = 12.0,
        stroke: Optional[str] = None,
        stroke_width: float = 1.5,
    ) -> int:
        """Vektor ikon (Lucide 24-grid) dengan skema file ASLI engine.

        Dibuktikan via live session (probe node → save → baca document.json):
        engine menyimpan vector network {vertices[{x,y,radius}],
        segments[{a,b,ta,tb}], regions[]}, BUKAN string path. SEMANTIK
        TRANSFORM: posisi render = transform tersimpan apa adanya; engine
        live MENAMBAH bbox-min saat create via API. Karena file dibaca
        mentah, path DINORMALISASI dulu (bbox-min → 0,0, skala width/24)
        sehingga transform (x, y) = posisi render persis — tak perlu koreksi
        node.set. Warna stroke = list `strokes` (paint solid) + metadata
        `stroke` (weight/align/cap round ala Lucide); KEDUANYA wajib ada —
        file tanpa `strokes` ter-render tak terlihat. Lihat log untuk konteks.
        """
        import re as _re
        scale = float(width) / 24.0 if width else 1.0

        def _subpaths() -> List[List[Tuple[float, float]]]:
            """Parse path menjadi daftar subpath (satu per M/m; Z menutup).

            Segment HANYA menghubungkan titik dalam subpath yang sama —
            segmen lintas-subpath menggambar garis liar (mistake: ikon x
            berekor diagonal). Kurva C dipecah per titik kontrol
            (aproksimasi terdokumentasi, cukup untuk set ikon Lucide).
            """
            subs: List[List[Tuple[float, float]]] = []
            cur: List[Tuple[float, float]] = []
            for d in path_data:
                # Tiap string path independen (satu atribut d SVG): titik
                # awal kembali ke (0,0). Tanpa ini, "m12 5..." pada string
                # kedua panah dihitung dari ujung string pertama (meluber
                # ke 31,36 di luar grid 24).
                cx = cy = sx = sy = 0.0
                toks = _re.findall(r"[MmLlHhVvCcZz]|-?\d*\.?\d+", d)
                cmd = "M"
                i = 0
                while i < len(toks):
                    t = toks[i]
                    if _re.fullmatch(r"[MmLlHhVvCcZz]", t):
                        cmd = t
                        i += 1
                        continue
                    if cmd == "Z":
                        if cur:
                            cur.append((sx, sy))
                        i += 1
                        continue
                    # SVG: pasangan koordinat setelah M/m = lineto implisit.
                    # Tanpa ini, "M18 6 6 18" pecah jadi 2 subpath 1-titik
                    # (ikon x kehilangan segmennya).
                    if cmd == "M":
                        if cur:
                            subs.append(cur)
                        cur = []
                        cx, cy = float(toks[i]), float(toks[i + 1])
                        i += 2
                        sx, sy = cx, cy
                        cur.append((cx, cy))
                        cmd = "L"
                        continue
                    if cmd == "m":
                        if cur:
                            subs.append(cur)
                        cur = []
                        cx, cy = cx + float(toks[i]), cy + float(toks[i + 1])
                        i += 2
                        sx, sy = cx, cy
                        cur.append((cx, cy))
                        cmd = "l"
                        continue
                    if cmd in "ML":
                        cx, cy = float(toks[i]), float(toks[i + 1])
                        i += 2
                    elif cmd in "ml":
                        cx, cy = cx + float(toks[i]), cy + float(toks[i + 1])
                        i += 2
                    elif cmd == "H":
                        cx = float(toks[i])
                        i += 1
                    elif cmd == "h":
                        cx = cx + float(toks[i])
                        i += 1
                    elif cmd == "V":
                        cy = float(toks[i])
                        i += 1
                    elif cmd == "v":
                        cy = cy + float(toks[i])
                        i += 1
                    elif cmd in "Cc":
                        vals = [float(toks[i + k]) for k in range(6)]
                        if cmd == "c":
                            vals = [vals[0] + cx, vals[1] + cy, vals[2] + cx,
                                    vals[3] + cy, vals[4] + cx, vals[5] + cy]
                        cur.extend([(vals[0], vals[1]), (vals[2], vals[3])])
                        cx, cy = vals[4], vals[5]
                        i += 6
                    else:
                        raise ValueError(f"create_vector: perintah path '{cmd}' tak didukung")
                    cur.append((cx, cy))
            if cur:
                subs.append(cur)
            if not subs:
                raise ValueError("create_vector: path kosong, tak ada titik")
            return subs

        subs = _subpaths()
        all_pts = [p for sub in subs for p in sub]
        min_x = min(p[0] for p in all_pts)
        min_y = min(p[1] for p in all_pts)
        verts: List[Dict[str, float]] = []
        segs: List[Dict[str, Any]] = []
        for sub in subs:
            base = len(verts)
            for px, py in sub:
                verts.append({
                    "x": round((px - min_x) * scale, 3),
                    "y": round((py - min_y) * scale, 3),
                    "radius": 0.0,
                })
            segs.extend(
                {"a": base + k, "b": base + k + 1, "ta": [0.0, 0.0], "tb": [0.0, 0.0]}
                for k in range(len(sub) - 1)
            )
        max_x = max((v["x"] for v in verts), default=0.0)
        max_y = max((v["y"] for v in verts), default=0.0)
        nid = self.alloc_id()
        vec_node: Dict[str, Any] = {
            "id": nid,
            "name": name,
            "type": "vector",
            "network": {"vertices": verts, "segments": segs, "regions": []},
            "parent": parent_id,
            "blend": "normal",
            "transform": [1.0, 0.0, 0.0, 1.0, float(x), float(y)],
            "width": float(max_x),
            "height": float(max_y),
        }
        if stroke:
            # Renderer file membaca `strokes` (list, dicat warna) + `stroke`
            # (dict metadata weight/align/cap). Dibuktikan: live-create yang
            # ter-render menyimpan KEDUANYA; file tanpa `strokes` = tak
            # terlihat walau network valid (regions[] kosong → fills tak
            # berpengaruh pada subpath terbuka).
            vec_node["fills"] = []
            vec_node["strokes"] = make_solid_stroke(stroke)
            vec_node["stroke"] = {
                "weight": float(stroke_width),
                "align": "center",
                "sides": None,
                "cap_start": "round",
                "cap_end": "round",
                "join": "round",
                "miter_limit": 4.0,
                "dashes": [],
            }
        else:
            vec_node["fills"] = []
        return self.add_node(vec_node, parent_id)

    def build_connector(
        self,
        name: str,
        from_id: int,
        to_id: int,
        parent_id: int,
        from_side: str = "right",  # "right"|"left"|"top"|"bottom" (tengah sisi)
        to_side: str = "left",      # "right"|"left"|"top"|"bottom"
        style: str = "solid",       # "solid" | "dashed"
        color: Optional[str] = None,
        width: float = 2.0,
        offset: float = 0.0,        # geser garis tengah (mis. loopback ke atas)
    ) -> int:
        """Panah ortogonal antar node (S-03) — pengganti vektor ad-hoc.

        Anchor di tengah sisi; rute Manhattan dengan satu siku; kepala
        panah searah segmen terakhir. Jaringan = piksel mentah (bukan
        grid-24 create_vector). Topologi from->to eksplisit sehingga
        panah yatim / terbalik tertangkap saat review.
        """
        nodes = self.doc["nodes"]
        a, b = nodes[str(from_id)], nodes[str(to_id)]
        ax, ay, aw, ah = a["transform"][4], a["transform"][5], a["width"], a["height"]
        bx, by, bw, bh = b["transform"][4], b["transform"][5], b["width"], b["height"]

        def anchor(x, y, w, h, side):
            return {
                "right": (x + w, y + h / 2), "left": (x, y + h / 2),
                "bottom": (x + w / 2, y + h), "top": (x + w / 2, y),
            }[side]

        p1, p2 = anchor(ax, ay, aw, ah, from_side), anchor(bx, by, bw, bh, to_side)
        x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
        if from_side in ("left", "right") and to_side in ("left", "right"):
            if y1 == y2:
                pts = [p1, p2]
            else:
                mx = (x1 + x2) / 2.0
                pts = [p1, (mx, y1), (mx, y2), p2]
        elif from_side in ("top", "bottom") and to_side in ("top", "bottom"):
            if x1 == x2 and not offset:
                pts = [p1, p2]
            else:
                my = (y1 + y2) / 2.0 + offset
                pts = [p1, (x1, my), (x2, my), p2]
        elif from_side in ("left", "right"):
            pts = [p1, p2] if y1 == y2 else [p1, (x2, y1), p2]
        else:
            pts = [p1, p2] if x1 == x2 else [p1, (x1, y2), p2]
        # Kepala panah searah segmen terakhir.
        (qx, qy), (tx, ty) = pts[-2], pts[-1]
        head = 10.0
        dx = 1 if tx > qx else (-1 if tx < qx else 0)
        dy = 1 if ty > qy else (-1 if ty < qy else 0)
        base = (tx - dx * head, ty - dy * head)
        if dx:
            wings = [(base[0], base[1] - head * 0.55), (tx, ty), (base[0], base[1] + head * 0.55)]
        else:
            wings = [(base[0] - head * 0.55, base[1]), (tx, ty), (base[0] + head * 0.55, base[1])]
        main = pts[:-1] + [base]
        subpaths = [main, wings]
        verts, segs = [], []
        for sub in subpaths:
            base_i = len(verts)
            for px, py in sub:
                verts.append({"x": round(px, 3), "y": round(py, 3), "radius": 0.0})
            segs.extend(
                {"a": base_i + k, "b": base_i + k + 1, "ta": [0.0, 0.0], "tb": [0.0, 0.0]}
                for k in range(len(sub) - 1))
        stroke_color = color or TOKENS["colors"]["ink_muted"]
        node = {
            "id": self.alloc_id(), "name": name, "type": "vector",
            "network": {"vertices": verts, "segments": segs, "regions": []},
            "parent": 0, "blend": "normal",
            "transform": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            "width": max(v["x"] for v in verts),
            "height": max(v["y"] for v in verts),
            "fills": [], "strokes": make_solid_stroke(stroke_color),
            "stroke": {"weight": float(width), "align": "center", "sides": None,
                       "cap_start": "round", "cap_end": "round",
                       "join": "round", "miter_limit": 4.0,
                       "dashes": [6.0, 4.0] if style == "dashed" else []},
        }
        return self.add_node(node, parent_id)

    # ------------------------------------------------------------------
    # Builder v2.4 (kontrak SKILL §8): dialog, empty, error, ledger, pipe
    # ------------------------------------------------------------------
    def build_dialog(
        self,
        name: str,
        title: str,
        body_text: str,
        confirm_label: str,
        parent_id: int,
        width: float = 1280.0,
        height: float = 960.0,
    ) -> int:
        """Modal: scrim + kartu + header(tanya+Tutup) + body + footer(1 primer + Batal)."""
        wrap = self.create_frame(name, parent_id, width, height,
                                 fill=None, sizing_h="fill", sizing_v="fill")
        scrim = self.create_frame("Scrim", wrap, width, height,
                                 fill="#0a0a0d", sizing_h="fill", sizing_v="fill")
        self.doc["nodes"][str(scrim)]["fills"][0]["opacity"] = 0.6
        dw, dh = 480.0, 300.0
        card = self.create_frame("Dialog", wrap, dw, dh,
                                 x=(width - dw) / 2.0, y=(height - dh) / 2.0,
                                 fill=TOKENS["colors"]["surface_card"],
                                 stroke=TOKENS["colors"]["border_accent"],
                                 corner_radius=12.0, layout_mode="vertical",
                                 gap=0.0, padding=(0.0, 0.0, 0.0, 0.0),
                                 sizing_h="fixed", sizing_v="fixed")
        head = self.create_frame("DialogHeader", card, dw, 56.0,
                                 layout_mode="horizontal", gap=8.0,
                                 padding=(12.0, 16.0, 12.0, 16.0),
                                 main_align="spaceBetween", cross_align="center",
                                 sizing_h="fill", sizing_v="fixed")
        self.create_text("Title", title, head, font_size=15.0,
                         font_weight="SemiBold",
                         font_family=TOKENS["typography"]["font_brand"],
                         color=TOKENS["colors"]["ink_primary"])
        self.build_button("Btn_Tutup", "Tutup", head, variant="ghost", size="sm")
        dbody = self.create_frame("DialogBody", card, dw, 120.0,
                                  layout_mode="vertical", gap=6.0,
                                  padding=(8.0, 16.0, 8.0, 16.0),
                                  sizing_h="fill", sizing_v="fixed")
        self.create_text("Body", body_text, dbody, font_size=13.0,
                         color=TOKENS["colors"]["ink_secondary"])
        foot = self.create_frame("DialogFooter", card, dw, 64.0,
                                 layout_mode="horizontal", gap=8.0,
                                 padding=(12.0, 16.0, 12.0, 16.0),
                                 main_align="max", cross_align="center",
                                 sizing_h="fill", sizing_v="fixed")
        self.build_button("Btn_Confirm", confirm_label, foot,
                          variant="primary", size="md")
        self.build_button("Btn_Batal", "Batal", foot,
                          variant="ghost", size="md")
        return wrap

    def build_empty_state(
        self,
        name: str,
        title: str,
        desc: str,
        action_label: str,
        parent_id: int,
        width: float = 400.0,
    ) -> int:
        """Keadaan kosong: judul + deskripsi + aksi. Tanpa ilustrasi."""
        box = self.create_frame(name, parent_id, width, 180.0,
                                fill=None, layout_mode="vertical", gap=12.0,
                                padding=(24.0, 24.0, 24.0, 24.0),
                                sizing_h="fixed", sizing_v="fixed")
        self.create_text("Title", title, box, font_size=15.0,
                         font_weight="SemiBold",
                         color=TOKENS["colors"]["ink_primary"])
        self.create_text("Desc", desc, box, font_size=13.0,
                         color=TOKENS["colors"]["ink_secondary"])
        self.build_button("Btn_Action", action_label, box,
                          variant="primary", size="md")
        return box

    def build_error_inline(
        self,
        name: str,
        message: str,
        fix: str,
        parent_id: int,
    ) -> int:
        """Galat inline: badge danger + sebab + jalan keluar + [Coba lagi]."""
        row = self.create_frame(name, parent_id, 420.0, 96.0,
                                fill=TOKENS["colors"]["danger_subtle"],
                                stroke=None, corner_radius=8.0,
                                layout_mode="horizontal", gap=12.0,
                                padding=(12.0, 16.0, 12.0, 16.0),
                                cross_align="center",
                                sizing_h="fixed", sizing_v="fixed")
        self.build_badge("Bdg_Err", "GALAT", row, tone="danger")
        col = self.create_frame("Col", row, 280.0, 72.0,
                                layout_mode="vertical", gap=2.0,
                                sizing_h="fill", sizing_v="hug")
        self.create_text("Msg", message, col, font_size=13.0,
                         font_weight="SemiBold",
                         color=TOKENS["colors"]["ink_primary"])
        self.create_text("Fix", fix, col, font_size=12.0,
                         color=TOKENS["colors"]["ink_secondary"])
        self.build_button("Btn_Retry", "Coba lagi", row,
                          variant="ghost", size="sm")
        return row

    def build_ledger_row(
        self,
        name: str,
        c_num: str,
        c_page: str,
        c_src: str,
        c_dst: str,
        c_fit: str,
        c_check: str,
        parent_id: int,
        state: str = "plain",  # "plain" | "cursor" | "selected"
    ) -> int:
        """Baris tabel ledger: 6 kolom + separator 1px + state."""
        fill = TOKENS["colors"]["surface_card"]
        if state == "cursor":
            fill = TOKENS["colors"]["surface_active"]
        elif state == "selected":
            fill = TOKENS["colors"]["selected"]
        row = self.create_frame(name, parent_id, 640.0, 42.0, fill=fill,
                                stroke=TOKENS["colors"]["border"],
                                corner_radius=0.0, layout_mode="horizontal",
                                gap=8.0, padding=(6.0, 12.0, 6.0, 12.0),
                                cross_align="center",
                                sizing_h="fixed", sizing_v="fixed")
        for cname, txt, w in (("C_Num", c_num, 36.0), ("C_Page", c_page, 60.0),
                              ("C_Src", c_src, 170.0), ("C_Dst", c_dst, 170.0),
                              ("C_Fit", c_fit, 80.0), ("C_Chk", c_check, 60.0)):
            self.create_text(cname, txt, row, font_size=11.0,
                             font_family=TOKENS["typography"]["font_mono"],
                             color=TOKENS["colors"]["ink_secondary"],
                             width=w, max_w=w)
        return row

    def create_rect(
        self,
        name: str,
        parent_id: int,
        width: float,
        height: float,
        fill: Optional[str] = None,
        stroke: Optional[str] = None,
        stroke_width: float = 1.0,
        corner_radius: float = 0.0,
        x: float = 0.0,
        y: float = 0.0,
        sizing_h: str = "fixed",
        sizing_v: str = "fixed"
    ) -> int:
        nid = self.alloc_id()
        rect_node = {
            "id": nid,
            "name": name,
            "type": "rectangle",
            "parent": parent_id,
            "transform": [1.0, 0.0, 0.0, 1.0, float(x), float(y)],
            "width": float(width),
            "height": float(height),
            "fills": make_solid_fill(fill) if fill else [],
            "strokes": make_solid_stroke(stroke) if stroke else [],
            "stroke_weight": float(stroke_width) if stroke else 0.0,
            "child_layout": {
                "sizing_h": sizing_h,
                "sizing_v": sizing_v,
                "absolute": False,
                "min_w": None, "max_w": None,
                "min_h": None, "max_h": None,
                "grid_column": None, "grid_row": None,
                "grid_column_span": 0, "grid_row_span": 0
            }
        }
        if corner_radius > 0:
            rect_node["corners"] = {
                "radii": [corner_radius, corner_radius, corner_radius, corner_radius],
                "smoothing": 0.0
            }
        return self.add_node(rect_node, parent_id)

    def create_ellipse(
        self,
        name: str,
        parent_id: int,
        size: float,
        fill: str,
        x: float = 0.0,
        y: float = 0.0
    ) -> int:
        nid = self.alloc_id()
        ellipse_node = {
            "id": nid,
            "name": name,
            "type": "ellipse",
            "parent": parent_id,
            "start": 0.0,
            "sweep": 6.2831853,
            "inner": 0.0,
            "transform": [1.0, 0.0, 0.0, 1.0, float(x), float(y)],
            "width": float(size),
            "height": float(size),
            "fills": make_solid_fill(fill),
            "child_layout": {
                "sizing_h": "fixed",
                "sizing_v": "fixed",
                "absolute": False,
                "min_w": None, "max_w": None,
                "min_h": None, "max_h": None,
                "grid_column": None, "grid_row": None,
                "grid_column_span": 0, "grid_row_span": 0
            }
        }
        return self.add_node(ellipse_node, parent_id)

    # -----------------------------------------------------------------------
    # HIGH-LEVEL COMPONENT FACTORY
    # -----------------------------------------------------------------------

    def build_button(
        self,
        name: str,
        label: str,
        parent_id: int,
        variant: str = "default",  # "primary" | "default" | "ghost" | "danger"
        size: str = "md",          # "sm" (28px) | "md" (32px) | "lg" (40px)
        icon_name: Optional[str] = None
    ) -> int:
        """Create a consistent button with auto-layout matching DESIGN.md."""
        height = TOKENS["sizes"]["btn_md"]
        font_size = 12.0
        pad_x = 14.0
        pad_y = 6.0
        if size == "sm":
            height = TOKENS["sizes"]["btn_sm"]
            font_size = 11.0
            pad_x = 10.0
            pad_y = 4.0
        elif size == "lg":
            height = TOKENS["sizes"]["btn_lg"]
            font_size = 14.0
            pad_x = 18.0
            pad_y = 10.0

        if variant == "primary":
            bg = TOKENS["colors"]["coral"]
            stroke = None
            text_color = TOKENS["colors"]["coral_fg"]  # --ks-accent-fg di atas coral
            font_weight = "SemiBold"
        elif variant == "danger":
            bg = TOKENS["colors"]["danger"]
            stroke = None
            text_color = "#ffffff"
            font_weight = "SemiBold"
        elif variant == "ghost":
            bg = None
            stroke = None
            text_color = TOKENS["colors"]["ink_secondary"]
            font_weight = "Medium"
        else: # default
            bg = TOKENS["colors"]["surface_2"]
            stroke = TOKENS["colors"]["border"]
            text_color = TOKENS["colors"]["ink_primary"]
            font_weight = "Medium"

        # R2: ukur label DULU supaya frame tersimpan jujur (headless tidak
        # reflow; dulu width=100 fixed → ikon+label meluap +22px).
        label_w = estimate_text_width(label, font_size, TOKENS["typography"]["font_ui"])
        icon_dim = 0.0
        if icon_name:
            # DESIGN.md: ikon sm/md/lg = 16/20/24, ikut tier ukuran button.
            icon_dim = TOKENS["sizes"]["icon_md"]
            if size == "sm":
                icon_dim = TOKENS["sizes"]["icon_sm"]
            elif size == "lg":
                icon_dim = TOKENS["sizes"]["icon_lg"]
        frame_w = max(100.0, pad_x * 2 + label_w + (icon_dim + 6.0 if icon_dim else 0.0))

        btn_id = self.create_frame(
            name=name,
            parent_id=parent_id,
            width=frame_w,
            height=height,
            fill=bg,
            stroke=stroke,
            corner_radius=TOKENS["radii"]["control"],
            layout_mode="horizontal",
            gap=6.0,
            padding=(pad_y, pad_x, pad_y, pad_x),
            main_align="center",
            cross_align="center",
            sizing_h="hug",
            sizing_v="fixed"
        )

        if icon_name:
            paths = ICON_PATHS.get(icon_name)
            if paths is None:
                print(f"figcraft_tool: ikon '{icon_name}' tak dikenal — slot kosong.",
                      file=sys.stderr)
            else:
                self.create_vector(
                    name=f"icon/{icon_name}",
                    path_data=paths,
                    parent_id=btn_id,
                    width=icon_dim,
                    height=icon_dim,
                    stroke=text_color,
                    stroke_width=1.5
                )

        self.create_text(
            name="label",
            text=label,
            parent_id=btn_id,
            font_size=font_size,
            font_weight=font_weight,
            font_family=TOKENS["typography"]["font_ui"],
            color=text_color
        )
        return btn_id

    def build_badge(
        self,
        name: str,
        text: str,
        parent_id: int,
        tone: str = "cyan"  # "cyan" | "coral" | "ok" | "warn" | "danger" | "info" | "muted"
    ) -> int:
        """Create a semantic badge/chip (quiet workbench: pill penuh, tanpa border)."""
        bg_color = TOKENS["colors"]["surface_2"]
        border_color = None  # Quiet workbench: badge/chip TIDAK memakai border.
        text_color = TOKENS["colors"]["ink_secondary"]

        if tone == "cyan":
            bg_color = TOKENS["colors"]["cyan_subtle"]
            text_color = TOKENS["colors"]["cyan"]
        elif tone == "coral":
            bg_color = TOKENS["colors"]["coral_subtle"]
            text_color = TOKENS["colors"]["coral"]
        elif tone == "ok":
            bg_color = TOKENS["colors"]["success_subtle"]
            text_color = TOKENS["colors"]["success"]
        elif tone == "warn":
            bg_color = TOKENS["colors"]["warning_subtle"]
            text_color = TOKENS["colors"]["warning"]
        elif tone == "danger":
            bg_color = TOKENS["colors"]["danger_subtle"]
            text_color = TOKENS["colors"]["danger"]
        elif tone == "info":
            bg_color = TOKENS["colors"]["info_subtle"]
            text_color = TOKENS["colors"]["info"]

        badge_id = self.create_frame(
            name=name,
            parent_id=parent_id,
            width=50.0,
            height=20.0,
            fill=bg_color,
            stroke=border_color,
            corner_radius=TOKENS["radii"]["badge"],  # pil penuh 9999 (DESIGN.md)
            layout_mode="horizontal",
            gap=4.0,
            padding=(2.0, 8.0, 2.0, 8.0),
            main_align="center",
            cross_align="center",
            sizing_h="hug",
            sizing_v="fixed"
        )

        self.create_text(
            name="text",
            text=text,
            parent_id=badge_id,
            font_size=TOKENS["typography"]["sizes"]["badge"],
            font_weight="SemiBold",
            font_family=TOKENS["typography"]["font_mono"],
            color=text_color
        )
        return badge_id

    def build_window_bar(self, parent_id: int, title: str = "Kuron Studio — Manga Translator") -> int:
        """Build macOS-style top window header."""
        bar_id = self.create_frame(
            name="WindowBar",
            parent_id=parent_id,
            width=1280.0,
            height=TOKENS["sizes"]["window_bar"],
            fill=TOKENS["colors"]["surface_2"],
            stroke=TOKENS["colors"]["border_subtle"],
            layout_mode="horizontal",
            gap=12.0,
            padding=(0.0, 16.0, 0.0, 16.0),
            main_align="spaceBetween",
            cross_align="center",
            sizing_h="fill",
            sizing_v="fixed"
        )
        # Traffic lights
        traffic_id = self.create_frame(
            name="TrafficLights",
            parent_id=bar_id,
            width=52.0,
            height=12.0,
            layout_mode="horizontal",
            gap=8.0,
            sizing_h="hug",
            sizing_v="fixed"
        )
        self.create_ellipse("close", traffic_id, 12.0, "#ff5f56")
        self.create_ellipse("minimize", traffic_id, 12.0, "#ffbd2e")
        self.create_ellipse("maximize", traffic_id, 12.0, "#27c93f")

        # Centered title
        self.create_text(
            name="AppTitle",
            text=title,
            parent_id=bar_id,
            font_size=11.0,
            font_weight="SemiBold",
            font_family=TOKENS["typography"]["font_ui"],
            color=TOKENS["colors"]["ink_secondary"]
        )

        # Right status indicator
        status_id = self.create_frame(
            name="StatusRight",
            parent_id=bar_id,
            width=60.0,
            height=16.0,
            layout_mode="horizontal",
            gap=6.0,
            cross_align="center",
            sizing_h="hug",
            sizing_v="fixed"
        )
        self.create_ellipse("dot_green", status_id, 6.0, TOKENS["colors"]["success"])
        self.create_text("status_text", "Ready", status_id, font_size=10.0, color=TOKENS["colors"]["ink_muted"])

        return bar_id

    def build_pipeline_bar(self, parent_id: int, active_stage: int = 1) -> int:
        """Pipeline Bar: Import -> Detect -> Translate -> Review -> Export"""
        bar_id = self.create_frame(
            name="PipelineBar",
            parent_id=parent_id,
            width=1280.0,
            height=40.0,
            fill=TOKENS["colors"]["surface"],
            stroke=TOKENS["colors"]["border"],
            layout_mode="horizontal",
            gap=12.0,
            padding=(0.0, 20.0, 0.0, 20.0),
            main_align="min",
            cross_align="center",
            sizing_h="fill",
            sizing_v="fixed"
        )

        stages = [
            ("1. Import", "ok"),
            ("2. Detect", "active" if active_stage == 2 else ("ok" if active_stage > 2 else "pending")),
            ("3. Translate", "active" if active_stage == 3 else ("ok" if active_stage > 3 else "pending")),
            ("4. Review", "active" if active_stage == 4 else ("ok" if active_stage > 4 else "pending")),
            ("5. Export", "active" if active_stage == 5 else ("ok" if active_stage > 5 else "pending")),
        ]

        for idx, (label, state) in enumerate(stages):
            if idx > 0:
                self.create_text(f"arrow_{idx}", "→", bar_id, font_size=12.0, color=TOKENS["colors"]["ink_muted"])

            color = TOKENS["colors"]["ink_muted"]
            weight = "Regular"
            bg = None
            if state == "active":
                color = TOKENS["colors"]["coral"]
                weight = "Bold"
                bg = TOKENS["colors"]["coral_subtle"]
            elif state == "ok":
                color = TOKENS["colors"]["ink_primary"]
                weight = "Medium"

            stage_frame = self.create_frame(
                name=f"Stage_{idx+1}",
                parent_id=bar_id,
                width=80.0,
                height=26.0,
                fill=bg,
                corner_radius=4.0,
                layout_mode="horizontal",
                padding=(4.0, 8.0, 4.0, 8.0),
                main_align="center",
                cross_align="center",
                sizing_h="hug",
                sizing_v="fixed"
            )
            self.create_text("label", label, stage_frame, font_size=11.0, font_weight=weight, color=color)

        return bar_id


# ---------------------------------------------------------------------------
# FIGCRAFT CLIENT (LIVE CONTROL SERVER OVER TCP)
# ---------------------------------------------------------------------------
class FigcraftClient:
    """Communicates with running FigCraft app via `--control <port>` TCP JSON-RPC."""

    def __init__(self, port: int = 9880, host: str = "127.0.0.1"):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self._req_id = 0

    def connect(self, timeout: float = 2.0) -> bool:
        """Connect to FigCraft control port."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(timeout)
            self.sock.connect((self.host, self.port))
            return True
        except Exception:
            self.sock = None
            return False

    def is_connected(self) -> bool:
        return self.sock is not None

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def send_command(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a JSON command and return decoded result."""
        if not self.sock:
            raise ConnectionError("Not connected to FigCraft control server.")
        
        self._req_id += 1
        payload = {"id": self._req_id, "method": method}
        if params is not None:
            payload["params"] = params

        req_bytes = json.dumps(payload).encode("utf-8") + b"\n"
        self.sock.sendall(req_bytes)

        # Read JSON response line: socket timeout (set in connect) + hard
        # chunk cap so a chatty/misbehaving server cannot loop forever.
        buf = b""
        for _ in range(1024):  # cut-loop guard
            chunk = self.sock.recv(16384)
            if not chunk:
                break
            buf += chunk
            if b"\n" in buf:
                break

        if not buf:
            raise EOFError("Connection closed by FigCraft control server.")

        return json.loads(buf.decode("utf-8"))

    # High-level RPC methods
    def document_inspect(self) -> Dict[str, Any]:
        return self.send_command("document.inspect")

    def node_get(self, node_id: int) -> Dict[str, Any]:
        return self.send_command("node.get", {"id": node_id})

    def engine_execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.send_command("engine.execute", {"command": command, "params": params or {}})

    def engine_commands(self) -> List[Dict[str, Any]]:
        res = self.send_command("engine.commands")
        return res.get("result", [])

    def export_frame(self, node_id: int, out_path: str, format: str = "png", scale: float = 1.0) -> Dict[str, Any]:
        return self.engine_execute("file.export", {
            "ids": [node_id],
            "format": format,
            "scale": scale,
            "path": os.path.abspath(out_path)
        })

    def save_file(self, path: Optional[str] = None) -> Dict[str, Any]:
        p = {"path": os.path.abspath(path)} if path else {}
        return self.engine_execute("file.save", p)


# ---------------------------------------------------------------------------
# SCREEN BUILDERS (TEMPLATES MATCHING DESIGN.MD)
# ---------------------------------------------------------------------------
def build_workbench_screen(doc: FigcraftDocument, x: float = 40.0, y: float = 40.0) -> int:
    """Build the complete Kuron Studio Desktop Workbench (1280x960)."""
    # Main outer frame (Desktop 1280x960)
    screen_id = doc.create_frame(
        name="1. Workbench",
        parent_id=1,
        width=1280.0,
        height=960.0,
        x=x,
        y=y,
        fill=TOKENS["colors"]["surface"],
        corner_radius=TOKENS["radii"]["window"],
        layout_mode="vertical",
        gap=0.0,
        clip=True
    )

    # 1. Window Bar
    doc.build_window_bar(screen_id, title="Kuron Studio — ONIMASA Ch.12 (P.04)")

    # 2. Pipeline Bar
    doc.build_pipeline_bar(screen_id, active_stage=3)

    # 3. Main Workspace Area (3 Columns: Rail 196px | Canvas 1fr | Inspector 268px)
    body_id = doc.create_frame(
        name="WorkbenchBody",
        parent_id=screen_id,
        width=1280.0,
        height=888.0,
        layout_mode="horizontal",
        gap=0.0,
        sizing_h="fill",
        sizing_v="fill"
    )

    # LEFT RAIL (196px): Page List & Navigator
    left_rail = doc.create_frame(
        name="LeftRail",
        parent_id=body_id,
        width=196.0,
        height=888.0,
        fill=TOKENS["colors"]["surface_2"],
        stroke=TOKENS["colors"]["border"],
        layout_mode="vertical",
        gap=8.0,
        padding=(12.0, 12.0, 12.0, 12.0),
        sizing_h="fixed",
        sizing_v="fill"
    )
    doc.create_text("PagesHeader", "PAGES (41)", left_rail, font_size=11.0, font_weight="Bold", color=TOKENS["colors"]["ink_muted"])
    
    # Page thumbnails list in Left Rail
    for i in range(1, 6):
        is_active = (i == 4)
        page_card = doc.create_frame(
            name=f"PageItem_{i}",
            parent_id=left_rail,
            width=172.0,
            height=48.0,
            fill=TOKENS["colors"]["surface_active"] if is_active else TOKENS["colors"]["surface_card"],
            stroke=TOKENS["colors"]["coral"] if is_active else TOKENS["colors"]["border"],
            corner_radius=TOKENS["radii"]["control"],
            layout_mode="horizontal",
            gap=8.0,
            padding=(6.0, 8.0, 6.0, 8.0),
            cross_align="center",
            sizing_h="fill",
            sizing_v="fixed"
        )
        doc.create_rect("Thumb", page_card, 32.0, 36.0, fill=TOKENS["colors"]["surface_active"], corner_radius=3.0)
        col_text = doc.create_frame(f"Meta_{i}", page_card, width=100.0, height=36.0, layout_mode="vertical", gap=2.0, sizing_h="fill", sizing_v="hug")
        doc.create_text("Title", f"Page {i:02d}", col_text, font_size=11.0, font_weight="SemiBold", color=TOKENS["colors"]["ink_primary"])
        doc.create_text("BubbleCount", f"{12 - i*2} bubbles", col_text, font_size=10.0, font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["cyan"])

    # CENTER CANVAS (1fr): Dark Manga Preview with Coral Bubble Outlines
    center_canvas = doc.create_frame(
        name="CenterCanvas",
        parent_id=body_id,
        width=816.0,
        height=888.0,
        fill=TOKENS["colors"]["bg_app"],
        layout_mode="vertical",
        gap=16.0,
        padding=(24.0, 24.0, 24.0, 24.0),
        main_align="center",
        cross_align="center",
        sizing_h="fill",
        sizing_v="fill"
    )
    
    # Manga Page Mockup
    manga_page = doc.create_frame(
        name="MangaPage_P04",
        parent_id=center_canvas,
        width=520.0,
        height=740.0,
        fill="#f8f8fc",
        stroke="#444455",
        stroke_width=2.0,
        corner_radius=4.0,
        clip=True
    )
    
    # Manga comic panels inside page
    doc.create_rect("PanelTop", manga_page, 480.0, 220.0, fill="#e8e8f0", stroke="#111118", stroke_width=2.0, x=20.0, y=20.0)
    doc.create_rect("PanelMidLeft", manga_page, 230.0, 240.0, fill="#e2e2ec", stroke="#111118", stroke_width=2.0, x=20.0, y=250.0)
    doc.create_rect("PanelMidRight", manga_page, 240.0, 240.0, fill="#dedee8", stroke="#111118", stroke_width=2.0, x=260.0, y=250.0)
    doc.create_rect("PanelBottom", manga_page, 480.0, 210.0, fill="#e4e4ee", stroke="#111118", stroke_width=2.0, x=20.0, y=500.0)

    # Active Detected Speech Bubbles (Highlighted in Coral)
    bubble1 = doc.create_frame("Bubble_01", manga_page, 140.0, 90.0, x=50.0, y=60.0, fill="#ffffff", stroke=TOKENS["colors"]["coral"], stroke_width=2.0, corner_radius=20.0)
    doc.create_text("Txt1", "なに？！本当にあいつが…", bubble1, font_size=11.0, font_weight="Bold", color="#111111", x=12.0, y=14.0, width=116.0, height=60.0)
    
    bubble2 = doc.create_frame("Bubble_02", manga_page, 130.0, 80.0, x=330.0, y=270.0, fill="#ffffff", stroke=TOKENS["colors"]["coral"], stroke_width=2.0, corner_radius=18.0)
    doc.create_text("Txt2", "嘘じゃない。この目で見た。", bubble2, font_size=11.0, font_weight="Bold", color="#111111", x=12.0, y=14.0, width=106.0, height=52.0)

    # RIGHT INSPECTOR (268px): Translation cards & Fit bar
    right_inspector = doc.create_frame(
        name="RightInspector",
        parent_id=body_id,
        width=268.0,
        height=888.0,
        fill=TOKENS["colors"]["surface_2"],
        stroke=TOKENS["colors"]["border"],
        layout_mode="vertical",
        gap=12.0,
        padding=(16.0, 16.0, 16.0, 16.0),
        sizing_h="fixed",
        sizing_v="fill"
    )
    doc.create_text("InspectorTitle", "BUBBLE INSPECTOR #01", right_inspector, font_size=11.0, font_weight="Bold", font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["cyan"])

    # Original Japanese Card
    card_orig = doc.create_frame("CardOriginal", right_inspector, 236.0, 90.0, fill=TOKENS["colors"]["surface_card"], stroke=TOKENS["colors"]["border"], corner_radius=TOKENS["radii"]["control"], layout_mode="vertical", gap=6.0, padding=(10.0, 12.0, 10.0, 12.0), sizing_h="fill", sizing_v="hug")
    doc.create_text("LblOrig", "ASLI (JA)", card_orig, font_size=10.0, font_weight="Bold", color=TOKENS["colors"]["ink_muted"])
    doc.create_text("ValOrig", "なに？！本当にあいつが…", card_orig, font_size=12.0, color=TOKENS["colors"]["ink_primary"])

    # Indonesian Translation Card
    card_trans = doc.create_frame("CardTrans", right_inspector, 236.0, 120.0, fill=TOKENS["colors"]["surface_card"], stroke=TOKENS["colors"]["coral"], stroke_width=1.5, corner_radius=TOKENS["radii"]["control"], layout_mode="vertical", gap=6.0, padding=(10.0, 12.0, 10.0, 12.0), sizing_h="fill", sizing_v="hug")
    doc.create_text("LblTrans", "TERJEMAHAN (ID)", card_trans, font_size=10.0, font_weight="Bold", color=TOKENS["colors"]["coral"])
    doc.create_text("ValTrans", "Apa?! Apa benar dia yang…", card_trans, font_size=13.0, font_weight="SemiBold", color=TOKENS["colors"]["ink_primary"])
    doc.create_text("FitBar", "Fit: 94%  •  2 baris  •  Font: 14pt", card_trans, font_size=10.0, font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["success"])

    # Actions footer inside inspector
    doc.build_button("BtnApply", "Terapkan Terjemahan", right_inspector, variant="primary", size="md")
    doc.build_button("BtnInpaint", "Bersihkan Balon (Inpaint)", right_inspector, variant="default", size="md")

    return screen_id

def build_tokens_screen(doc: FigcraftDocument, x: float = 1360.0, y: float = 40.0) -> int:
    """Build the Design Tokens Living Style Guide Frame."""
    frame_id = doc.create_frame(
        name="03. Design Tokens & Patterns",
        parent_id=1,
        width=1280.0,
        height=960.0,
        x=x,
        y=y,
        fill=TOKENS["colors"]["surface"],
        corner_radius=TOKENS["radii"]["window"],
        layout_mode="vertical",
        gap=20.0,
        padding=(32.0, 40.0, 32.0, 40.0),
        clip=True
    )
    
    # Header
    doc.create_text("TokenHeader", "KURON STUDIO — DESIGN TOKENS & SYSTEM", frame_id, font_size=20.0, font_weight="Bold", color=TOKENS["colors"]["ink_primary"])
    doc.create_text("TokenSub", "Sumber tunggal kebenaran visual. Ikuti token di bawah secara konsisten.", frame_id, font_size=13.0, color=TOKENS["colors"]["ink_secondary"])

    # Colors Section Grid
    doc.create_text("ColorSecTitle", "01 / PALETTE WARNA", frame_id, font_size=13.0, font_weight="Bold", color=TOKENS["colors"]["coral"])
    color_row = doc.create_frame("ColorRow", frame_id, 1200.0, 90.0, layout_mode="horizontal", gap=16.0, sizing_h="fill", sizing_v="hug")
    
    swatches = [
        ("Coral (Aksi Utama)", TOKENS["colors"]["coral"]),
        ("Cyan (Info Teknis)", TOKENS["colors"]["cyan"]),
        ("Surface (Latar)", TOKENS["colors"]["surface"]),
        ("Surface 2 (Panel)", TOKENS["colors"]["surface_2"]),
        ("Card (Elevasi)", TOKENS["colors"]["surface_card"]),
        ("Border (Garis)", TOKENS["colors"]["border"]),
        ("Success (Sukses)", TOKENS["colors"]["success"]),
        ("Danger (Error)", TOKENS["colors"]["danger"]),
    ]
    for name, hex_code in swatches:
        sw = doc.create_frame(f"Sw_{name}", color_row, 130.0, 80.0, fill=TOKENS["colors"]["surface_card"], stroke=TOKENS["colors"]["border"], corner_radius=6.0, layout_mode="vertical", gap=6.0, padding=(8.0, 8.0, 8.0, 8.0), sizing_h="fixed", sizing_v="fixed")
        doc.create_rect("ColorBox", sw, 114.0, 32.0, fill=hex_code, corner_radius=4.0)
        doc.create_text("CName", name, sw, font_size=10.0, font_weight="Medium", color=TOKENS["colors"]["ink_primary"])
        doc.create_text("CHex", hex_code, sw, font_size=9.0, font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["ink_muted"])

    # Components Preview Row
    doc.create_text("CompSecTitle", "02 / KOMPONEN PRIMITIF", frame_id, font_size=13.0, font_weight="Bold", color=TOKENS["colors"]["cyan"])
    comp_row = doc.create_frame("CompRow", frame_id, 1200.0, 80.0, fill=TOKENS["colors"]["surface_2"], stroke=TOKENS["colors"]["border"], corner_radius=8.0, layout_mode="horizontal", gap=20.0, padding=(16.0, 20.0, 16.0, 20.0), cross_align="center", sizing_h="fill", sizing_v="hug")
    
    doc.build_button("BtnPri", "Aksi Coral (Primary)", comp_row, variant="primary", size="md")
    doc.build_button("BtnDef", "Tombol Default", comp_row, variant="default", size="md")
    doc.build_button("BtnDgr", "Hapus", comp_row, variant="danger", size="md")
    doc.build_badge("BdgCyan", "12 BUBBLES", comp_row, tone="cyan")
    doc.build_badge("BdgCoral", "CH.12 ACTIVE", comp_row, tone="coral")
    doc.build_badge("BdgOk", "VERIFIED", comp_row, tone="ok")

    # Typography Scale
    doc.create_text("TypeSecTitle", "03 / TATA TIPOGRAFI", frame_id, font_size=13.0, font_weight="Bold", color=TOKENS["colors"]["ink_primary"])
    type_box = doc.create_frame("TypeBox", frame_id, 1200.0, 180.0, fill=TOKENS["colors"]["surface_2"], stroke=TOKENS["colors"]["border"], corner_radius=8.0, layout_mode="vertical", gap=12.0, padding=(16.0, 24.0, 16.0, 24.0), sizing_h="fill", sizing_v="hug")
    doc.create_text("T1", "Space Grotesk Bold 20pt — Heading & Identitas Proyek", type_box, font_size=20.0, font_weight="Bold", font_family="Space Grotesk", color=TOKENS["colors"]["ink_primary"])
    doc.create_text("T2", "Inter Medium 13pt — Standar UI label, tombol, dan teks instruksi", type_box, font_size=13.0, font_weight="Medium", font_family="Inter", color=TOKENS["colors"]["ink_secondary"])
    doc.create_text("T3", "JetBrains Mono Regular 11pt — Tabular numbers, koordinat [x: 420, y: 180, w: 90], status 94%", type_box, font_size=11.0, font_family="JetBrains Mono", color=TOKENS["colors"]["cyan"])

    return frame_id


# ---------------------------------------------------------------------------
# QUIET-WORKBENCH LINTER (murni: tanpa I/O, warn-only)
# ---------------------------------------------------------------------------
# Warna konten yang sah tapi bukan token UI (kertas manga, tinta cetak,
# traffic light macOS, overlay peredup). Validator tidak menandainya.
_CONTENT_ALLOWLIST = frozenset({
    "#ffffff",  # gelembung manga / teks label tombol
    "#111111",  # tinta teks di atas kertas manga
    "#111118",  # garis panel manga
    "#444455",  # outline halaman manga
    "#f8f8fc",  # kertas halaman manga
    "#e8e8f0", "#e2e2ec", "#dedee8", "#e4e4ee",  # panel komik
    "#ff5f56", "#ffbd2e", "#27c93f",  # traffic light macOS
    "#000000",  # overlay peredup (alpha diabaikan saat banding)
    "#0a0a0d",  # scrim dialog (kegelapan kanvas, bukan token)
    "#121216",  # backdrop mock grid redup (layar 05/07)
    "#16161a",  # label hex swatch gelap (layar 06, data demo)
    "#111115",  # tinta cetak artwork manga (layar 03)
    "#f0f0f5", "#ebebf2",  # kertas halaman manga (layar 03)
    "#555566", "#666677", "#888899",  # tinta cetak/SFX artwork (layar 03)
    "#f7f6f4", "#f1f0ed", "#e8e7e3", "#deddd8",  # swatch terang demo (06) & Light Mode surfaces
    "#d8d7d1", "#55555f",  # swatch demo tambahan (06) & Light Mode selected/ring
    "#dfdfd9", "#c4c3bc", "#7c7c86",  # Light Mode --ks-line, --ks-line-strong, --ks-text-3
    "#c4342a", "#a62a21", "#fbe9e7",  # Light Mode --ks-accent, hover, soft
    "#0b6e78", "#e0f2f4",  # Light Mode --ks-cyan, soft
    "#1f7a4d", "#e4f3ea",  # Light Mode --ks-success, soft
    "#8a5a00", "#fbf0dc",  # Light Mode --ks-warn, soft
    "#b3261e", "#fde8e6",  # Light Mode --ks-danger, soft
    # Kuron Mobile AppColors (Warm physical palette from colors_const.dart)
    "#f1958e", "#e0827e", "#9d555b", "#1a1a1f",  # brand Coral, Muted, Dusty, Dark
    "#1c1816", "#221e1c", "#2a2522", "#2e2926", "#4a3d36", "#d4ccc4", "#9e948c",  # dark theme
    "#efe6dc", "#f5ede4", "#fcf7f0", "#faf3ec", "#d6c8bc", "#2e2722", "#7a6e66", "#c76a62",  # light theme
    "#d48a6a", "#c8a06a",  # warm accent, read gold
})

# Border artwork (bukan chrome UI): garis panel/tinta manga.
_BORDER_CONTENT_ALLOW = frozenset({
    "#111115",  # tinta panel manga (layar 03)
    "#22222a",  # tepi lembar manga (= surface, menyatu kertas, layar 03)
})

_FORBIDDEN_NEON = "#00e5ff"  # DILARANG (patterns.md): pakai --ks-cyan #35e7f5.


def _lint_hex(color: Dict[str, Any]) -> str:
    """Ubah dict RGBA float FigCraft menjadi hex `#rrggbb` (abaikan alpha)."""
    r = int(round(color.get("r", 0) * 255))
    g = int(round(color.get("g", 0) * 255))
    b = int(round(color.get("b", 0) * 255))
    return f"#{r:02x}{g:02x}{b:02x}"


def _lint_paint_hexes(node: Dict[str, Any]) -> List[str]:
    """Ambil semua hex fill+stroke yang terlihat pada satu node."""
    hexes: List[str] = []
    for key in ("fills", "strokes"):
        for paint in node.get(key, []) or []:
            if not paint.get("visible", True):
                continue
            color = paint.get("color")
            if isinstance(color, dict):
                hexes.append(_lint_hex(color))
    return hexes


def lint_design(doc: "FigcraftDocument") -> List[str]:
    """Validasi quiet-workbench atas dokumen (murni, warn-only, tanpa I/O).

    Menerima objek FigcraftDocument maupun dict mentah hasil
    `json.loads(document.json)` (mis. file .figcraft dari disk).
    Memeriksa tiap node dan mengembalikan daftar string peringatan:
    fill/stroke neon terlarang, badge/chip ber-border, border struktural
    berwarna (S-01), token tak dikenal, lebih dari satu coral primer per
    layar, teks cyan non-teknis (S-02), dan teks meluber (S-08).
    """
    warnings: List[str] = []
    raw = doc.doc if hasattr(doc, "doc") else doc
    nodes: Dict[str, Any] = raw.get("nodes", {})
    known = {v.lower() for v in TOKENS["colors"].values()}
    coral = TOKENS["colors"]["coral"].lower()
    cyan = TOKENS["colors"]["cyan"].lower()

    def label(nid: Any, node: Dict[str, Any]) -> str:
        return f"[{nid}] {node.get('name', '?')}"

    # 1-3: cek per node (neon, border badge, token tak dikenal, teks tubuh cyan).
    for nid, node in nodes.items():
        if not isinstance(node, dict) or node.get("type") not in (
            "frame", "rectangle", "ellipse", "text",
        ):
            continue
        hexes = _lint_paint_hexes(node)
        name = str(node.get("name", ""))
        lname = name.lower()

        for h in hexes:
            if h == _FORBIDDEN_NEON:
                warnings.append(
                    f"{label(nid, node)}: fill/stroke {_FORBIDDEN_NEON} "
                    f"terlarang — pakai --ks-cyan {cyan}."
                )

        # R4: template memakai nama Bdg* (BdgCyan/BdgCoral/BdgOk) yang lolos
        # cek substring lama — cocokkan juga prefix bdg + bentuk pil (radius
        # 9999) yang memakai border.
        corners = node.get("corners", {}).get("radii", [0]) if isinstance(node.get("corners"), dict) else [0]
        is_pill_shape = (corners or [0])[0] >= 9000
        looks_like_badge = (
            "badge" in lname or "chip" in lname or "pill" in lname
            or lname.startswith("bdg") or is_pill_shape
        )
        if looks_like_badge and node.get("strokes"):
            warnings.append(
                f"{label(nid, node)}: badge/chip memakai border — "
                "quiet workbench: tanpa border, duduk di atas --ks-*-soft."
            )

        # S-01: border struktural hanya hairline netral. Frame/rectangle
        # ber-stroke warna (cyan/success/warn/...) = border hijacking —
        # dulu lolos karena cek badge hanya melihat nama node.
        if node.get("type") in ("frame", "rectangle") and node.get("strokes"):
            _border_ok = {
                TOKENS["colors"]["border"].lower(),
                TOKENS["colors"].get("border_accent", "").lower(),
                TOKENS["colors"].get("ring", "").lower(),  # fokus keyboard
                coral,  # cincin seleksi aktif (dihitung terpisah)
                "#dfdfd9", "#c4c3bc", "#55555f", "#16161a", "#ffffff", "#c4342a",  # Light Mode + Glass hairlines
                "#4a3d36", "#d6c8bc",  # Kuron Mobile borders (darkBorder, lightBorder)
            } | _BORDER_CONTENT_ALLOW
            for paint in node.get("strokes", []) or []:
                color = paint.get("color")
                if isinstance(color, dict) and paint.get("visible", True):
                    _bh = _lint_hex(color)
                    if _bh and _bh not in _border_ok:
                        warnings.append(
                            f"{label(nid, node)}: border {_bh} di luar "
                            f"hairline netral — pakai --ks-line / "
                            f"--ks-line-strong."
                        )
                        break

        unknown = sorted({h for h in hexes if h not in known and h not in _CONTENT_ALLOWLIST})
        if unknown:
            warnings.append(
                f"{label(nid, node)}: warna di luar tabel token: "
                f"{', '.join(unknown)}."
            )

        if node.get("type") == "text":
            import re as _re_cyan
            style = node.get("style", {}) or {}
            chars = str(node.get("characters", "") or "")
            if hexes and hexes[0] == cyan:
                # S-02: cyan = data teknis SAJA. Mono saja tak cukup —
                # judul sengaja diganti mono agar lolos dulu. Lolos bila pola
                # teknis ([..], #id, a/b) atau pendek tanpa huruf kecil.
                _stripped = chars.strip()
                _is_mono = style.get("font_family") == TOKENS["typography"]["font_mono"]
                _is_tech_pattern = bool(
                    _re_cyan.fullmatch(r"\[[^\]]*\]", _stripped)
                    or bool(_re_cyan.fullmatch(r"#\d+", _stripped))
                    or bool(_re_cyan.fullmatch(r"\d+\s*/\s*\d+", _stripped))
                )
                _is_short_code = (
                    len(_stripped) <= 24
                    and not _re_cyan.search(r"[a-z]", chars)
                )
                if not (_is_mono and (_is_tech_pattern or _is_short_code)):
                    warnings.append(
                        f"{label(nid, node)}: teks cyan bukan data teknis — "
                        "cyan hanya untuk info teknis pendek "
                        "(koordinat/ID/rasio/counter mono)."
                    )
            # S-08: teks meluber dari ruang dalam induknya.
            parent = nodes.get(str(node.get("parent", ""))) or {}
            _pw = parent.get("width") or 0
            _pad = (parent.get("layout") or {}).get("padding", [0, 0, 0, 0]) or [0, 0, 0, 0]
            try:
                _inner = float(_pw) - float(_pad[1]) - float(_pad[3])
            except (IndexError, TypeError, ValueError):
                _inner = float(_pw)
            if _pw and node.get("width", 0) > _inner + 1:
                warnings.append(
                    f"{label(nid, node)}: teks {node.get('width', 0):.0f}px "
                    f"meluber dari ruang dalam {_inner:.0f}px — "
                    f"kecilkan max_w teks / perlebar kartu."
                )

    # 4 (R5+R9): semantik coral tiga peran — FILL coral pada SHAPE
    # (frame/rect/ellipse) = permukaan aksi primer (maks 1 per layar);
    # FILL coral pada TEXT = teks aksen (badge tone di atas soft-tint,
    # header aktif — patterns.md §2/§5; wajar ≤3, warn bila lebih);
    # STROKE coral = cincin seleksi aktif — wajar beberapa, warn bila >4.
    # Cek lama hanya menghitung node bernama btn/* sehingga outline coral
    # ganda lolos diam-diam.
    # Pengecualian terdokumentasi: ProgressFill warnanya sudah di-gate
    # pct==100 di template (coral HANYA saat 100% — patterns.md §2).
    PROGRESS_EXEMPT = ("progressfill", "progressbar")
    def coral_roles(nids: List[Any]) -> tuple:
        surfaces, texts, rings = [], [], []
        for nid in nids:
            node = nodes.get(str(nid), {})
            if not isinstance(node, dict):
                continue
            if str(node.get("name", "")).lower().replace("_", "") in PROGRESS_EXEMPT:
                continue
            bucket = texts if node.get("type") == "text" else surfaces
            for paint in node.get("fills", []) or []:
                color = paint.get("color")
                if isinstance(color, dict) and paint.get("visible", True):
                    if _lint_hex(color) == coral:
                        bucket.append(label(nid, node))
            for paint in node.get("strokes", []) or []:
                color = paint.get("color")
                if isinstance(color, dict) and paint.get("visible", True):
                    if _lint_hex(color) == coral:
                        rings.append(label(nid, node))
        return surfaces, texts, rings

    def subtree(nid: Any) -> List[Any]:
        out, stack = [], [nid]
        while stack:
            cur = stack.pop()
            out.append(cur)
            node = nodes.get(str(cur), {})
            if isinstance(node, dict):
                stack.extend(node.get("children", []) or [])
        return out

    for pid in raw.get("pages", []):
        page = nodes.get(str(pid), {})
        if not isinstance(page, dict):
            continue
        for screen_id in page.get("children", []) or []:
            screen = nodes.get(str(screen_id), {})
            if not isinstance(screen, dict):
                continue
            surfaces, texts, rings = coral_roles(subtree(screen_id))
            if len(surfaces) > 1:
                warnings.append(
                    f"Layar '{screen.get('name', screen_id)}': "
                    f"{len(surfaces)} permukaan coral ({', '.join(surfaces)}) — "
                    "coral fill shape hanya untuk SATU aksi utama per layar."
                )
            if len(texts) > 3:
                warnings.append(
                    f"Layar '{screen.get('name', screen_id)}': "
                    f"{len(texts)} teks coral ({', '.join(texts)}) — "
                    "teks aksen coral maks 3 (badge tone + header aktif)."
                )
            if len(rings) > 4:
                warnings.append(
                    f"Layar '{screen.get('name', screen_id)}': "
                    f"{len(rings)} stroke coral ({', '.join(rings)}) — "
                    "cincin seleksi aktif wajar beberapa; >4 curigai aksen ganda."
                )

    # 5b (S-10): teks tak boleh meluber vertikal dari induk fixed.
    # Kelas bug nyata 2026-11-08: baris terakhir kartu baris-list
    # (104,5+14,9=119,4) melebihi kartu (115) — kepotong 4px.
    for nid, node in nodes.items():
        if not isinstance(node, dict) or node.get('type') != 'text':
            continue
        parent = nodes.get(str(node.get('parent', '')), {})
        if not isinstance(parent, dict) or parent.get('type') not in (
            'frame', 'rectangle', 'ellipse',
        ):
            continue
        if (parent.get('child_layout', {}) or {}).get('sizing_v') == 'hug':
            continue  # induk hug ikut membesar — bukan meluber
        pad = (parent.get('layout') or {}).get('padding', [0, 0, 0, 0]) or [0, 0, 0, 0]
        try:
            limit = float(parent.get('height', 0)) - float(pad[2])
            bottom = float(node.get('transform', [0]*6)[5]) + float(node.get('height', 0))
        except (IndexError, TypeError, ValueError):
            continue
        if bottom > limit + 1.0:
            warnings.append(
                f"{label(nid, node)}: teks meluber vertikal "
                f"({bottom:.0f}px > ruang dalam {limit:.0f}px) — "
                f"naikkan height induk / jadikan hug."
            )

    # 5 (S-09): ikon di atas permukaan coral HARUS sewarna teks tombol
    # (coral_fg, bukan putih). Satu kelas bug: 10 ikon vektor putih di
    # atas tombol coral ditegur 2026-11-08 (teksnya sudah coral_fg).
    coral_fg = TOKENS["colors"]["coral_fg"].lower()
    for nid, node in nodes.items():
        if not isinstance(node, dict) or node.get("type") not in (
            "frame", "rectangle", "ellipse",
        ):
            continue
        fills = node.get("fills", []) or []
        if not any(
            isinstance(p.get("color"), dict) and _lint_hex(p["color"]) == coral
            for p in fills if isinstance(p, dict)
        ):
            continue
        for sub in subtree(nid):
            vec = nodes.get(str(sub), {})
            if not isinstance(vec, dict) or vec.get("type") != "vector":
                continue
            for paint in vec.get("strokes", []) or []:
                color = paint.get("color")
                if (isinstance(color, dict) and paint.get("visible", True)
                        and _lint_hex(color) not in (coral_fg, coral)):
                    warnings.append(
                        f"{label(sub, vec)}: ikon di atas permukaan coral "
                        f"berwarna {_lint_hex(color)} — harus {coral_fg} "
                        "(coral_fg, samakan teks tombol)."
                    )

    return warnings


# ---------------------------------------------------------------------------
# DESIGN-TO-CODE CONVERTER (FIGCRAFT NODE -> SVELTE + TAILWIND)
# ---------------------------------------------------------------------------
def node_to_svelte(doc: FigcraftDocument, node_id: int, indent_level: int = 0) -> str:
    """Convert any FigCraft node hierarchy directly into Svelte + Tailwind markup."""
    nodes = doc.doc.get("nodes", {})
    node = nodes.get(str(node_id))
    if not node:
        return ""

    indent = "  " * indent_level
    ntype = node.get("type", "").lower()
    name = node.get("name", "")

    # Helper: map color to token
    def map_color(hex_str: str) -> str:
        h = hex_str.lower()
        if h in ["#0d0d10"]: return "bg"
        if h in ["#141418", "#121215", "#121214"]: return "surface"
        if h in ["#1a1a20", "#18181f"]: return "surface-2"
        if h in ["#22222a", "#212129"]: return "surface-card"
        if h in ["#2a2a33"]: return "hover"
        if h in ["#26262e", "#2e2e38", "#23232c"]: return "line"
        if h in ["#35353f", "#3a3a48"]: return "line-strong"
        if h in ["#ff6b5a", "#ff5f57", "#ff5f56"]: return "coral"
        if h in ["#9a9aa8"]: return "ring"
        if h in ["#34343f"]: return "selected"
        if h in ["#35e7f5"]: return "cyan"
        if h in ["#22c55e", "#27c93f"]: return "success"
        if h in ["#ef4444"]: return "danger"
        return f"[{hex_str}]"

    # Helper: extract hex fill
    fills = node.get("fills", [])
    bg_class = ""
    if fills and fills[0].get("visible", True):
        c = fills[0].get("color", {})
        r, g, b = int(c.get("r", 0)*255), int(c.get("g", 0)*255), int(c.get("b", 0)*255)
        hex_val = f"#{r:02x}{g:02x}{b:02x}"
        tok = map_color(hex_val)
        bg_class = f"bg-{tok}"

    # Helper: extract stroke
    strokes = node.get("strokes", [])
    border_class = ""
    if strokes and strokes[0].get("visible", True):
        border_class = "border border-border"

    # Helper: corner radius
    corners = node.get("corners", {}).get("radii", [0])[0] if "corners" in node else 0
    rounded_class = ""
    if corners >= 9000: rounded_class = "rounded-full"
    elif corners >= 16: rounded_class = "rounded-2xl"
    elif corners >= 12: rounded_class = "rounded-card"
    elif corners >= 6:  rounded_class = "rounded-md"
    elif corners >= 4:  rounded_class = "rounded"

    if ntype == "text":
        chars = node.get("characters", "")
        style = node.get("style", {})
        fsize = style.get("font_size", 13.0)
        ffam = style.get("font_family", "Inter")
        fweight = style.get("font_style", "Regular")

        # Color
        c = fills[0].get("color", {}) if fills else {}
        r, g, b = int(c.get("r", 1)*255), int(c.get("g", 1)*255), int(c.get("b", 1)*255)
        hex_val = f"#{r:02x}{g:02x}{b:02x}"
        text_color_class = "text-ink"
        if hex_val in ["#ff6b5a", "#ff5f57"]: text_color_class = "text-coral"
        elif hex_val == "#35e7f5": text_color_class = "text-cyan"
        elif hex_val in ["#a0a0b2", "#9e9eb0"]: text_color_class = "text-ink-2"
        elif hex_val in ["#68687a", "#636375"]: text_color_class = "text-ink-3"
        elif hex_val == "#22c55e": text_color_class = "text-success"

        classes = [f"text-[{int(fsize)}px]", text_color_class]
        if fweight in ["Bold", "SemiBold"]: classes.append("font-semibold")
        if "Space" in ffam: classes.append("font-brand")
        elif "Mono" in ffam: classes.append("font-mono tnum")

        return f'{indent}<span class="{" ".join(classes)}">{chars}</span>'

    elif ntype == "rectangle":
        w = node.get("width", 16)
        h = node.get("height", 16)
        classes = [f"w-[{int(w)}px]", f"h-[{int(h)}px]", bg_class, border_class, rounded_class]
        classes = [c for c in classes if c]
        return f'{indent}<div class="{" ".join(classes)}" />'

    elif ntype == "ellipse":
        w = node.get("width", 12)
        classes = [f"size-[{int(w)}px]", "rounded-full", bg_class]
        classes = [c for c in classes if c]
        return f'{indent}<div class="{" ".join(classes)}" />'

    elif ntype in ["frame", "page"]:
        # Layout classes
        layout = node.get("layout", {})
        mode = layout.get("mode", "none")
        gap = layout.get("gap", 0)
        pad = layout.get("padding", [0, 0, 0, 0])
        main_align = layout.get("main_align", "min")
        cross_align = layout.get("cross_align", "min")

        classes = []
        if mode == "horizontal":
            classes.append("flex flex-row")
            if gap > 0: classes.append(f"gap-[{int(gap)}px]")
            if main_align == "spaceBetween": classes.append("justify-between")
            elif main_align == "center": classes.append("justify-center")
            if cross_align == "center": classes.append("items-center")
        elif mode == "vertical":
            classes.append("flex flex-col")
            if gap > 0: classes.append(f"gap-[{int(gap)}px]")
            if main_align == "spaceBetween": classes.append("justify-between")
            elif main_align == "center": classes.append("justify-center")
            if cross_align == "center": classes.append("items-center")

        # Padding
        pt, pr, pb, pl = pad
        if pt == pb == pr == pl and pt > 0: classes.append(f"p-[{int(pt)}px]")
        else:
            if pt == pb and pt > 0: classes.append(f"py-[{int(pt)}px]")
            elif pt > 0: classes.append(f"pt-[{int(pt)}px]")
            if pr == pl and pr > 0: classes.append(f"px-[{int(pr)}px]")
            elif pr > 0: classes.append(f"pr-[{int(pr)}px]")

        if bg_class: classes.append(bg_class)
        if border_class: classes.append(border_class)
        if rounded_class: classes.append(rounded_class)
        if node.get("clip"): classes.append("overflow-hidden")

        # Sizing inside parent
        ch = node.get("child_layout", {})
        if ch.get("sizing_h") == "fill": classes.append("w-full")
        if ch.get("sizing_v") == "fill": classes.append("h-full")

        classes_str = f' class="{" ".join([c for c in classes if c])}"' if classes else ""
        children = node.get("children", [])

        if not children:
            return f'{indent}<div{classes_str} />'

        lines = [f'{indent}<div{classes_str}> <!-- {name} -->']
        for cid in children:
            child_str = node_to_svelte(doc, cid, indent_level + 1)
            if child_str:
                lines.append(child_str)
        lines.append(f'{indent}</div>')
        return "\n".join(lines)

    return ""


# ---------------------------------------------------------------------------
# CLI CONTROLLER
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="FigCraft CLI: Live automation & offline .figcraft generator for AI agents"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: file
    file_p = subparsers.add_parser("file", help="Offline .figcraft file operations")
    file_sub = file_p.add_subparsers(dest="file_action", required=True)

    # file inspect
    p_ins = file_sub.add_parser("inspect", help="Inspect a .figcraft document")
    p_ins.add_argument("path", help="Path to .figcraft file")

    # file code (Design-to-Code generator)
    p_code = file_sub.add_parser("code", help="Convert FigCraft node into Svelte + Tailwind markup")
    p_code.add_argument("path", help="Path to .figcraft file")
    p_code.add_argument("--id", type=int, default=None, help="Node ID to convert (default: first top frame)")

    # file create
    p_create = file_sub.add_parser("create", help="Create a new consistent .figcraft file")
    p_create.add_argument("path", help="Output .figcraft file path")
    p_create.add_argument("--template", choices=["workbench", "tokens", "blank", "all"], default="all", help="Preset design template")
    p_create.add_argument("--name", default="Kuron Studio", help="Project name")

    # file add-screen
    p_add = file_sub.add_parser("add-screen", help="Add a screen frame to existing .figcraft file")
    p_add.add_argument("path", help="Path to .figcraft file")
    p_add.add_argument("--screen", choices=["workbench", "tokens"], required=True, help="Screen type")

    # Subcommand: live
    live_p = subparsers.add_parser("live", help="Live FigCraft.app automation via socket")
    live_sub = live_p.add_subparsers(dest="live_action", required=True)

    # live status
    p_stat = live_sub.add_parser("status", help="Check FigCraft live status")
    p_stat.add_argument("--port", type=int, default=9880, help="Control server port")

    # live exec
    p_exec = live_sub.add_parser("exec", help="Execute an engine command live")
    p_exec.add_argument("cmd", help="Engine command ID (e.g. node.create, node.set, file.save)")
    p_exec.add_argument("params", nargs="?", default="{}", help="JSON params for command")
    p_exec.add_argument("--port", type=int, default=9880)

    # live export
    p_exp = live_sub.add_parser("export", help="Export active node to PNG/SVG")
    p_exp.add_argument("--id", type=int, required=True, help="Node ID to export")
    p_exp.add_argument("--out", required=True, help="Output image path (.png/.svg)")
    p_exp.add_argument("--format", default="png", choices=["png", "svg", "jpg", "pdf", "webp"])
    p_exp.add_argument("--scale", type=float, default=1.0)
    p_exp.add_argument("--port", type=int, default=9880)

    # Subcommand: tokens
    tok_p = subparsers.add_parser("tokens", help="Print design tokens")
    tok_p.add_argument("--json", action="store_true", help="Print in JSON format")

    args = parser.parse_args()

    if args.command == "tokens":
        if args.json:
            print(json.dumps(TOKENS, indent=2))
        else:
            print("=== KURON STUDIO DESIGN TOKENS ===")
            print("\n[COLORS]")
            for k, v in TOKENS["colors"].items():
                print(f"  --ks-{k.replace('_', '-')}: {v}")
            print("\n[TYPOGRAPHY]")
            for k, v in TOKENS["typography"]["sizes"].items():
                print(f"  text-{k}: {v}pt")
            print("\n[RADII]")
            for k, v in TOKENS["radii"].items():
                print(f"  rounded-{k}: {v}px")
        return

    elif args.command == "file":
        if args.file_action == "inspect":
            doc = FigcraftDocument.load(args.path)
            nodes = doc.doc.get("nodes", {})
            page = nodes.get("1", {})
            print(f"Document: {doc.name}")
            print(f"File Path: {args.path}")
            print(f"Total Nodes: {len(nodes)}")
            top_level = page.get("children", [])
            print(f"Top-Level Frames ({len(top_level)}):")
            for cid in top_level:
                cnode = nodes.get(str(cid), {})
                print(f"  - [{cid}] {cnode.get('name')} ({cnode.get('type')}) - {cnode.get('width')}x{cnode.get('height')}")

        elif args.file_action == "code":
            doc = FigcraftDocument.load(args.path)
            nodes = doc.doc.get("nodes", {})
            target_id = args.id
            if target_id is None:
                page = nodes.get("1", {})
                ch = page.get("children", [])
                if ch:
                    target_id = ch[0]
                else:
                    print("Error: No frames found in document.")
                    sys.exit(1)
            code = node_to_svelte(doc, target_id)
            print(f"<!-- SVELTE + TAILWIND CODE FOR NODE [{target_id}] -->")
            print(code)

        elif args.file_action == "create":
            doc = FigcraftDocument(args.name)
            if args.template in ["workbench", "all"]:
                build_workbench_screen(doc, x=40.0, y=40.0)
            if args.template in ["tokens", "all"]:
                build_tokens_screen(doc, x=1360.0, y=40.0)
            doc.save(args.path)
            print(f"Successfully generated FigCraft design file: {args.path}")

        elif args.file_action == "add-screen":
            doc = FigcraftDocument.load(args.path)
            # Find max X to place screen to the right
            nodes = doc.doc.get("nodes", {})
            page = nodes.get("1", {})
            max_x = 40.0
            for cid in page.get("children", []):
                cn = nodes.get(str(cid), {})
                tf = cn.get("transform", [1,0,0,1,0,0])
                w = cn.get("width", 0)
                right = tf[4] + w
                if right > max_x:
                    max_x = right
            new_x = max_x + 80.0

            if args.screen == "workbench":
                build_workbench_screen(doc, x=new_x, y=40.0)
            elif args.screen == "tokens":
                build_tokens_screen(doc, x=new_x, y=40.0)
            doc.save()
            print(f"Added {args.screen} screen at x={new_x} to {args.path}")

    elif args.command == "live":
        client = FigcraftClient(port=args.port)
        if not client.connect():
            print(f"Error: FigCraft is not running on 127.0.0.1:{args.port}")
            print("Start FigCraft with: /Applications/FigCraft.app/Contents/MacOS/FigCraft --control " + str(args.port))
            sys.exit(1)

        try:
            if args.live_action == "status":
                info = client.document_inspect()
                print("FigCraft Live Status: CONNECTED")
                print(json.dumps(info.get("result", {}), indent=2))

            elif args.live_action == "exec":
                params = json.loads(args.params)
                res = client.engine_execute(args.cmd, params)
                print(json.dumps(res, indent=2))

            elif args.live_action == "export":
                res = client.export_frame(args.id, args.out, format=args.format, scale=args.scale)
                print(f"Exported node {args.id} to {args.out}")
                print(json.dumps(res, indent=2))
        finally:
            client.close()

if __name__ == "__main__":
    main()
