---
name: kuron-design-figcraft
description: Design token-driven UI screens in FigCraft (.figcraft) - dark workbench, light glassmorphism, live terminal editing, and a mandatory 3-5x pixel-verification loop before any design claim.
metadata:
  author: Kuron Studio Team
  license: MIT
  version: "3.0.0"
---

# kuron-design-figcraft — Token-Driven Design + FigCraft Visual Verification

Satu skill mandiri untuk merancang, memodifikasi, dan memverifikasi layar UI
dalam format `.figcraft`. Skill ini menyatukan tiga produk lama
(`kuron_design_crafting`, `kuron_glass_light_design`, `figcraft_live_editing`)
menjadi satu kontrak yang tak terpisahkan dengan script pendampingnya:

- **Yin (kontrak):** aturan token, estetika, dan kriteria lulus — ada di
  `SKILL.md` ini dan `references/`.
- **Yang (eksekusi):** builder, linter, terminal live, dan exporter — ada di
  `scripts/`.

Aturan tanpa script tak tereksekusi; script tanpa aturan melahirkan *slop*.
Setiap perubahan pada satu sisi WAJIB memutakhirkan sisi lain dan mengunci
versi yang sama di `VERSION`, frontmatter ini, dan `HARNESS_VERSION`.

Kompatibel dengan Claude Code, Codex, Cursor, Antigravity, dan harness generik.
Tidak bergantung pada path absolut, repo tertentu, atau kredensial apa pun.

---

## Peta Modul

| Kebutuhan | Baca | Pakai script |
|---|---|---|
| Brief domain, opsi gaya UX/IA, state, handoff | `references/product-designer-2026.md` | — |
| Token warna, tipografi, geometri, layout | `references/patterns.md` | `figcraft_tool.py`, `quick_design.py` |
| Aturan gelap, builder, anti-asumsi, supremasi DESIGN.md | `references/dark-artifact-rules.md` | `figcraft_tool.py`, `build_artistic_flow.py` |
| Light mode, glassmorphism, komponen & state | `references/light-glass-system.md` | `figcraft_tool.py` |
| Sesi live, port, sinkronisasi, guardrail | `references/live-editing-workflow.md` | `agent_terminal.py`, `multi_agent_worker.py` |
| Sumber nilai warna portabel | `references/design-tokens.css`, `references/DESIGN.md` | — |
| Audit objektif (utilisasi, overflow, topologi) | `references/dark-artifact-rules.md` | `audit_render.py` |

Semua perintah di bawah dijalankan dari **root paket skill** ini. Path relatif
bersifat portabel; `scripts/agent_terminal.py` mendukung flag global
`--port <PORT>` yang ditulis **sebelum** subcommand.

---

## 0. Product Designer 2026 — Empat Pilar (gerbang sebelum desain)

Rincian: `references/product-designer-2026.md`. Ringkasnya:

1. **Domain → outcome → opsi gaya.** Brief 4 pertanyaan (jenis aplikasi, target
   user, masalah, hasil terukur), lalu tawarkan 2–3 arah gaya/tata letak
   (`dense operational`, `bento/modular`, `editorial`, `clean utility`) sesuai
   konteks — pengguna yang memilih. Tolak AI slop; utamakan *cognitive clarity*.
2. **Desain menyeluruh, zero "bolong".** UX flow + IA, microcopy fungsional
   (aksi+objek, sebab+solusi), state lengkap (`empty`, `loading`, `error`,
   `disabled/focus`, panjang teks/data), pola AI yang transparan bila relevan,
   serta aksesibilitas & handoff yang realistis dibangun.
3. **Component-first: `Duplicate → Refine`.** Bangun komponen dasar dulu
   (input, form, button, icon, card/list item) dengan variant jelas dan
   hierarki token `primitive → semantic → component`. Di FigCraft, salin node
   komponen yang ada lalu sesuaikan — jangan rakit ulang dari nol per layar.
4. **Eksekusi tajam.** Keputusan terukur dan langsung ke inti; time-box singkat,
   tanpa analisis bertele-tele. Guardrail (0 path privat, 0 secret, test hijau,
   PNG 3–5x) tetap mutlak.

---

## 1. Filosofi Inti

1. **Token adalah satu-satunya sumber nilai.** Warna, padding, gap, radius,
   dan tipografi mengikuti `references/design-tokens.css` (namespace `--ks-*`)
   dan `references/DESIGN.md`. Dilarang mengarang angka atau hex "kira-kira
   bagus". Custom prompt user menang **hanya** pada yang disebut eksplisit;
   diam = DESIGN.md menang.
2. **Satu protagonis per layar.** Tepat satu aksi utama coral di atas lipatan.
   Cyan hanya untuk data teknis monospace (koordinat, ID, counter).
3. **Dense workbench, bukan landing page.** Baris rapat tapi bernapas, grup
   jelas, ritme gap `4 / 8 / 12 / 20`, tanpa gradient, shadow dekoratif,
   atau emoji sebagai ikon.
4. **Piksel > mata > JSON.** Lint hijau bukan bukti. Satu-satunya bukti
   kebenaran visual adalah PNG hasil export yang dibuka dan diperiksa.
5. **Setiap klaim visual harus segar.** Sesi live bisa basi, ID bisa bergeser,
   dan `save()` selalu menjalankan reflow.

---

## 2. Alur Kerja End-to-End

```text
baca references/ → tentukan modul (gelap / terang / keduanya)
      ↓
build/compile (quick_design.py atau figcraft_tool.py)
      ↓
lint_design() → 0 warning
      ↓
agent_terminal.py --port 9880 start --file <file>.figcraft
      ↓
frames → ambil ID asli (JANGAN menebak)
      ↓
edit → watch / reload --soft → export / export-all
      ↓
buka PNG → catat cacat → perbaiki → ULangi (minimal 3, maksimal 5 pass)
      ↓
audit_render.py → stop → laporan
```

Contoh minimal:

```bash
python3 scripts/quick_design.py "Dashboard ringkas" -o out/workbench.figcraft --preview
python3 scripts/agent_terminal.py --port 9880 start --file out/workbench.figcraft
python3 scripts/agent_terminal.py --port 9880 frames
python3 scripts/agent_terminal.py --port 9880 export-all -o out/previews/ --scale 2
python3 scripts/audit_render.py out/workbench.figcraft
python3 scripts/agent_terminal.py --port 9880 stop
```

Port bukan konstanta sakral: gunakan `--port` pada setiap perintah, atau
`--port` saat menjalankan `quick_design.py`. Default `9880` hanya nilai awal.

---

## 3. Modul Gelap — Dark Workbench

Rincian lengkap: `references/dark-artifact-rules.md` dan
`references/patterns.md`. Ringkasan operasional:

- **Builder wajib** (dari `figcraft_tool.py`): `build_button`,
  `build_badge`, `build_connector`, `build_dialog`, `build_empty_state`,
  `build_error_inline`, `build_ledger_row`, `build_pipeline_bar`,
  `Screen_*`. Jangan merakit node manual.
- **Ikon vs garis:** `create_vector` = grid-24 untuk ikon; konektor/panah
  memakai `build_connector` (network piksel mentah, rute Manhattan, kepala
  panah otomatis). Jangan campur keduanya.
- **Teks multiline:** satu baris = satu node. Renderer menumpuk `\n`.
- **Widget wajib:** `lint_design()` 0 warning DAN export PNG membuktikan
  glyph/ikon benar-ter-render.
- **Kanvas dokumentasi** (diagram, flowchart, panduan token) dikecualikan
  dari kewajiban CTA coral — jangan tempel tombol palsu.

---

## 4. Modul Terang — Light Glassmorphism

Rincian lengkap: `references/light-glass-system.md` (sudah lengkap termasuk
Modal Dialog, Verification Checklist, dan aturan paritas Light/Dark).

- Kanvas hangat `#F7F6F4` (bukan putih murni), sebagai ganti permukaan
  gelap saat tema terang.
- Kaca buram (frosted glass) **hanya** untuk krom/navigasi/inspector
  mengambang — tidak pernah menimpa area baca.
- Satu CTA `--ks-accent` `#C4342A`; cyan teknis `#0B6E78` + `tabular-nums`.
- Di `.figcraft`, glass WAJIB memakai efek native `effect.add` bertipe
  `glass`, bukan sekadar fill transparan.
- Ikon Lucide, grid 24, stroke 1.75px, nol emoji. Radius `6 / 12 / 16 /
  9999`, tiga level elevasi (level keempat dilarang).
- **Paritas terang/gelap:** setiap token terang punya pasangan gelap; tint
  memakai `color-mix`, bukan hex baru.

---

## 5. Modul Live — Live Terminal Editing

Rincian lengkap: `references/live-editing-workflow.md`.

```bash
python3 scripts/agent_terminal.py --port 9880 start --file <file>.figcraft
python3 scripts/agent_terminal.py --port 9880 frames          # discover ID
python3 scripts/agent_terminal.py --port 9880 exec node.set '{"id": <ID>, "name": "<nama>"}'
python3 scripts/agent_terminal.py --port 9880 diff --id <ID>
python3 scripts/agent_terminal.py --port 9880 watch <file>.figcraft -o out/previews/ --scale 2 --max-events 200 --max-seconds 600
python3 scripts/agent_terminal.py --port 9880 export-all -o out/previews/ --scale 2
python3 scripts/agent_terminal.py --port 9880 stop
```

Guardrail:

- Flag `--port` **sebelum** subcommand; path `.figcraft` tahan-cwd.
- `exec` menolak JSON invalid dengan pesan ramah.
- `frames` dulu sebelum `export`/`exec`; ulangi setelah `reload`.
- `reload --soft` default; `--hard` hanya bila struktur basi.
- `watch` selalu dibatasi `--max-events` / `--max-seconds` (cut-loop guard).
- Jangan dua writer bersamaan pada satu file; `watch` hanya membaca.
- Jangan klaim dari metadata JSON — bukti = PNG.

Untuk kerja paralel, `multi_agent_worker.py` memakai partisi namespace ID
(A `1000–1999`, B `2000–2999`, C `3000–3999`) + lock `.figcraft.lock`.

---

## 6. Loop Verifikasi Wajib 3–5x

Setiap hasil WAJIB lewat siklus tertutup ini:

1. **Build** → 2. **`lint_design()`** (0 warning) → 3. **export PNG** →
4. **buka PNG, periksa piksel per piksel** → 5. **catat semua cacat** →
6. **perbaiki** → kembali ke 1.

**Gate keluar:** minimal **3 pass penuh**, berhenti hanya pada satu pass
bersih (lint 0 + PNG sesuai maksud). Maksimal **5 pass**; bila masih cacat,
hentikan dan laporkan sisa cacat — jangan ship.

| Dalih | Kenyataan |
|---|---|
| "Satu export cukup, sudah hijau" | Lint tak melihat tabrakan, garis raksasa, atau typo di node dalam. |
| "Pass 1 bagus, skip 2–3" | Selalu ada pass 2; cacat tersembunyi muncul di render kedua. |
| "Cuma teks kecil, tak perlu re-export" | Edit teks = re-export. |
| "5 pass kelamaan" | Ship *slop* menghabiskan revisi 3x lipat. |

**Hard checklist sebelum klaim bersih:** utilisasi kanvas ≥60%; nol teks
meluber; topologi graf utuh (tiap node ≥1 masuk + ≥1 keluar kecuali
terminal); dot/status sesuai kamus semantik; state hover/kursor/terpilih
tiga state berbeda; `clip: true` pada frame layar.

---

## 7. Aturan Anti-Asumsi & Anti-Halu

1. **State basi:** `frames` tiap sesi dan setelah `reload`; klaim visual
   wajib PNG baru.
2. **Vektor butuh `strokes` + `stroke`:** keduanya wajib ada pada node hasil
   `create_vector`.
3. **Skema dari `save_file` live, bukan tebakan:** baca `document.json` dari
   zip hasil save sebagai kontrak render.
4. **Engine hanya memuat `pages[0]`:** subtree di page lain tak terlihat.
5. **`open_file` di-cache per path:** edit headless lalu buka path yang sama
   = basi; paksa reload via close+open.
6. **`save()` selalu reflow:** jangan tune `y` manual — perbaikan lewat
   struktur (layout/padding/sizing) atau akan revert saat save berikutnya.
7. **Binary engine tertutup:** `figcraft-cli` adalah arbiter opsional; bila
   tidak tersedia, pakai fallback headless yang dibundling. Jangan berteori
   soal perilaku engine — buat file probe kecil dan ukur pikselnya.

---

## 8. Identitas Nama & Disiplin File Hidup

ID numerik node **bisa bergeser antar save**. Sebelum mutasi, cocokkan pasangan
`id + name` hasil load **fresh**; samakan node by `name`, bukan ID.

Jangan menulis file selagi aplikasi user terbuka — minta jeda, backup, lalu
koordinasi reload. Lint + parity pada **setiap save** menangkap edit nyasar:
drift >2px atau warning baru vs baseline = revert dulu, selidiki kemudian.

---

## 9. Kontrak Script & Version Lock

| Berkas | Peran |
|---|---|
| `scripts/figcraft_tool.py` | builder, `TOKENS`, `lint_design()`, `save()`, klien JSON-RPC |
| `scripts/build_artistic_flow.py` | `resolve_tree_layout()` dipakai `save()`; generator alur lengkap |
| `scripts/agent_terminal.py` | start/stop/frames/export/export-all/reload/diff/watch/exec/harness-info |
| `scripts/quick_design.py` | generator cepat + preview PNG |
| `scripts/audit_render.py` | audit utilisasi/overflow/topologi/semantik |
| `scripts/multi_agent_worker.py` | partisi ID + lock untuk kerja paralel |

Semua subprocess dan socket memakai timeout; semua loop pembacaan/polling
punya batas keras (*cut-loop guard*), sehingga agen tak pernah menggantung.
Lokasi binary FigCraft bisa diganti lewat env var `FIGCRAFT_APP` (default
platform macOS), dan file kerja lewat `FIGCRAFT_DESIGN`.

Versi tunggal: `VERSION` = frontmatter `metadata.version` =
`HARNESS_VERSION` = manifest `harness-info` = **`3.0.0`**.
`install.sh` menolak instalasi bila versi tidak sinkron.
