# Live Editing Workflow — `agent_terminal.py`

Workflow resmi untuk **live editing** file `.figcraft` lewat
`scripts/agent_terminal.py` (port kontrol TCP, default `9880`). Gunakan modul
ini saat mengedit, memantau, mengekspor, atau memverifikasi layar secara
langsung. Padukan dengan `dark-artifact-rules.md` (gelap) atau
`light-glass-system.md` (terang) untuk aturan token dan estetika.

Semua perintah dijalankan dari root paket skill.

---

## 1. Aturan Flag Global & Path

- Flag **`--port <PORT>` wajib ditulis SEBELUM subcommand**:

  ```bash
  python3 scripts/agent_terminal.py --port 9880 status
  ```

- Port dapat diganti bebas (`--port 9901`, dst.) bila port default sibuk.
  Port bukan konstanta — selalu baca dari flag atau `.figcraft.port`.
- Path file `.figcraft` bersifat **tahan-cwd**: path relatif diselesaikan
  terhadap direktori kerja/root yang berisi file tersebut. Default dapat
  diganti lewat env var `FIGCRAFT_DESIGN`.
- File PID/port (`.figcraft.pid`, `.figcraft.port`) ditulis di *working
  directory* saat ini.
- Lokasi binary FigCraft dapat diganti lewat env var `FIGCRAFT_APP`.

---

## 2. Daftar Subcommand

| Subcommand | Kegunaan | Contoh |
|---|---|---|
| `start` | Jalankan FigCraft dengan live port (`--file/-f`, `--no-wait`) | `--port 9880 start --file out/workbench.figcraft` |
| `status` | Cek kesehatan socket & dokumen aktif | `--port 9880 status` |
| `open` | Buka file lain di instance berjalan | `--port 9880 open out/other.figcraft` |
| `frames` | Daftar frame level-layar (`id`, `name`, `x/y/w/h`); `--json` | `--port 9880 frames` |
| `reload` | `--soft` (default, aman) atau `--hard` (paksa) | `--port 9880 reload --soft` |
| `watch` | Pantau mtime → auto reload + export-all | `--port 9880 watch out/workbench.figcraft -o out/previews/ --scale 2 --max-events 200 --max-seconds 600` |
| `exec` | JSON-RPC engine command langsung | `--port 9880 exec select.set '{"ids": [10]}'` |
| `diff` | Ringkasan properti satu node | `--port 9880 diff --id <ID>` |
| `export` | Ekspor SATU frame (`--id`, `-o`, `--format`, `--scale`) | `--port 9880 export --id <ID> -o out/previews/01.png --scale 2` |
| `export-all` | Ekspor SEMUA frame ke folder | `--port 9880 export-all -o out/previews/ --scale 2` |
| `interactive` | REPL interaktif (maks 10.000 baris) | `--port 9880 interactive` |
| `harness-info` | Manifest JSON kapabilitas harness | `--port 9880 harness-info` |
| `stop` | Hentikan proses FigCraft | `--port 9880 stop` |

Contoh manifest singkat:

```bash
python3 scripts/agent_terminal.py --port 9880 harness-info
# => {"name": "kuron-design-figcraft", "version": "3.0.0", ...}
```

---

## 3. Alur Live Visual Feedback Loop (WAJIB)

Jangan mengedit `.figcraft` secara buta atau menganggap build sukses hanya dari
exit code. Jalankan siklus tertutup:

1. **Start & Discover**
   - `start --file <file>.figcraft`
   - `frames` untuk mendapatkan ID frame asli — **jangan pernah menebak ID**.
2. **Edit / Mutasi**
   - Ubah lewat builder Python (`figcraft_tool.py`) atau mutasi via `exec`
     (`node.set`, `select.set`, `file.save`).
   - Pastikan `lint_design()` menghasilkan **0 warning** sebelum ekspor.
3. **Sync ke Canvas**
   - Iterasi cepat: `watch <file> -o out/previews/ --scale 2` di terminal
     terpisah, atau `reload --soft` setelah setiap perubahan file.
   - `reload --hard` hanya bila `--soft` tidak menyegarkan struktur page/font.
4. **Verifikasi Mutasi & Ekspor**
   - `diff --id <ID>` memastikan properti benar-benar berubah.
   - `export --id <ID>` atau `export-all` menghasilkan bukti visual.
5. **Inspeksi Visual Piksel per Piksel**
   - Buka PNG; periksa teks tak terpotong, tak ada tumpang tindih, kontras
     bersih, batas `clip: true` rapi.
   - Ulangi 2–5 sampai satu pass penuh lolos (minimal 3 pass untuk layar baru,
     maksimal 5).
6. **Cleanup**
   - `stop` saat sesi selesai bila tidak ada agen lain yang memakai port itu.

---

## 4. Contoh Pola `exec`

```bash
# Pilih node
python3 scripts/agent_terminal.py --port 9880 exec select.set '{"ids": [<ID>]}'

# Ubah properti (validasi JSON dulu)
python3 scripts/agent_terminal.py --port 9880 exec node.set '{"id": <ID>, "name": "<nama>"}'

# Simpan dokumen aktif
python3 scripts/agent_terminal.py --port 9880 exec file.save '{}'
```

Gunakan single quotes di shell untuk membungkus JSON agar tidak diinterpretasi.

---

## 5. Guardrails & Troubleshooting

- **JSON invalid ditolak** sebelum dikirim ke socket; pesan ramah menyertakan
  contoh bentuk JSON yang benar.
- **Port sibuk / stale PID:** jalankan `status` dulu. Bila socket mati tapi
  `.figcraft.pid` tertinggal, `stop` lalu `start` ulang (atau ganti `--port`).
- **Jangan paralelkan dua writer** pada file `.figcraft` yang sama; `watch`
  hanya membaca & me-render. Untuk kerja paralel pakai
  `multi_agent_worker.py` (partisi namespace ID + lock `.figcraft.lock`).
- **Jangan klaim dari metadata JSON:** bukti kebenaran = PNG yang dibuka.
- **Semua socket punya timeout** (`send_rpc`, `FigcraftClient.connect`, worker),
  dan semua loop pembacaan/polling punya cut-loop guard:
  - `send_rpc`: maksimal 1024 potongan `recv()` per respons.
  - `watch`: `--max-events` (default 1000) dan `--max-seconds` (default 3600).
  - `interactive`: maksimal 10.000 baris.
- **Binary tidak ada:** `start` melaporkan error jelas. Set `FIGCRAFT_APP`
  ke lokasi binary; operasi offline (builder/lint/save) tetap bisa jalan.
- **Sesi basi:** setelah edit headless di luar sesi, `reload --hard` atau
  buka file lain lalu buka kembali file target sebelum klaim visual.

---

## 6. Ringkasan Satu Baris

`status/start → harness-info → frames → edit → reload/watch → diff →
export/export-all → lihat PNG (3–5x) → stop`.
