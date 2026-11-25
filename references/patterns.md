# FigCraft Design Patterns & System Specification

Portable design contract for `kuron-design-figcraft`. Every AI agent using this
skill **must** follow this specification when creating or modifying designs.
All values come from the bundled token file `design-tokens.css` (namespace
`--ks-*`) plus `DESIGN.md` in this same `references/` directory. Those two files
are the single source of truth; a consuming project may supply its own token
file with the same names, but never invent a value outside the tokens.

---

## 1. Filosofi Desain

- **Dense Desktop Workbench:** a compact productivity tool — tight rows, clear
  groups, minimal empty decoration. Not a relaxed landing page.
- **Single Source of Truth:** colours and sizes resolve to `--ks-*` tokens in
  `references/design-tokens.css`. No value outside those tokens.
- **Peran Warna Tegas:**
  - **Coral (`#ff6b5a`):** primary action only (main CTA, active selection outline).
  - **Cyan (`#35e7f5`):** technical information (coordinates `[x, y, w, h]`, IDs, counters).
  - **Surface/Panel:** layered neutral darks (`#0d0d10` → `#141418` → `#1a1a20` → `#22222a`).
  - **Inks:** hierarchical text (`#ececf1` primary, `#a5a6b0` secondary, `#71727d` muted).
- **Auto-Layout Sentris:** every container, button, card, and panel **must** use
  Auto-Layout (`mode: horizontal | vertical`) with measured padding and gap.

---

## 2. Palet Token Warna (dark default; pasangan light di `design-tokens.css`)

| Token | Dark Hex | Kegunaan |
|---|---|---|
| `--ks-bg` | `#0d0d10` | Kanvas terluar / background window terdalam |
| `--ks-surface` | `#141418` | Latar utama halaman kerja |
| `--ks-surface-2` | `#1a1a20` | Header, folder bar, toolbar, rail navigasi |
| `--ks-raised` | `#22222a` | Kartu daftar, dialog modal Level 3 |
| `--ks-hover` | `#2a2a33` | State hover tombol / baris tabel |
| `--ks-line` | `#26262e` | Garis pembatas panel 1px hairline monokrom |
| `--ks-line-strong` | `#35353f` | Kontur jendela luar, border dialog modal |
| `--ks-text` | `#ececf1` | Judul, label aktif, teks utama |
| `--ks-text-2` | `#a5a6b0` | Teks tubuh, metadata, label form |
| `--ks-text-3` | `#71727d` | Placeholder, shortcut, teks non-aktif |
| `--ks-accent` | `#ff6b5a` | **Aksi utama saja** (CTA), outline seleksi aktif |
| `--ks-accent-hover` | `#ff8272` | Hover tombol aksi utama |
| `--ks-accent-fg` | `#1a0a08` | Teks di atas latar coral |
| `--ks-accent-soft` | `#2e1614` | Soft tint coral untuk latar tombol/badge |
| `--ks-cyan` | `#35e7f5` | Info teknis mono — **Dilarang neon `#00e5ff`** |
| `--ks-cyan-soft` | `#0e2a2e` | Soft tint cyan lembut tanpa border |
| `--ks-success` | `#5fd99a` | Status selesai / online |
| `--ks-success-soft` | `#10281d` | Latar badge selesai |
| `--ks-warn` | `#ffc15e` | Status proses berjalan / review |
| `--ks-warn-soft` | `#2b2110` | Latar badge berjalan |
| `--ks-danger` | `#ff5c5c` | Aksi destruktif / error |
| `--ks-danger-soft` | `#2e1416` | Latar badge error |
| `--ks-info` | `#6ba6ff` | Status info netral |
| `--ks-info-soft` | `#111e33` | Latar badge info |
| `--ks-ring` | `#9a9aa8` | Cincin fokus + halo seleksi (bukan dekorasi) |
| `--ks-selected` | `#34343f` | Baris terpilih persisten, beda dari `--ks-hover` |

> **Aturan Border Bersih (Quiet Workbench):**
> 1. Dilarang border neon (`#00e5ff` atau cyan menyala). Cyan yang benar `#35e7f5`.
> 2. Badge & chip **tanpa border**, duduk lembut di atas `--ks-*-soft`.
> 3. Pembatas struktural memakai hairline monokrom (`--ks-line` / `--ks-line-strong`).
> 4. Tanpa gradient, shadow dekoratif, atau emoji sebagai ikon; angka memakai
>    `tabular-nums`; fokus keyboard selalu terlihat; hormati `prefers-reduced-motion`.

Lihat `light-glass-system.md` untuk nilai light dan token kaca.

---

## 3. Tipografi & Font

| Peran | Font Family | Style | Ukuran | Kegunaan |
|---|---|---|---|---|
| Brand / Title | `Space Grotesk` (atau `Inter`) | Bold | 20 pt | Nama aplikasi, judul layar |
| Heading | `Inter` | Bold | 15 pt | Judul seksi, judul kartu |
| Body (default) | `Inter` | Medium | 13 pt | Teks UI, instruksi |
| Button Label | `Inter` | SemiBold | 12 pt | Label tombol aksi |
| Caption / Meta | `Inter` | Regular | 11 pt | Deskripsi sekunder |
| Mono / Counter | `JetBrains Mono` | SemiBold | 10–11 pt | Angka tabular, koordinat, pill |

Font di-bundel offline (fontsource), bukan CDN.

---

## 4. Skala Ukuran & Radius (Strict Geometry)

| Elemen | Tinggi | Radius | Padding | Layout |
|---|---|---|---|---|
| Button sm | 28 px | 6 px | `pad_x:10`, `pad_y:4` | horizontal, gap 6 |
| Button md (default) | 32 px | 6 px | `pad_x:14`, `pad_y:6` | horizontal, gap 6 |
| Button lg | 40 px | 6 px | `pad_x:18`, `pad_y:10` | horizontal, gap 8 |
| Input / Field | 36 px | 6 px | `pad_x:12`, `pad_y:6` | horizontal, gap 8 |
| Badge / Pill | 20 px | 9999 px | `pad_x:8`, `pad_y:2` | horizontal, mono 10 pt |
| Card | Hug | 12 px | `pad_x:14`, `pad_y:12` | vertical, border 1px |
| Window Frame | 960 px | 16 px | — | root screen frame |
| Window Bar | 32 px | — | `pad_x:16` | traffic lights + judul + status |
| Pipeline Bar | 40 px | — | `pad_x:20` | 5 tahap dengan arrow `→` |
| Touch target | ≥44 px | — | — | mobile / tablet |

---

## 5. Pola Layout Layar Standar

### Desktop Workbench (1280 × 960)
1. **WindowBar (32px):** traffic lights 12px, judul dokumen, status dot.
2. **PipelineBar (40px):** 5 tahap (Import → Deteksi → Terjemah → Review → Ekspor).
3. **Body (888px):** 3 kolom — **Left Rail 196px** (daftar item + counter),
   **Center Canvas 1fr** (latar `--ks-bg`), **Right Inspector 268px** (kartu detil:
   asli / hasil / fit bar + footer aksi).

### Dashboard Proyek (1280 × 960)
Grid kartu lebar 300px: cover, judul Space Grotesk, counter mono, progress bar
3px, badge mode.

### Ritme Makro Kanvas (S-06)
Margin horizontal 40–80px; konten simetris. Ruang mati vertikal bawah >150px =
tolak — distribusikan ulang atau pusatkan (`main_align: center/spaceBetween`).
Utilisasi kanvas ≥60%.

### Tablet (834 × 1194)
Rail ikon 64px + grid 3 kolom + bottom sheet 40% (grab handle aksen cyan).

### Mobile (390 × 844)
Grid 2 kolom + tab bar bawah 56px (touch target minimal 44px).

---

## 6. Aturan Penamaan & Struktur Node

1. Nama node semantik: `WindowBar`, `TrafficLights`, `PipelineBar`,
   `LeftRail`, `CenterCanvas`, `RightInspector`, `Btn_<Action>`,
   `Card_<Name>`, `Badge_<Type>`.
2. Sizing Auto-Layout: container utama `sizing_h: "fill"`; sidebar/inspector
   `sizing_h: "fixed"`, `sizing_v: "fill"`; tombol/badge `sizing_h: "hug"`,
   `sizing_v: "fixed"`; teks `hug`/`hug`.
3. Selalu sertakan `clip: true` pada frame level layar untuk memotong sudut
   melengkung 16px.
4. **Samakan node by `name`, bukan ID** — ID numerik bisa bergeser antar save.
