# DESIGN.md — Portable Design Constitution (kuron-design-figcraft 3.0.0)

Aturan visual + layout yang mengikat seluruh desain yang dibuat dengan skill
ini. Sumber nilai: `design-tokens.css` di direktori yang sama — jangan mengarang
warna di luar token `--ks-*`. Pasangan dokumen ini: `patterns.md` (spesifikasi
teknis) dan `dark-artifact-rules.md` / `light-glass-system.md` (modul tema).

---

## Arah

Dense desktop workbench, bukan landing page. Quiet, tight rows, grup jelas.
Satu protagonis per layar. Cyan hanya data teknis, coral hanya aksi utama.

## Token

- Single source: `--ks-*` di `design-tokens.css` (dark default + light).
  Pasangan teks/latar minimal WCAG AA.
- Peran warna: **coral = aksi utama saja**; **cyan = info teknis** (koordinat,
  ID, counter); success/warn/danger/info = status. Tanpa gradient, shadow
  dekoratif, emoji sebagai ikon.
- Font (bundel offline, bukan CDN): Inter = UI, Space Grotesk = brand/heading,
  JetBrains Mono = angka + nama file. Angka memakai `.tnum` (tabular-nums).
- Kontrol mengikuti tabel skala ukuran di bawah (tinggi, radius, ikon, touch
  target); separator garis 1px.

### Skala ukuran (satu-satunya yang boleh dipakai)

| Elemen | sm | md (default) | lg | Konstanta |
|---|---|---|---|---|
| Button | 28px | 32px | 40px | `build_button(..., size=)` |
| Field / input / dropdown | — | 36px | — | pengecualian 32px hanya di dalam dropdown |
| Segmented group | 28px | 32px | — | samakan dengan Button di sebelahnya |
| Icon | 16px | 20px | 24px | Lucide grid 24, `stroke=currentColor` |
| Radius | 6px (kontrol) | 12px (kartu/panel/modal) | 9999px (pill/badge) | `--radius-card` |
| Touch target | min 44px (mobile/tablet) | — | — | drawer, FAB, gagang sheet |

## Primitif

Primitif yang tersedia: `.btn` (primary/default/ghost/danger/small/on/disabled),
`.field`, `.badge` (ok/run/warn/err/cy/mute), `.dot`. Implementasi di build
script memakai builder `figcraft_tool.py`; untuk web/CSS pakai token
`design-tokens.css`. Button menamai aksi + objek. Error menyebut sebab + jalan
keluar. Empty state menawarkan aksi, bukan ilustrasi.

## Layout

| Layar | Pola |
|---|---|
| Dashboard | Kartu 300px: cover, judul, counter mono, progress bar tipis, badge mode |
| Daftar halaman | Pipeline bar 5 tahap (Import→Deteksi→Terjemah→Review→Ekspor) + grid kartu; terpilih = outline coral |
| Editor | 3 kolom 196px / 1fr / 268px: daftar, kanvas + outline coral, inspector |
| Ledger | Tabel dense: `# \| Hlm \| Asli \| Terjemahan \| Muat \| Dicek`; filter + search + footer ringkasan |
| Tablet 834 | Rail ikon 64px + kartu 3 kolom + bottom sheet 40% |
| Mobile 390 | Grid 2 kolom + tab bar 56px |

String UI default Bahasa Indonesia; perlakukan sebagai locale yang dapat diganti.
Fokus keyboard selalu terlihat; hormati `prefers-reduced-motion`.

## Peran → token

Satu peran = satu token. Tint selalu
`color-mix(in srgb, var(--token) N%, transparent)`, tidak pernah hex baru →
paritas dark/light otomatis.

| Peran | Token | Catatan |
|---|---|---|
| Kanvas aplikasi | `--ks-bg` | latar window terdalam |
| Panel di atas kanvas | `--ks-surface` | latar halaman kerja |
| Panel bertumpuk | `--ks-surface-2` | header, toolbar, rail |
| Kartu / modal terangkat | `--ks-raised` | elevasi level 2–3, bukan shadow bebas |
| Hover baris list | `--ks-hover` | sementara; hilang saat pointer pergi |
| Baris terpilih persisten | `--ks-selected` | opt-in `[data-current="true"]` |
| Kursor keyboard | tint + inset ring | `color-mix(in srgb, var(--ks-text) 12%, transparent)` + `inset 0 0 0 1px var(--ks-ring)` |
| Garis rambut | `--ks-line` | semua pembatas struktural 1px |
| Garis kuat | `--ks-line-strong` | kontur jendela luar, border dialog |
| Cincin fokus | `--ks-ring` | `:focus-visible` + halo seleksi; bukan dekorasi |
| Aksi utama | `--ks-accent` | satu-satunya aksi afirmatif per alur |
| Info teknis | `--ks-cyan` | hanya koordinat, ID, counter — selalu mono + `.tnum` |
| Status | `--ks-success/warn/danger/info` (+`-soft`) | badge tanpa border di atas soft-tint |

## Elevasi (3 level, tidak ada level keempat)

| Level | Komposisi | Pakai untuk |
|---|---|---|
| 1 | border hairline `--ks-line`, tanpa shadow | default — hampir semua hal |
| 2 | border + shadow halus | kontrol outline, kartu tertanam |
| 3 | border `--ks-line-strong` + shadow floating | popover / dialog lepas dari kanvas |

Butuh lebih dari level 3 biasanya berarti yang dicari adalah fokus `--ks-ring`,
bukan shadow. Level keempat dilarang.

## Baris list

| State | Tampilan |
|---|---|
| idle | transparan |
| hover | `--ks-hover` |
| kursor keyboard | tint foreground + inset `--ks-ring` |
| aktif persisten | `--ks-selected` + `[data-current="true"]` |

Tiga state harus berbeda dan terlihat — hover / kursor / terpilih tidak boleh
saling menyamar.

## Perilaku UX

| Durasi | Yang ditampilkan |
|---|---|
| 0–100 ms | tidak ada |
| 100 ms–1 s | disable kontrol saja |
| 1–3 s | disable + spinner |
| 3 s+ / multi-tahap | label progres per tahap |

- `disabled` di-bind segera; spinner baru muncul setelah ~200 ms.
- Ruang label yang berganti dipesan (`width`, bukan `min-width`).
- Copy tidak overclaim: verb hasil hanya bila ada data nyata; selama proses
  pakai bahasa netral; tanpa pengisi.
- Error menyebut sebab + jalan keluar — termasuk toast.
- Jalur mundur sunyi (Batal / Tutup / Buang): ghost, tanpa aksen; `Esc` selalu
  menutup lapisan teratas.
- Shortcut mengikuti binding nyata (`⌘`/`⇧` di macOS, `Ctrl+`/`Shift+` di lain).
- `prefers-reduced-motion` dihormati per elemen; spinner tetap hidup.
- Kosong vs error vs loading berbeda: kosong → aksi; toast → hasil sesaat;
  error yang harus dibaca/di-retry → inline persisten.

## Supremasi

`DESIGN.md` ini mengikat semua warna, padding, margin, gap, radius, dan layout.
Custom prompt user mengalahkan dokumen ini **hanya** pada yang disebut eksplisit.
Diam = dokumen ini menang. Pelanggaran dicatat di laporan, tidak dinormalkan
diam-diam.
