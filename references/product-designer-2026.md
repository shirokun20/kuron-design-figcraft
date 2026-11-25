# Product Designer 2026 — Empat Pilar Wajib

Standar kerja `kuron-design-figcraft` sebagai product designer modern: pahami
domain dulu, rancang menyeluruh (bukan kulit UI saja), bangun dari komponen,
lalu eksekusi tegas. Modul ini mengikat `SKILL.md`, `patterns.md`, dan modul
tema — bukan tambahan opsional.

---

## 1. Analisis Domain, Outcome & Opsi Gaya UI Dinamis

Sebelum menyentuh kanvas, jalankan **brief 4 pertanyaan** (maksimal 5 menit):

| Pertanyaan | Output |
|---|---|
| Jenis aplikasi? | kelas produk (operasional, konten, multi-modul, utilitas) |
| Target user? | siapa, konteks pakai, tingkat akrabnya |
| Masalah utama? | satu friksi yang harus hilang |
| Outcome? | satu hasil terukur yang ingin dicapai pengguna |

Lalu **tawarkan 2–3 opsi arah gaya UI & tata letak** yang sesuai konteks —
pengguna memilih atau mengarahkan. Jangan memaksakan satu gaya seragam.

| Opsi arah | Cocok untuk | Karakter |
|---|---|---|
| `dense operational` | alur kerja profesional, banyak data | baris rapat, 3 kolom, aksi cepat |
| `bento / modular` | dashboard multi-modul, ringkasan | kartu grid asimetris, skala jelas |
| `editorial` | konten, dokumentasi, bacaan | ritme tipografi, lebar baca terukur |
| `clean utility` | alat sempit, setup, form | satu fokus, minimum dekorasi |

**Tolak keras AI slop:** dekorasi kosong, gradasi seragam, layout klise yang
sama untuk semua domain. Utamakan **cognitive clarity** — tiap elemen punya
alasan hadir.

---

## 2. Kompetensi Product Designer Menyeluruh (Zero "Bolong")

Rancang sistem, bukan sekadar layar. Ceklist minimum sebelum build:

- **UX Flow & IA:** alur aksi utama + sekunder jelas; hierarki informasi
  terbaca oleh manusia dan terbaca oleh alat bantu (urutan node, nama semantik,
  label yang bisa dibaca mesin).
- **Microcopy fungsional:** label menyebut aksi + objek; *helper text* menjelaskan
  format; *empty state* menawar aksi; pesan *error/validation* menyebut sebab +
  jalan keluar. **Jangan bergantung pada warna saja** — sertakan teks/icon.
- **State & edge cases (Zero "Bolong"):** `empty`, `loading/skeleton`,
  `error`, `disabled/focus`, serta variasi panjang teks & jumlah data
  (0 / 1 / banyak / sangat panjang). Setiap state punya desain nyata.
- **Pola AI & interaksi modern (bila relevan):** status proses proporsional
  (diam → disable → spinner → progres bertahap), kontrol/koreksi user
  (batal, edit, ulang), dan transparansi hasil tanpa overclaim.
- **Aksesibilitas & handoff-friendly:** kontras teks/latar WCAG AA, fokus
  terlihat, target sentuh ≥44px, dan komposisi yang realistis dibangun
  (token + builder yang tersedia).

---

## 3. Component-First & Reuse (Duplicate → Refine)

1. **Bangun komponen dasar lebih dulu:** `input`, `form`, `button`, `icon`,
   `card`/`list item`, dan elemen berulang — masing-masing punya *variant* dan
   *property* yang jelas (`size`, `tone`, `state`).
2. **Hierarki token:** `primitive → semantic → component` (lalu `theme/state`).
   Komponen tidak pernah memakai hex mentah; ia memakai token semantik.
3. **Di FigCraft, utamakan `Duplicate → Refine`:** salin node komponen yang
   sudah ada, lalu rapikan/sesuaikan bagian yang kurang tepat. Jangan merakit
   node mentah dari nol untuk setiap screen — itu sumber inkonsistensi dan
   iterasi lambat.
4. Perubahan pada komponen induk menyebar ke turunan. Nama node tetap semantik
   (`Btn_<Action>`, `Card_<Name>`), cocokkan by `name`, bukan ID.

---

## 4. Eksekusi Tajam & Anti-Overthinking

- Keputusan desain **terukur, tegas, langsung ke inti kebutuhan** — tanpa
  perdebatan estetika bertele-tele.
- Time-box: brief ≤5 menit → pilih satu opsi arah → build → verifikasi.
- Guardrail tetap mutlak: 0 path pribadi, 0 secret/token, test hijau, dan loop
  verifikasi PNG 3–5x. Tajam bukan berarti melangkahi bukti.

---

## Ringkasan Satu Baris

`brief domain → tawarkan opsi gaya → pilih → komponen dulu → duplicate & refine
→ state lengkap → eksekusi tegas → bukti PNG`.
