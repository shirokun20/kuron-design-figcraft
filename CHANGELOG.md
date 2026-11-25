# Changelog — kuron-design-figcraft

Satu versi untuk seluruh paket: `VERSION`, frontmatter `SKILL.md`, dan
`HARNESS_VERSION` selalu identik.

## 3.0.0 — Paket mandiri, aman dipublikasikan

- **Gabung tiga skill** (`kuron_design_crafting` 2.5.1,
  `kuron_glass_light_design` 1.0.0, `figcraft_live_editing` 1.0.0) menjadi satu
  `SKILL.md` + modul di `references/`: dark workbench, light glassmorphism,
  live terminal editing, dan loop verifikasi piksel 3–5x.
- **Lengkapi modul light:** sambung tabel Modal Dialog yang terpotong,
  tambahkan Verification Checklist (14 butir) dan 8 aturan paritas Light/Dark.
- **Portabilitas:** hapus seluruh path absolut pribadi; token & `DESIGN.md`
  dibundling di `references/`; prefix `--ks-*` didokumentasikan sebagai
  konvensi skill, bukan milik satu repo; port `--port` dapat dikonfigurasi;
  binary via env `FIGCRAFT_APP`, file kerja via `FIGCRAFT_DESIGN`.
- **Script dibundling** di `scripts/` (tanpa build one-off yang memuat path
  privat): `figcraft_tool.py`, `build_artistic_flow.py`, `agent_terminal.py`,
  `quick_design.py`, `audit_render.py`, `multi_agent_worker.py`.
- **Guardrail:** semua subprocess/socket memakai timeout; semua loop
  baca/polling/REPL punya cut-loop guard (`--max-events`, `--max-seconds`,
  batas chunk `recv`, batas baris REPL).
- **Harness unified:** `harness-info` melaporkan nama `kuron-design-figcraft`
  dan versi `3.0.0` (sebelumnya `kuron_design_crafting` 2.5.1).
- **Test:** konversi 4 script test ke `unittest.TestCase`, tambahkan
  `test_package_hygiene.py` (zero-leak, frontmatter, version lock).
- **Distribusi:** `install.sh` kini memasang ke
  `<target>/skills/kuron-design-figcraft/` dan memverifikasi versi + test.

## Riwayat warisan (ringkas)

- 2.5.1 — identitas nama (name ≠ ID) + disiplin file hidup.
- 2.5.0 — peta mesin & anti-halu (piksel > mata > JSON).
- 2.4.0 — yin-yang + version lock + builder dialog/empty/error/ledger.
- 2.3.0 — red-team integration, `build_connector`, linter S-01/S-02/S-08.
- 2.2.0 — loop verifikasi 3–5x + supremasi `DESIGN.md`.
