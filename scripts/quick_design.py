#!/usr/bin/env python3
"""
FigCraft QuickDesign Engine — rapid UI generator (kuron-design-figcraft 3.0.0)
Enables AI agents and designers to generate token-compliant, high-fidelity
UI designs in seconds from natural prompts or declarative specs, complete with
automatic PNG visual preview rendering.

Setiap dokumen yang dihasilkan dicek validator quiet-workbench
(figcraft_tool.lint_design); peringatan dicetak ke stderr tanpa
menggagalkan build. Port preview default (9880) disatukan dengan
agent_terminal.DEFAULT_PORT / FigcraftClient agar satu FigCraft
yang berjalan bisa dipakai semua perkakas.
"""

import sys
import os
import json
import subprocess
import time
import argparse
from typing import Dict, List, Optional, Any, Union

# Import base toolkit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figcraft_tool import FigcraftDocument, FigcraftClient, TOKENS, hex_to_rgba, lint_design

# ---------------------------------------------------------------------------
# RAPID BLOCK COMPONENT FACTORY
# ---------------------------------------------------------------------------
class DesignBlocks:
    """Reusable high-level design blocks conforming strictly to Kuron Studio DESIGN.md."""

    @staticmethod
    def add_app_header(
        doc: FigcraftDocument,
        parent_id: int,
        title: str = "Kuron Studio",
        chapter: str = "ONIMASA Ch. 12",
        page_info: str = "41 pages",
        actions: Optional[List[Dict[str, str]]] = None
    ) -> int:
        """Top Application Toolbar with brand, breadcrumbs, search, and action buttons."""
        header_id = doc.create_frame(
            name="AppHeader",
            parent_id=parent_id,
            width=1280.0,
            height=TOKENS["sizes"]["header"],
            fill=TOKENS["colors"]["surface_2"],
            stroke=TOKENS["colors"]["border"],
            layout_mode="horizontal",
            gap=16.0,
            padding=(0.0, 20.0, 0.0, 20.0),
            main_align="spaceBetween",
            cross_align="center",
            sizing_h="fill",
            sizing_v="fixed"
        )

        # Left: Brand + Breadcrumbs
        left_grp = doc.create_frame("BrandGroup", header_id, width=320.0, height=32.0, layout_mode="horizontal", gap=12.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
        # Brand logo badge — ink_primary (Design C); penanda aktif = ring/box
        # luar, BUKAN warna logo. Coral di sini = aksen ganda.
        doc.create_rect("AppLogo", left_grp, 24.0, 24.0, fill=TOKENS["colors"]["ink_primary"], corner_radius=6.0)
        doc.create_text("AppName", title, left_grp, font_size=13.0, font_weight="Bold", font_family=TOKENS["typography"]["font_brand"], color=TOKENS["colors"]["ink_primary"])
        doc.create_text("Sep", "—", left_grp, font_size=12.0, color=TOKENS["colors"]["ink_muted"])
        doc.create_text("ChapName", chapter, left_grp, font_size=12.0, font_weight="Medium", color=TOKENS["colors"]["ink_secondary"])
        doc.build_badge("BadgePages", page_info.upper(), left_grp, tone="cyan")

        # Right: Actions
        right_grp = doc.create_frame("HeaderActions", header_id, width=300.0, height=32.0, layout_mode="horizontal", gap=10.0, cross_align="center", sizing_h="hug", sizing_v="fixed")
        if actions:
            for act in actions:
                doc.build_button(
                    name=f"Btn_{act.get('label', 'Action')}",
                    label=act.get("label", "Button"),
                    parent_id=right_grp,
                    variant=act.get("variant", "default"),
                    size=act.get("size", "md"),
                    icon_name=act.get("icon")
                )
        else:
            doc.build_button("BtnDetect", "Deteksi Balon", right_grp, variant="default", size="md")
            doc.build_button("BtnTranslate", "Terjemahkan Semua", right_grp, variant="primary", size="md")

        return header_id

    @staticmethod
    def add_stats_grid(
        doc: FigcraftDocument,
        parent_id: int,
        stats: List[Dict[str, Any]]
    ) -> int:
        """Horizontal row of dense metric cards."""
        row_id = doc.create_frame(
            name="StatsRow",
            parent_id=parent_id,
            width=1280.0,
            height=84.0,
            layout_mode="horizontal",
            gap=16.0,
            sizing_h="fill",
            sizing_v="hug"
        )
        for stat in stats:
            card = doc.create_frame(
                name=f"StatCard_{stat.get('label', '')}",
                parent_id=row_id,
                width=240.0,
                height=84.0,
                fill=TOKENS["colors"]["surface_card"],
                stroke=TOKENS["colors"]["border"],
                corner_radius=TOKENS["radii"]["card"],
                layout_mode="vertical",
                gap=6.0,
                padding=(12.0, 16.0, 12.0, 16.0),
                sizing_h="fill",
                sizing_v="fixed"
            )
            top_line = doc.create_frame("TopLine", card, width=200.0, height=16.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
            doc.create_text("Label", stat.get("label", "").upper(), top_line, font_size=10.0, font_weight="Bold", color=TOKENS["colors"]["ink_muted"])
            if "badge" in stat:
                doc.build_badge("Badge", stat["badge"], top_line, tone=stat.get("tone", "cyan"))

            bot_line = doc.create_frame("BottomLine", card, width=200.0, height=28.0, layout_mode="horizontal", gap=8.0, cross_align="baseline", sizing_h="fill", sizing_v="hug")
            doc.create_text("Value", str(stat.get("value", "")), bot_line, font_size=20.0, font_weight="Bold", font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["ink_primary"])
            if "desc" in stat:
                doc.create_text("Desc", stat["desc"], bot_line, font_size=11.0, color=TOKENS["colors"]["ink_secondary"])

        return row_id

    @staticmethod
    def add_project_cards_grid(
        doc: FigcraftDocument,
        parent_id: int,
        projects: List[Dict[str, Any]]
    ) -> int:
        """Grid of Manga Project cards (300px each) for Dashboard."""
        grid_id = doc.create_frame(
            name="ProjectsGrid",
            parent_id=parent_id,
            width=1280.0,
            height=400.0,
            layout_mode="horizontal",
            gap=20.0,
            sizing_h="fill",
            sizing_v="hug"
        )
        for proj in projects:
            card = doc.create_frame(
                name=f"Project_{proj.get('title', 'Card')}",
                parent_id=grid_id,
                width=300.0,
                height=340.0,
                fill=TOKENS["colors"]["surface_card"],
                stroke=TOKENS["colors"]["coral"] if proj.get("active") else TOKENS["colors"]["border"],
                stroke_width=1.5 if proj.get("active") else 1.0,
                corner_radius=TOKENS["radii"]["card"],
                layout_mode="vertical",
                gap=12.0,
                padding=(14.0, 14.0, 14.0, 14.0),
                sizing_h="fixed",
                sizing_v="fixed"
            )
            # Manga Cover Thumbnail with mode badge overlay
            cover = doc.create_frame("CoverBox", card, 272.0, 180.0, fill=TOKENS["colors"]["surface_active"], corner_radius=8.0, layout_mode="vertical", main_align="spaceBetween", padding=(8.0, 8.0, 8.0, 8.0), sizing_h="fill", sizing_v="fixed")
            tag_row = doc.create_frame("TagRow", cover, 256.0, 22.0, layout_mode="horizontal", main_align="spaceBetween", sizing_h="fill", sizing_v="hug")
            doc.build_badge("ModeBadge", proj.get("mode", "JA → ID"), tag_row, tone="coral" if proj.get("active") else "cyan")
            doc.build_badge("StatusBadge", proj.get("status", "Review"), tag_row, tone="ok" if proj.get("done") else "warn")
            
            # Comic art placeholder icon
            doc.create_text("CoverText", "MANGA COVER", cover, font_size=12.0, font_weight="Bold", color=TOKENS["colors"]["ink_muted"])

            # Project Info
            info = doc.create_frame("InfoBlock", card, 272.0, 80.0, layout_mode="vertical", gap=4.0, sizing_h="fill", sizing_v="hug")
            doc.create_text("Title", proj.get("title", "Project Title"), info, font_size=14.0, font_weight="Bold", font_family=TOKENS["typography"]["font_brand"], color=TOKENS["colors"]["ink_primary"])
            doc.create_text("Meta", f"{proj.get('pages', 24)} halaman  •  {proj.get('bubbles', 180)} balon kata", info, font_size=11.0, font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["cyan"])

            # Progress Bar (3px height)
            pct = proj.get("progress", 50)
            bar_bg = doc.create_frame("ProgressBar", card, 272.0, 6.0, fill=TOKENS["colors"]["surface_2"], corner_radius=3.0, sizing_h="fill", sizing_v="fixed")
            doc.create_rect("ProgressFill", bar_bg, 272.0 * (pct / 100.0), 6.0, fill=TOKENS["colors"]["coral"] if pct == 100 else TOKENS["colors"]["cyan"], corner_radius=3.0)

            # Footer
            ftr = doc.create_frame("CardFooter", card, 272.0, 24.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
            doc.create_text("ProgressText", f"{pct}% Selesai", ftr, font_size=10.0, font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["ink_secondary"])
            doc.create_text("Updated", proj.get("updated", "Baru saja"), ftr, font_size=10.0, color=TOKENS["colors"]["ink_muted"])

        return grid_id

    @staticmethod
    def add_ledger_table(
        doc: FigcraftDocument,
        parent_id: int,
        rows_data: List[Dict[str, Any]]
    ) -> int:
        """Dense Ledger / Data Table for translation review."""
        table_container = doc.create_frame(
            name="LedgerTable",
            parent_id=parent_id,
            width=1280.0,
            height=500.0,
            fill=TOKENS["colors"]["surface_card"],
            stroke=TOKENS["colors"]["border"],
            corner_radius=TOKENS["radii"]["card"],
            layout_mode="vertical",
            gap=0.0,
            clip=True,
            sizing_h="fill",
            sizing_v="hug"
        )
        # Header Row
        head_row = doc.create_frame("TableHeader", table_container, width=1280.0, height=36.0, fill=TOKENS["colors"]["surface_2"], stroke=TOKENS["colors"]["border"], layout_mode="horizontal", padding=(0.0, 16.0, 0.0, 16.0), cross_align="center", sizing_h="fill", sizing_v="fixed")
        doc.create_text("H_Idx", "#", head_row, font_size=11.0, font_weight="Bold", font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["ink_muted"], width=40.0)
        doc.create_text("H_Page", "HLM", head_row, font_size=11.0, font_weight="Bold", color=TOKENS["colors"]["ink_muted"], width=60.0)
        doc.create_text("H_Orig", "TEKS ASLI (JA)", head_row, font_size=11.0, font_weight="Bold", color=TOKENS["colors"]["ink_muted"], width=300.0)
        doc.create_text("H_Trans", "TERJEMAHAN (ID)", head_row, font_size=11.0, font_weight="Bold", color=TOKENS["colors"]["ink_muted"], width=380.0)
        doc.create_text("H_Fit", "FIT", head_row, font_size=11.0, font_weight="Bold", font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["ink_muted"], width=80.0)
        doc.create_text("H_Status", "STATUS", head_row, font_size=11.0, font_weight="Bold", color=TOKENS["colors"]["ink_muted"], width=120.0)

        # Rows
        for i, row in enumerate(rows_data):
            is_even = (i % 2 == 1)
            row_frame = doc.create_frame(
                name=f"Row_{i+1}",
                parent_id=table_container,
                width=1280.0,
                height=44.0,
                fill=TOKENS["colors"]["surface_active"] if is_even else TOKENS["colors"]["surface_card"],
                stroke=TOKENS["colors"]["border_subtle"],
                layout_mode="horizontal",
                padding=(0.0, 16.0, 0.0, 16.0),
                cross_align="center",
                sizing_h="fill",
                sizing_v="fixed"
            )
            doc.create_text("Idx", f"{i+1:02d}", row_frame, font_size=11.0, font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["ink_muted"], width=40.0)
            doc.create_text("Page", f"P.{row.get('page', 1):02d}", row_frame, font_size=11.0, font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["cyan"], width=60.0)
            doc.create_text("Orig", row.get("orig", "—"), row_frame, font_size=12.0, color=TOKENS["colors"]["ink_secondary"], width=300.0)
            doc.create_text("Trans", row.get("trans", "—"), row_frame, font_size=12.0, font_weight="SemiBold", color=TOKENS["colors"]["ink_primary"], width=380.0)
            doc.create_text("Fit", f"{row.get('fit', 95)}%", row_frame, font_size=11.0, font_family=TOKENS["typography"]["font_mono"], color=TOKENS["colors"]["success"], width=80.0)
            status_tone = "ok" if row.get("status") == "Dicek" else ("warn" if row.get("status") == "Perlu Cek" else "cyan")
            doc.build_badge("Status", row.get("status", "Selesai"), row_frame, tone=status_tone)

        return table_container

    @staticmethod
    def add_mobile_drawer_sheet(
        doc: FigcraftDocument,
        parent_id: int,
        title: str = "Pengaturan & Tindakan Cepat",
        items: Optional[List[Dict[str, str]]] = None
    ) -> int:
        """Bottom sheet / mobile drawer component (Issue #14 spec)."""
        sheet = doc.create_frame(
            name="MobileDrawerSheet",
            parent_id=parent_id,
            width=390.0,
            height=460.0,
            fill=TOKENS["colors"]["surface_2"],
            stroke=TOKENS["colors"]["border"],
            corner_radius=20.0,
            layout_mode="vertical",
            gap=16.0,
            padding=(12.0, 20.0, 24.0, 20.0),
            sizing_h="fixed",
            sizing_v="hug"
        )
        # Grab Handle
        doc.create_rect("GrabHandle", sheet, 40.0, 4.0, fill=TOKENS["colors"]["cyan"], corner_radius=2.0)
        
        # Header Title Row
        head = doc.create_frame("DrawerHeader", sheet, 350.0, 28.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
        doc.create_text("DrawerTitle", title, head, font_size=15.0, font_weight="Bold", font_family=TOKENS["typography"]["font_brand"], color=TOKENS["colors"]["ink_primary"])
        doc.build_badge("BadgeMbl", "MOBILE", head, tone="coral")

        # Action items list
        menu_items = items or [
            {"label": "Deteksi Ulang Semua Halaman", "desc": "Jalankan model YOLO11n-seg", "cta": "Deteksi", "tone": "default"},
            {"label": "Pilih Penyedia AI (Provider)", "desc": "DeepSeek / Gemini 1.5 Flash", "cta": "Ubah", "tone": "default"},
            {"label": "Bersihkan Balon Kosong (Inpaint)", "desc": "Hapus sisa teks Jepang otomatis", "cta": "Jalankan", "tone": "default"},
            {"label": "Ekspor Chapter Selesai (.cbz / .zip)", "desc": "41 halaman terjemahan siap baca", "cta": "Ekspor", "tone": "primary"},
        ]
        for it in menu_items:
            item_frame = doc.create_frame(
                name=f"Item_{it['label'][:10]}",
                parent_id=sheet,
                width=350.0,
                height=56.0,
                fill=TOKENS["colors"]["surface_card"],
                stroke=TOKENS["colors"]["border_subtle"],
                corner_radius=TOKENS["radii"]["control"],
                layout_mode="horizontal",
                padding=(8.0, 12.0, 8.0, 12.0),
                main_align="spaceBetween",
                cross_align="center",
                sizing_h="fill",
                sizing_v="fixed"
            )
            text_col = doc.create_frame("TextCol", item_frame, 240.0, 40.0, layout_mode="vertical", gap=2.0, sizing_h="fill", sizing_v="hug")
            doc.create_text("Label", it["label"], text_col, font_size=12.0, font_weight="SemiBold", color=TOKENS["colors"]["ink_primary"])
            doc.create_text("Desc", it["desc"], text_col, font_size=10.0, color=TOKENS["colors"]["ink_muted"])
            doc.build_button("CTA", it["cta"], item_frame, variant=it.get("tone", "default"), size="sm")

        return sheet


# ---------------------------------------------------------------------------
# HIGH-LEVEL PRESET GENERATORS
# ---------------------------------------------------------------------------
def generate_preset(preset_name: str, doc_name: str = "Kuron QuickDesign") -> FigcraftDocument:
    doc = FigcraftDocument(doc_name)

    if preset_name == "dashboard":
        # Screen: 1280x960 Dashboard
        screen = doc.create_frame("Dashboard Screen", 1, 1280.0, 960.0, fill=TOKENS["colors"]["surface"], corner_radius=TOKENS["radii"]["window"], layout_mode="vertical", gap=20.0, padding=(0.0, 0.0, 32.0, 0.0), clip=True)
        doc.build_window_bar(screen, "Kuron Studio — Proyek Manga & Webtoon")
        DesignBlocks.add_app_header(doc, screen, title="Kuron Studio", chapter="Dashboard Proyek", page_info="8 Proyek Aktif")

        content = doc.create_frame("ContentArea", screen, 1280.0, 800.0, layout_mode="vertical", gap=20.0, padding=(0.0, 32.0, 0.0, 32.0), sizing_h="fill", sizing_v="fill")
        # Stats summary row
        stats = [
            {"label": "Total Bab Dikerjakan", "value": "128", "desc": "+12 minggu ini", "badge": "AKTIF", "tone": "cyan"},
            {"label": "Balon Kata Terdeteksi", "value": "3,420", "desc": "Akurasi 98.4%", "badge": "YOLO11", "tone": "cyan"},
            {"label": "Waktu Rata-rata / Bab", "value": "4.2m", "desc": "3x lebih cepat", "badge": "CEPAT", "tone": "ok"},
            {"label": "Siap Diekspor", "value": "6", "desc": "Tinggal verifikasi akhir", "badge": "CORAL CTA", "tone": "coral"},
        ]
        DesignBlocks.add_stats_grid(doc, content, stats)

        # Projects cards
        doc.create_text("SecTitle", "PROYEK BERJALAN", content, font_size=13.0, font_weight="Bold", color=TOKENS["colors"]["coral"])
        projects = [
            {"title": "ONIMASA: Demon Hunter", "pages": 41, "bubbles": 218, "mode": "JA → ID", "status": "Review", "progress": 82, "active": True, "updated": "2 menit lalu"},
            {"title": "Kagurabachi: Katana Soul", "pages": 28, "bubbles": 142, "mode": "JA → ID", "status": "Translating", "progress": 45, "active": False, "updated": "1 jam lalu"},
            {"title": "Chainsaw Atelier", "pages": 34, "bubbles": 190, "mode": "JA → ID", "status": "Selesai", "progress": 100, "done": True, "active": False, "updated": "Kemarin"},
            {"title": "Frieren: Beyond Journey", "pages": 22, "bubbles": 98, "mode": "JA → EN", "status": "Deteksi", "progress": 15, "active": False, "updated": "3 hari lalu"},
        ]
        DesignBlocks.add_project_cards_grid(doc, content, projects)

    elif preset_name == "ledger":
        # Screen: 1280x960 Translation Review Ledger
        screen = doc.create_frame("Ledger Screen", 1, 1280.0, 960.0, fill=TOKENS["colors"]["surface"], corner_radius=TOKENS["radii"]["window"], layout_mode="vertical", gap=20.0, padding=(0.0, 0.0, 32.0, 0.0), clip=True)
        doc.build_window_bar(screen, "Kuron Studio — Tabel Terjemahan Balon Kata")
        DesignBlocks.add_app_header(doc, screen, title="Kuron Studio", chapter="Ledger Review: ONIMASA Ch. 12", page_info="14 Balon Hlm. 04")
        
        content = doc.create_frame("ContentArea", screen, 1280.0, 800.0, layout_mode="vertical", gap=16.0, padding=(0.0, 32.0, 0.0, 32.0), sizing_h="fill", sizing_v="fill")
        # Filters toolbar
        ft_bar = doc.create_frame("FilterBar", content, 1216.0, 36.0, layout_mode="horizontal", main_align="spaceBetween", cross_align="center", sizing_h="fill", sizing_v="hug")
        search_box = doc.create_frame("SearchBox", ft_bar, 300.0, 36.0, fill=TOKENS["colors"]["surface_card"], stroke=TOKENS["colors"]["border"], corner_radius=6.0, layout_mode="horizontal", padding=(0.0, 12.0, 0.0, 12.0), cross_align="center", sizing_h="hug", sizing_v="fixed")
        doc.create_text("SearchTxt", "Cari teks asli atau hasil terjemahan...", search_box, font_size=11.0, color=TOKENS["colors"]["ink_muted"])
        
        btn_grp = doc.create_frame("BtnGrp", ft_bar, 200.0, 36.0, layout_mode="horizontal", gap=8.0, sizing_h="hug", sizing_v="fixed")
        doc.build_button("BtnFilter", "Filter: Belum Dicek (4)", btn_grp, variant="default", size="sm")
        doc.build_button("BtnApprove", "Setujui Semua Halaman", btn_grp, variant="default", size="sm")

        # Table rows
        rows = [
            {"page": 4, "orig": "なに？！本当にあいつが…", "trans": "Apa?! Apa benar dia yang…", "fit": 94, "status": "Dicek"},
            {"page": 4, "orig": "嘘じゃない。この目で見た。", "trans": "Bukan bohong. Aku melihatnya sendiri.", "fit": 98, "status": "Dicek"},
            {"page": 4, "orig": "なら…急がねばなるまい！", "trans": "Kalau begitu… kita harus bergegas!", "fit": 88, "status": "Perlu Cek"},
            {"page": 4, "orig": "結界が破られたら終わりだ。", "trans": "Jika penghalang hancur, habislah kita.", "fit": 96, "status": "Dicek"},
            {"page": 4, "orig": "おい、お前も来い！", "trans": "Hei, kamu juga ikut!", "fit": 92, "status": "Dicek"},
            {"page": 5, "orig": "待ってくれ！まだ準備が…", "trans": "Tunggu sebentar! Aku belum siap…", "fit": 90, "status": "Draft"},
        ]
        DesignBlocks.add_ledger_table(doc, content, rows)

    elif preset_name == "drawer":
        # Screen: Mobile 390x844 with active Bottom Drawer Sheet (Issue #14)
        screen = doc.create_frame("Mobile Screen with Drawer", 1, 390.0, 844.0, fill="#00000088", corner_radius=32.0, layout_mode="vertical", main_align="max", clip=True)
        # Background dimmed app
        DesignBlocks.add_mobile_drawer_sheet(doc, screen)

    else:
        # Default: Desktop Workbench
        from figcraft_tool import build_workbench_screen
        build_workbench_screen(doc, x=40.0, y=40.0)

    return doc


# ---------------------------------------------------------------------------
# MAIN CLI & AUTO-RENDER PREVIEW
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="FigCraft QuickDesign: Viral rapid UI generator with instant PNG previews"
    )
    parser.add_argument("prompt", nargs="?", default="", help="Natural language prompt describing what to design")
    parser.add_argument("-p", "--preset", choices=["workbench", "dashboard", "ledger", "drawer"], default="workbench", help="Template preset")
    parser.add_argument("-o", "--output", required=True, help="Output .figcraft file path")
    parser.add_argument("--preview", action="store_true", help="Automatically render PNG preview using FigCraft headless engine")
    parser.add_argument("--port", type=int, default=9880, help="Port for automated render worker (default 9880, sama dengan agent_terminal/FigcraftClient agar satu FigCraft bisa dipakai bersama)")

    args = parser.parse_args()

    # Determine preset from prompt if provided
    prompt_lower = args.prompt.lower()
    selected_preset = args.preset
    if "dash" in prompt_lower or "proyek" in prompt_lower or "card" in prompt_lower:
        selected_preset = "dashboard"
    elif "ledger" in prompt_lower or "tabel" in prompt_lower or "review" in prompt_lower:
        selected_preset = "ledger"
    elif "drawer" in prompt_lower or "sheet" in prompt_lower or "mobile" in prompt_lower:
        selected_preset = "drawer"
    elif "workbench" in prompt_lower or "editor" in prompt_lower:
        selected_preset = "workbench"

    print(f"\n🚀 [FigCraft QuickDesign] Generating UI: '{selected_preset.upper()}'")
    doc_title = args.prompt if args.prompt else f"Kuron Studio — {selected_preset.capitalize()}"
    doc = generate_preset(selected_preset, doc_title)
    for warn in lint_design(doc):
        print(f"[lint] {warn}", file=sys.stderr)
    doc.save(args.output)
    print(f"✨ File .figcraft created: {args.output}")

    # Render Preview if requested
    if args.preview:
        out_base, _ = os.path.splitext(args.output)
        preview_png = f"{out_base}_preview.png"
        print(f"📸 Rendering visual preview: {preview_png}...")
        
        # Launch headless FigCraft to render the screen
        abs_fig = os.path.abspath(args.output)
        abs_png = os.path.abspath(preview_png)
        work_dir = os.path.dirname(abs_fig)

        app_bin = os.environ.get(
            "FIGCRAFT_APP", "/Applications/FigCraft.app/Contents/MacOS/FigCraft")
        if not os.path.exists(app_bin):
            print(f"Preview skipped: FigCraft binary not found at {app_bin} "
                  "(set FIGCRAFT_APP to override).")
            return
        cmd = [
            app_bin,
            "--control", str(args.port),
            "--automation-read-root", work_dir,
            "--automation-write-root", work_dir,
            abs_fig
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.2)

        client = FigcraftClient(port=args.port)
        rendered = False
        try:
            if client.connect(timeout=2.0):
                # Inspect to find the top screen ID
                doc_info = client.document_inspect()
                pages = doc_info.get("result", {}).get("pages", [])
                if pages and pages[0].get("children"):
                    screen_id = pages[0]["children"][0].get("id")
                    if screen_id:
                        res = client.export_frame(screen_id, abs_png, format="png", scale=1.0)
                        if res.get("ok"):
                            print(f"✅ Preview exported successfully: {preview_png}")
                            rendered = True
        except Exception as e:
            print(f"Warning: Render error: {e}")
        finally:
            client.close()
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except Exception:
                proc.kill()

        if not rendered:
            print("💡 Tip: You can open the file directly in FigCraft to view.")

    print("\n🎉 Done! Ready to inspect or iterate.\n")

if __name__ == "__main__":
    main()
