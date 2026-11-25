# Dark Artifact Rules — Kontrak Desain Gelap & Disiplin Eksekusi

Modul ini mengikat aturan desain gelap dengan kontrak builder dan loop
verifikasi. Pasangannya adalah `patterns.md` (token & geometri) dan
`live-editing-workflow.md` (Operasi terminal live).

---

## 1. Supremasi DESIGN.md

Semua warna, padding, margin, gap, radius, dan layout **wajib** mengikuti
`DESIGN.md` dan token `--ks-*` di `design-tokens.css` / `patterns.md`. Tanpa
nilai di luar token, tanpa tebakan angka "kira-kira bagus".

- Custom prompt user mengalahkan `DESIGN.md` **hanya tepat pada yang disebut
  eksplisit** ("tombol biru" = tombol itu biru; gap, radius, dan lain-lain tetap
  mengikuti `DESIGN.md`). Diam = `DESIGN.md` menang.
- Bila custom bertentangan dengan token (mis. meminta neon `#00e5ff`), turuti
  user, tetapi **tulis di laporan** bahwa itu melanggar token — jangan
  diam-diam dinormalkan.

---

## 2. Aturan Artistik di Atas Token

> **Pengecualian kanvas dokumentasi (S-04):** diagram arsitektur, flowchart,
> dan panduan token BUKAN layar kerja — bebas dari kewajiban CTA coral. Jangan
> menempel tombol aksi palsu di kanvas dokumentasi.

1. **Satu protagonis per layar.** Dalam 3 detik jelas apa yang diklik. Tepat
   satu coral primer di atas lipatan; kartu aktif = outline coral 2px, kartu
   lain hairline netral.
2. **Ritme gap 4/8/12/20.** Tidak ada jarak "hampir sama tapi beda".
3. **Hierarki 3 sapuan.** Judul (Space Grotesk Bold) → body (Inter) → meta mono
   (JetBrains Mono, `tabular-nums`).
4. **Cyan hanya data teknis mono** (counter, koordinat, ID). Coral hanya aksi
   utama + outline seleksi aktif.
5. **Badge/chip tanpa border**, di atas soft-tint (`--ks-*-soft`). Progress bar
   3–6px; fill coral hanya saat 100%, selebihnya cyan.
6. **Microcopy nyata.** Button menyebut aksi + objek; error = sebab + jalan
   keluar; empty state = tawaran aksi, bukan ilustrasi. Tanpa lorem/placeholder.
7. **Keyboard & gerak.** Fokus keyboard selalu terlihat; shortcut terlihat;
   hormati `prefers-reduced-motion`; touch target mobile ≥44px.
8. **Detail 1px.** Window bar 32px, traffic lights 12px, grab handle 40×4px,
   satu hairline tunggal. Tanpa gradient, shadow dekoratif, emoji-ikon.

---

## 3. Kontrak Builder (wajib pakai `figcraft_tool.py`)

| Komponen | Builder | Anatomi wajib |
|---|---|---|
| Tombol | `build_button` (+`icon_name`) | frame + ikon vektor + label; 1 coral primer per layar |
| Badge/chip | `build_badge` | frame pil + teks mono; tanpa border, di atas soft-tint |
| Toggle | frame + knob | track success saat ON; radius pil penuh |
| Input | frame + teks | masker kredensial (`••••`), font mono |
| Layar | `Screen_*` | WindowBar + body |
| Dialog/modal | `build_dialog` | Scrim + frame radius 12 + header + body + footer (1 primer + Batal) |
| Empty state | `build_empty_state` | Judul + deskripsi + aksi; tanpa ilustrasi |
| Error inline | `build_error_inline` | Badge tanpa border + sebab + jalan keluar + [Coba lagi] |
| Baris ledger | `build_ledger_row` | `#/Hlm/Asli/Hasil/Muat/Dicek`; separator 1px; 3 state |
| Pipeline bar | `build_pipeline_bar` | 5 tahap, arrow `→`, tahap aktif coral di atas `--ks-accent-soft` |
| Konektor | `build_connector` | network piksel mentah, rute Manhattan, kepala panah otomatis |

**Ikon vs garis — dua mesin berbeda.** `create_vector` mengalikan path sebagai
grid-24 ikon; JANGAN dipakai untuk garis/konektor/panah (koordinat meledak
4–8x). Konektor memakai network piksel mentah dengan `strokes` + `stroke`.
Satu network per panah boleh multi-subpath (garis + kepala panah); siku
ortogonal, bukan diagonal.

**Topologi alur:** tiap node wajib ≥1 incoming + ≥1 outgoing (kecuali
terminal). Panah yatim = cacat.

**Teks multiline:** satu baris = satu node (`D1`/`D2`). Renderer menumpuk `\n`
sehingga baris 2+ menimpa node di bawahnya.

Verifikasi tiap build: `lint_design()` **0 warning** DAN export PNG menunjukkan
glyph/ikon benar-ter-render (membaca JSON saja tidak cukup).

**Reuse (Duplicate → Refine):** sebelum membangun layar, salin node komponen
yang sudah ada lalu sesuaikan bagian yang kurang tepat. Sertakan state nyata —
`empty`, `loading/skeleton`, `error`, `disabled/focus`, dan variasi panjang
teks/data — agar tidak ada layar "bolong". Rincian di
`product-designer-2026.md`.

---

## 4. Loop Verifikasi Wajib 3–5x

Satu pass tidak pernah cukup — cacat visual lolos dari lint (garis raksasa,
tabrakan teks, typo di node dalam). Setiap hasil WAJIB lewat siklus:

```text
Build → lint_design (0 warning) → export PNG → lihat PNG piksel-per-piksel
     → catat semua cacat → perbaiki → (kembali ke Build)
```

**Gate keluar:** minimal **3 pass penuh**; berhenti hanya pada satu pass penuh
bersih (lint 0 + PNG sesuai maksud). Maksimal **5 pass** — bila masih cacat,
hentikan, laporkan sisa cacat, jangan ship.

| Dalih | Kenyataan |
|---|---|
| "Satu export cukup, sudah hijau" | Lint tak melihat tabrakan/tebal garis/slop. PNG satu-satunya bukti. |
| "Pass 1 bagus, skip 2–3" | Selalu ada pass 2; cacat tersembunyi muncul di render kedua. |
| "Cuma teks kecil" | Edit teks = re-export. |
| "5 pass kelamaan" | Ship slop menghabiskan revisi 3x lipat. |

**Red flags — ulangi pass:** klaim "sudah bagus" tanpa PNG baru; memperbaiki
tanpa re-export; membaca JSON sebagai ganti melihat gambar.

**Hard checklist sebelum klaim bersih (S-05):**
1. Utilisasi kanvas ≥60% (bounding box konten vs luas frame; bawah mati >150px = tolak).
2. Nol teks meluber (lint S-08 diam + mata: tak ada glyph menimpa).
3. Topologi graf utuh (tiap node ≥1 masuk + ≥1 keluar, kecuali terminal).
4. Dot/status sesuai kamus semantik (sukses/warn/muted/info tepat makna).
5. Tiga state list berbeda: hover / kursor keyboard / terpilih persisten.
6. `clip: true` pada frame layar.

---

## 5. Aturan Anti-Asumsi (v2.1 — masih berlaku)

Tiga asumsi yang terbukti salah lewat render-evidence — jangan ulangi:

1. **State basi.** Jangan tebak ID/struktur dari sesi lalu. `frames` dulu tiap
   sesi dan setelah `reload`; klaim visual wajib PNG baru.
2. **Vektor butuh `strokes` + `stroke`.** Node hasil `create_vector` wajib
   punya keduanya. File tanpa `strokes` render tak terlihat walau network valid.
3. **Skema dari `save_file` live, bukan tebakan.** Buat node via live API →
   `save_file` → baca `document.json` dari zip. Itu kontrak render engine.
4. **Engine hanya memuat page pertama.** Subtree di page kedua tak terlihat;
   diagram wajib di `pages[0]` atau file terpisah — verifikasi via `frames`.
5. **`open_file` di-cache per path.** Edit headless lalu buka path yang sama =
   basi. Paksa reload: buka file lain dulu, lalu buka kembali file target.

---

## 6. Peta Mesin & Anti-Halu

Engine FigCraft adalah **binary tertutup** — semua klaim perilaku wajib
dibuktikan lewat render, bukan tebakan.

- `figcraft-cli` (bila tersedia) adalah arbiter opsional untuk `export` headless
  dari disk. Skill ini **tidak** bergantung padanya; fallback headless ada di
  script yang dibundling.
- Format `.figcraft` = zip berisi `document.json`. Kunci konektivitas: `parent`
  ↔ `children`, plus `flows`/`prototype`. Kunci layout: `mode/wrap/gap/
  cross_gap/padding/main_align/cross_align` (+`grid_*`). Kunci teks:
  `characters/style/fills`.
- Untuk mengetahui "node X nyambung ke apa": ikuti rantai `parent` ke atas dan
  daftar `children` ke bawah — jangan tebak ID.

**Tiga hukum besi (pelanggaran = halu):**

1. **`save()` selalu reflow.** `resolve_tree_layout` menghitung ulang SEMUA
   posisi anak autolayout. Jangan tune `y` manual — akan revert saat save
   berikutnya. Perbaiki struktur (layout/padding/sizing).
2. **Piksel > mata > JSON.** Ukur posisi lewat export + baris glyph, bukan
   "kelihatannya" di PNG dan bukan angka JSON.
3. **Sesi live bisa basi.** `reload --hard` sebelum klaim, atau pakai headless
   yang membaca dari disk. Bila ragu, buat file probe kecil dan ukur pikselnya.

---

## 7. Identitas Nama + Disiplin File Hidup

ID numerik node **bisa bergeser antar save aplikasi** — peta ID lama bisa
menunjuk node yang salah. Aturannya:

1. **Samakan node by `name`, bukan ID.** Sebelum mutasi, cetak pasangan
   `id + name` hasil load FRESH dan cocokkan nama yang dimaksud.
2. **Jangan tulis selagi aplikasi user terbuka.** Tulis balapan dengan save
   aplikasi menghapus kerja salah satu pihak. Koordinasi: minta jeda, backup,
   tulis, minta reload. Selalu backup sebelum save pertama.
3. **Lint + parity SETIAP save menangkap nyasar.** Drift >2px atau warning baru
   vs baseline backup = edit salah sasaran — revert dulu, selidiki kemudian.
