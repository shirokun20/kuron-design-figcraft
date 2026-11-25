# Light Mode + macOS Glassmorphism & Design System

Standar resmi untuk merancang **Light Mode + macOS Glassmorphism** dan
**Design System / Components Library** di `kuron-design-figcraft` (`.figcraft`
maupun implementasi UI). Semua nilai token Light Mode selaras **1:1** dengan
`design-tokens.css` (blok `:root[data-theme="light"]`) dan `DESIGN.md`.
Untuk alur live editing, gunakan `live-editing-workflow.md`.

---

## 1. Filosofi Visual: Eye-Comfort & Zero AI Slop

1. **Anti-Silau untuk Sesi Panjang:** kanvas utama memakai warm paper `#F7F6F4`
   (`--ks-bg`), bukan putih murni di seluruh layar. Area di balik halaman
   memakai `--ks-raised` (`#E8E7E3`) agar halaman putih tetap punya pemisah
   lembut tanpa menyilaukan mata.
2. **Vibrancy macOS yang Tenang:** kaca buram hanya untuk lapisan krom/navigasi/
   inspector mengambang — **bukan** menimpa teks atau area baca.
3. **Zero AI Slop:**
   - Dilarang gradasi ungu/biru/pelangi, glow neon (`#00e5ff`), atau shadow hitam pekat.
   - **Satu protagonis per layar:** tepat 1 CTA utama (`--ks-accent` `#C4342A`) di atas lipatan.
   - **Ramah orang awam:** label lugas yang menyebut aksi + objek, tanpa jargon teknis tanpa penjelasan.
   - **Pemisahan jelas:** teks asli vs hasil vs elemen aktif (`--ks-accent` 2px) vs data teknis mono (`--ks-cyan` `#0B6E78` + `tabular-nums`) langsung terbaca dalam 3 detik.

---

## 2. Color System (1:1 `design-tokens.css` Light Mode + Glass Tokens)

### A. Token Permukaan, Border & Teks (`:root[data-theme="light"]`)

| Token | Light Hex | Dark Parity | Peran Semantik |
|---|---|---|---|
| `--ks-bg` | `#F7F6F4` | `#0D0D10` | Kanvas aplikasi hangat (anti-silau) |
| `--ks-surface` | `#FFFFFF` | `#141418` | Panel kerja utama / kartu solid |
| `--ks-surface-2` | `#F1F0ED` | `#1A1A20` | Header, toolbar, rail navigasi |
| `--ks-raised` | `#E8E7E3` | `#22222A` | Latar kanvas, kartu terangkat |
| `--ks-hover` | `#DEDDD8` | `#2A2A33` | State hover sementara |
| `--ks-selected` | `#D8D7D1` | `#34343F` | Baris/item terpilih persisten (`[data-current="true"]`) |
| `--ks-line` | `#DFDFD9` | `#26262E` | Garis rambut pembatas struktural 1px |
| `--ks-line-strong` | `#C4C3BC` | `#35353F` | Kontur jendela luar & dialog modal |
| `--ks-ring` | `#55555F` | `#9A9AA8` | Cincin fokus `:focus-visible` (bukan dekorasi) |
| `--ks-text` | `#16161A` | `#ECECF1` | Teks utama, judul, label aktif (WCAG AA) |
| `--ks-text-2` | `#55555F` | `#A5A6B0` | Teks sekunder, label form, metadata |
| `--ks-text-3` | `#7C7C86` | `#71727D` | Placeholder, shortcut, teks non-aktif |

### B. Token Aksen & Semantik

| Token | Light Hex | Soft Tint | Dark Parity | Aturan Pakai |
|---|---|---|---|---|
| `--ks-accent` | `#C4342A` | `#FBE9E7` | `#FF6B5A` | **Aksi utama saja** (hover `#A62A21`, fg `#FFFFFF`), outline aktif |
| `--ks-cyan` | `#0B6E78` | `#E0F2F4` | `#35E7F5` | **Hanya data teknis mono** (koordinat, ID, counter `.tnum`) |
| `--ks-success` | `#1F7A4D` | `#E4F3EA` | `#5FD99A` | Status selesai, online |
| `--ks-warn` | `#8A5A00` | `#FBF0DC` | `#FFC15E` | Proses berjalan, perlu review |
| `--ks-danger` | `#B3261E` | `#FDE8E6` | `#FF5C5C` | Aksi destruktif, error |
| `--ks-info` | `#1F5FBF` | `#E5EEFB` | `#6BA6FF` | Info netral, tips workflow |

### C. macOS Glassmorphism & Vibrancy Tokens

| Token | Nilai | Blur | Kegunaan |
|---|---|---|---|
| `--ks-glass-bg` | `rgba(255,255,255,0.72)` | `20px` | Panel frosted utama, sidebar, inspector |
| `--ks-glass-toolbar` | `rgba(241,240,237,0.78)` | `16px` | WindowBar, top toolbar, segmented bar |
| `--ks-glass-floating` | `rgba(255,255,255,0.88)` | `24px` | Floating mini-toolbar, popover, dropdown, modal dialog |
| `--ks-glass-specular` | `rgba(255,255,255,0.70)` | — | Highlight hairline 1px di tepi atas/dalam panel kaca |
| `--ks-glass-border` | `rgba(22,22,26,0.08)` | — | Border hairline luar panel kaca (fallback `--ks-line`) |
| `--ks-glass-shadow` | `0 8px 24px rgba(22,22,26,0.08), 0 1px 2px rgba(22,22,26,0.04)` | `24px, y 8px` | Kedalaman difus lembut ala macOS; dilarang shadow gelap pekat |

> **Representasi Wajib di `.figcraft` (Native FigCraft Glass Effect):** jangan
> hanya menumpuk fill transparan datar. Wajib `effect.add` dengan `"type":
> "glass"`: `depth: 20–26`, `frost: 8–12`, `refraction: 0.85–0.94`,
> `dispersion: 0.35–0.45`, `lightAngle: -45`, `lightIntensity: 0.92–0.96`,
> `splay: 0.18–0.22`, dipasangkan tint `#FFFFFF` opacity `0.28–0.40`, specular
> stroke `#FFFFFF` (`0.78–0.80`), `dropShadow` lembut (`#16161A16`,
> `offset: [0, 8]`, `radius: 24`), serta latar ambient hangat di belakang panel
> kaca agar bias kaca benar-benar terasa.

---

## 3. Iconography System (Lucide Standard)

- **Library:** Lucide Icons (konsisten di seluruh aplikasi, tanpa campuran pack
  lain, **nol emoji** sebagai ikon UI).
- **Grid & Stroke:** kanvas `24×24px`, `stroke-width: 1.75px` (atau `1.5px` di
  ukuran `14px`), `stroke-linecap: round`, `stroke-linejoin: round`,
  `stroke="currentColor"`.
- **Skala resmi:** `14px` (badge/chip, metadata, shortcut), `16px` (tombol
  sm/md, input prefix/suffix, dropdown), `20px` (toolbar, rail), `24px`
  (header dialog, empty state, status utama).
- **Warna semantik ikon:** default `--ks-text-2`, aktif `--ks-text` atau
  `--ks-accent`, teknis `--ks-cyan`, status mengikuti
  `--ks-success/warn/danger/info`.

---

## 4. Typography, Spacing, Radius & Elevation

### A. Skala Tipografi
- **Display / Screen Title:** `Space Grotesk`, Bold, `20pt`, line-height `1.25`.
- **Section Heading:** `Inter`, Bold, `15pt`, line-height `1.35`.
- **Body:** `Inter`, Medium, `13pt`, line-height `1.45`.
- **Button / Control Label:** `Inter`, SemiBold, `12pt`, line-height `1.2`.
- **Caption / Helper:** `Inter`, Regular, `11pt`, line-height `1.4`.
- **Mono / Counter / Koordinat:** `JetBrains Mono`, SemiBold, `10–11pt`,
  `font-variant-numeric: tabular-nums` (`.tnum`).

### B. Spacing, Radius & Elevation
- **Ritme gap & padding:** kelipatan ketat `4 / 8 / 12 / 16 / 20 / 24 px`.
  Jangan angka ganjil seperti `7px` atau `13px`.
- **Radius:** `6px` (kontrol), `12px` (kartu, glass panel, mini-toolbar,
  modal), `16px` (root macOS window), `9999px` (badge, status dot, slider thumb).
- **3 level elevasi:**
  - **Level 1 (Flat/Hairline):** border 1px `--ks-line`, tanpa shadow — default.
  - **Level 2 (Raised Glass):** `--ks-glass-bg` + specular + shadow `y:2, blur:8`.
  - **Level 3 (Floating Glass):** `--ks-glass-floating` + specular +
    `--ks-glass-shadow` (`y:8, blur:24`). **Level 4 dilarang.**

---

## 5. Reusable Components Library & States

Semua komponen wajib memakai Auto-Layout dan mendukung state `Default`,
`Hover`, `Focus` (`2px solid --ks-ring`, offset `2px`), dan `Disabled`
(`opacity: 0.45`).

| Komponen | Spesifikasi Anatomi & Ukuran | Variants & States |
|---|---|---|
| **Button** | Tinggi `sm:28`, `md:32` (default), `lg:40`; radius `6px`; gap `6–8px`; label Inter SemiBold 12pt + ikon 16px | Primary (`#C4342A`, hover `#A62A21`, teks `#FFFFFF`), Secondary (`--ks-surface` + border `--ks-line-strong`), Ghost (transparan, hover `--ks-hover`), Danger (`--ks-danger` / soft) |
| **Input / Field & Dropdown** | Tinggi `36px`; radius `6px`; padding `12px`; ikon `16px`; teks 13pt | Default (`--ks-surface` + `--ks-line`), Focus (ring `--ks-ring`), Error (border `--ks-danger` + pesan sebab & solusi di bawah) |
| **Badge / Chip** | Tinggi `20px`; radius `9999px`; padding `8×2px`; tanpa border; JetBrains Mono 10pt | ok / warn / danger / info / cy di atas soft-tint masing-masing |
| **Segmented Control** | Tinggi `28px`/`32px`; container `--ks-surface-2` + border `--ks-line`; radius `6px`; item aktif `--ks-surface` + shadow Level 1 | Mode, perataan teks, dll. |
| **Slider** | Track `4px` `--ks-line-strong`; fill `--ks-accent` (atau `--ks-cyan` untuk teknis); thumb `14px` + border + shadow halus | Selalu disertai label nilai mono `.tnum` |
| **Color Swatch / Picker** | Kotak `24×24px` radius `6px` + border `--ks-glass-border`; preset cepat + input hex mono | Active swatch = ring luar `2px --ks-accent` (offset `2px`) |
| **Floating Mini-Toolbar** | Tinggi `36px`; `--ks-glass-floating` + specular + shadow; radius `12px`; padding `4px 8px`; gap `4px` | Muncul tepat di bawah bounding box seleksi: Font, Ukuran, Warna, Tebal, Rata, Duplikat, Hapus |
| **Glass Card / Panel** | `--ks-glass-bg`; radius `12px`; padding `12–16px`; border `--ks-glass-border` + highlight atas | Kartu proyek, sidebar, inspector `280px` |
| **Modal Dialog** | `--ks-glass-floating`; radius `12px`; scrim `rgba(22,22,26,0.28)`; header (judul + tombol `Tutup` ghost) + body + footer (`Batal` ghost + **1** CTA primary) | `Esc` selalu menutup dialog; klik scrim menutup; fokus terjebak di dalam dialog |

### Catatan Modal Dialog (dilengkapi)

Urutan anatomi wajib, dari luar ke dalam:

1. **Scrim** menutup seluruh frame layar, warna `rgba(22,22,26,0.28)`, tanpa blur
   tambahan (glass sudah ada pada dialog).
2. **Surface dialog** memakai `--ks-glass-floating` + native glass effect, radius
   `12px`, lebar maksimal `560px`, elevasi Level 3.
3. **Header:** judul `Space Grotesk Bold 15pt` + tombol `Tutup` bertipe ghost
   (tanpa aksen, tanpa chip shortcut).
4. **Body:** satu kalimat akibat konkret + field bila perlu. Error inline = sebab
   + jalan keluar, bukan hanya kode.
5. **Footer:** tepat satu CTA primary coral + `Batal` ghost. Jangan dua CTA primer.
6. **Perilaku:** `Esc` selalu menutup lapisan teratas; fokus awal di judul atau
   field pertama; fokus tidak keluar dialog sampai ditutup; setelah tutup,
   fokus kembali ke elemen pemicu.

Dilarang menaruh ilustrasi dekoratif, gradient, atau shadow gelap di dalam dialog.

---

## 6. Verification Checklist (wajib sebelum klaim selesai)

Loloskan **semua** butir sebelum export/klaim visual:

1. Kanvas memakai warm paper `#F7F6F4`, bukan putih murni seluruh layar.
2. Glass hanya pada krom/navigasi/inspector — tidak menimpa area baca.
3. Tepat satu CTA primer `#C4342A` di atas lipatan.
4. Cyan `#0B6E78` hanya untuk data teknis mono + `tabular-nums`.
5. Nol emoji sebagai ikon; semua ikon Lucide grid 24, stroke 1.75px.
6. Badge/chip tanpa border di atas soft-tint yang tepat.
7. Gap dan padding hanya kelipatan `4 / 8 / 12 / 16 / 20 / 24`.
8. Radius hanya `6 / 12 / 16 / 9999`; elevasi maksimal Level 3.
9. `Focus` memakai ring `2px --ks-ring` offset `2px`, terlihat jelas.
10. `Disabled` memakai `opacity: 0.45`, bukan warna baru.
11. Modal punya satu CTA primer, `Esc` menutup, fokus terjebak di dalam.
12. Teks asli / hasil / aktif / teknis terbaca beda dalam 3 detik.
13. Lint 0 warning **dan** PNG hasil export sudah dibuka piksel per piksel.
14. Paritas light/dark lolos (bagian 7) untuk setiap token yang dipakai.

---

## 7. Light/Dark Parity Rules

1. **Setiap token light punya pasangan dark** di `design-tokens.css`. Memakai
   token light tanpa pasangan dark = cacat paritas.
2. **Satu peran = satu token.** Jangan mengarang warna "selected" atau "hover"
   per layar; pakai `--ks-selected` / `--ks-hover`.
3. **Tint selalu turunan token:** `color-mix(in srgb, var(--token) N%, transparent)`.
   Dilarang hex baru untuk soft background — dengan itu paritas otomatis.
4. **Teks/latar minimal WCAG AA** di kedua tema. `--ks-text` di light `#16161A`
   dan di dark `#ECECF1` sudah memenuhi.
5. **`--ks-accent` berubah makna warna** (`#C4342A` light / `#FF6B5A` dark),
   tetapi **makna semantiknya tetap**: aksi utama. Jangan menukar perannya.
6. **`--ks-cyan` juga berubah nilai** (`#0B6E78` / `#35E7F5`) dengan peran
   tetap: data teknis mono.
7. **Status (success/warn/danger/info)** wajib dibaca di kedua tema; bila
   kontras turun, perbaiki pasangan tokennya, jangan menimpa dengan hex ad hoc.
8. **Uji paritas dengan latar ambient:** kaca light butuh latar hangat di
   belakangnya; kaca dark butuh surface bertingkat. Tanpa itu, efek glass
   jadi datar dan hasil render menyesatkan.

---

## 8. Penutup

Modul ini melengkapi `dark-artifact-rules.md`: gelap dan terang memakai
kontrak builder, lint, dan loop verifikasi 3–5x yang sama — yang berubah hanya
token warna, representasi glass, dan checklist di atas. Versi paket: `3.0.0`.
