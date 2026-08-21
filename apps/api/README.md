# apps/api

## OCR tangkapan layar (ING-10)

`POST /api/v1/ocr` memakai Tesseract. Di dalam container, `docker/api.Dockerfile` sudah memasang
`tesseract-ocr` beserta `tesseract-ocr-ind`, jadi tidak ada langkah tambahan.

Untuk menjalankannya di luar container:

```bash
# Debian/Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-ind
```

```powershell
winget install --id UB-Mannheim.TesseractOCR
```

Pemasang Windows di atas hanya membawa bahasa Inggris. Paket Indonesia diambil terpisah dari
[tessdata resmi](https://github.com/tesseract-ocr/tessdata) dan diletakkan di folder `tessdata`
yang dapat ditulis, lalu ditunjuk lewat `TESSDATA_PREFIX` - menulis langsung ke
`C:\Program Files\Tesseract-OCR\tessdata` membutuhkan hak administrator.

```powershell
$dir = "$env:LOCALAPPDATA\tessdata"
New-Item -ItemType Directory -Force $dir
Copy-Item "C:\Program Files\Tesseract-OCR\tessdata\eng.traineddata" $dir
Invoke-WebRequest "https://github.com/tesseract-ocr/tessdata/raw/main/ind.traineddata" -OutFile "$dir\ind.traineddata"
$env:TESSDATA_PREFIX = $dir
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Tanpa paket Indonesia sistem **tetap berjalan** memakai bahasa yang ada dan mencatat
peringatannya - kata Indonesia lebih sering salah baca, tetapi endpoint-nya tidak mati.
Tanpa Tesseract sama sekali, `/api/v1/ocr` menjawab dengan pesan yang menyarankan menempel teks
atau mengunggah CSV; endpoint lain tidak terpengaruh.
 - Backend FastAPI

Satu service tunggal, service layer modular **secara kode** (bukan dipecah jadi container terpisah).
Referensi: blueprint bagian 27 (arsitektur backend), 28 (API contracts), ADR-008.

## Struktur

| Folder | Isi | Referensi |
| --- | --- | --- |
| `app/routers/` | Endpoint handlers | bagian 28.1 |
| `app/services/` | `AnalyzeService`, `QnaService` - orkestrasi per request | bagian 27.2 |
| `app/tools/` | 10 tool contracts + 4 turunan - **satu-satunya sumber angka di sistem** | bagian 27.3 |
| `app/adapters/` | `TextModelAdapter`, `VisionModelAdapter`, `EmbeddingAdapter` | bagian 27.2 |
| `app/schemas/` | Pydantic models sesuai schema JSON | bagian 25 |
| `app/config.py` | Pembacaan `.env` + `configs/config.yaml` | bagian 27.2 |

## Endpoint Tier 1 (bagian 28.1)

| Endpoint | Method | Fungsi |
| --- | --- | --- |
| `/api/v1/analyze` | POST | Analisis penuh dari batch ulasan (`?trace=1` menyertakan jejak perhitungan) |
| `/api/v1/questions` | POST | Q&A ter-ground pada hasil analisis |
| `/api/v1/ocr` | POST | Baca teks ulasan dari tangkapan layar (draf, bukan analisis) |
| `/api/v1/reply-drafts` | POST | Draf balasan penjual untuk ulasan pendukung satu Action Card |
| `/api/v1/trace` | POST | Rantai klausa -> agregat -> skor untuk satu Action Card |
| `/api/v1/archive` | POST | Ringkasan agregat yang aman dibawa keluar sesi |
| `/api/v1/compare` | POST | Selisih antar-periode terhadap arsip milik pengguna |
| `/api/v1/health` | GET | Proses backend hidup |
| `/api/v1/readiness` | GET | Seluruh model selesai dimuat |
| `/api/v1/models` | GET | Versi model aktif (reproducibility) |
| `/api/v1/demo/sample` | GET | Dataset contoh untuk demo |

## Aturan yang mengikat

- **Sinkron**, tanpa background job - batas MVP rulebook (bagian 2.4 rulebook, ADR-008).
- `redact_personal_data()` berjalan **sebelum** data mencapai model manapun (bagian 27.3).
- Error pada `classify_review_image()` **tidak** menghentikan analisis (graceful degradation).
- Error pada `generate_action_recommendations()` / `answer_review_question()` memicu **FALLBACK MODE**,
  bukan kegagalan total (ADR-014).
- Model dimuat sekali saat startup, bukan per-request (bagian 27.2).
- `/reply-drafts` dan `/trace` membaca artefak sesi yang sama dengan Q&A - satu masa
  kedaluwarsa untuk seluruh sisa satu analisis (1 jam, maksimal 50 sesi). Lewat dari itu
  keduanya menolak dengan jujur alih-alih menghitung ulang; prediksi per klausa memang
  sudah tidak ada (ADR-010, sesi sekali-pakai).
- Draf balasan **tidak pernah** memuat janji ganti barang atau refund. Slot keputusan
  bisnis terbit sebagai `[keputusan Anda: ...]` dan tetap menjadi pekerjaan manusia
  (ADR-013).
- `/compare` **tidak menyimpan apa pun**. Arsip pembandingnya datang di badan permintaan,
  dari berkas milik pengguna, dan hilang bersama responsnya.
- `VisionModelAdapter` **menolak aktif** kalau artefak probe-nya berstatus selain GO atau
  CONDITIONAL GO. Gerbang go/no-go modul visual dijalankan kode, bukan diingat orang -
  dan alasan penolakannya keluar lewat `/readiness`.

