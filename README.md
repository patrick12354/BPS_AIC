# Ulasin

**Mengubah tumpukan ulasan dan foto pelanggan UMKM berbahasa Indonesia informal menjadi tiga masalah paling mendesak, bukti kutipan aslinya, dan langkah konkret yang bisa langsung dikerjakan - dalam satu kali unggah.**

Subtema: Smart Commerce · Seluruh model berjalan lokal, CPU-friendly, tanpa API berbayar · Setiap rekomendasi wajib persetujuan manusia

---

## Untuk juri: cara memeriksa sendiri, bukan mempercayai

Setiap klaim di dokumen ini punya satu perintah yang membuktikan atau membantahnya. Tidak ada yang perlu diterima begitu saja.

| Klaim | Cara memeriksanya |
| --- | --- |
| "Angka tidak pernah dikarang" | Buka kartu aksi mana pun di halaman hasil analisis, tekan **"Bagaimana angka ini dihitung?"**. Panelnya menampilkan klausa mentah yang terbaca model, prediksi tiap klausa, agregasinya, dan tiap komponen rumus prioritas beserta aritmetikanya. Kalikan sendiri: hasilnya adalah skor yang tertera di kartu. Lewat API: `POST /api/v1/analyze?trace=1`. |
| "Berjalan lokal, tanpa API berbayar" | Putus koneksi internet setelah container jalan, lalu analisis lagi. Tidak ada satu pun panggilan keluar di jalur inferensi. |
| "Sistem gagal dengan anggun" | Kosongkan mount `./models`, nyalakan ulang. `GET /api/v1/readiness` menyebutkan persis apa yang sedang tidak aktif, dan analisis **tetap terbit** memakai jalur leksikon. |
| "Versi model dapat diaudit" | `GET /api/v1/models` menyebut versi checkpoint teks, model embedding, dan status orchestrator. |
| Angka evaluasi di bagian 11 | `python ml/text/evaluate_gold.py` (label manusia independen) dan `python ml/text/evaluate_external.py` (dataset publik). Gerbang visual: `python ml/visual/evaluate_gate.py`. |
| "Keputusan selalu milik manusia" | Tidak ada nilai `executed` pada enum `UserAction`, dan `user_action` tidak pernah diisi sistem. Draf balasan pun menyisakan keputusan uang sebagai `[keputusan Anda: ...]` yang harus disunting sendiri. |
| Batas yang diakui sendiri | `docs/LIMITATIONS.md` memuat kegagalan yang terukur, termasuk gerbang visual yang **tidak lolos** dan angka keyakinan model yang sengaja disembunyikan karena belum terkalibrasi. |
| Angka keyakinan model | Tidak ditampilkan sampai benar-benar terkalibrasi. `AnalysisResult.confidence_calibrated` menentukannya, dan medannya dibaca dari isi checkpoint - bukan dari saklar konfigurasi. Metodenya di `docs/MODEL_CARD.md` bagian 9. |
| Gerbang model visual dijalankan, bukan diingat | `VisionModelAdapter` membaca vonis gerbang dari artefak probe dan **menolak aktif** kalau isinya bukan GO. Vonis yang belum dikenal juga menolak. Diuji di `tests/unit/test_vision_gate.py`. |
| "Riwayat antar-sesi tanpa database" | Unduh arsip di bagian terakhir laporan, buka `.json`-nya: angka agregat saja. Unggah kembali lewat "Bandingkan dengan sesi sebelumnya" - selisih yang tidak melampaui margin kesalahan gabungan ditandai "belum berarti", bukan dibaca sebagai keberhasilan. |
| Seluruh perilaku di atas | `pytest tests -q` - 340 test, termasuk kasus yang menguji bahwa sistem MENOLAK menjawab saat buktinya tidak ada, dan bahwa arsip tidak pernah membawa satu kata pun dari ulasan. |

## Daftar isi

1. [Ringkasan](#1-ringkasan)
2. [Status pengembangan](#2-status-pengembangan)
3. [Masalah dan mengapa AI diperlukan](#3-masalah-dan-mengapa-ai-diperlukan)
4. [Alur kerja sistem end-to-end](#4-alur-kerja-sistem-end-to-end)
5. [Arsitektur](#5-arsitektur)
6. [Kontrak data dan API](#6-kontrak-data-dan-api)
7. [Antarmuka pengguna](#7-antarmuka-pengguna)
8. [Alur kerja pengembangan](#8-alur-kerja-pengembangan)
9. [Menjalankan yang sudah ada](#9-menjalankan-yang-sudah-ada)
10. [Dataset dan lisensi](#10-dataset-dan-lisensi)
11. [Evaluasi dan batas klaim](#11-evaluasi-dan-batas-klaim)
12. [Keputusan arsitektur](#12-keputusan-arsitektur)
13. [Keterbatasan yang diketahui](#13-keterbatasan-yang-diketahui)
14. [Struktur repositori](#14-struktur-repositori)
15. [Konvensi pengembangan](#15-konvensi-pengembangan)
16. [Dokumentasi lengkap](#16-dokumentasi-lengkap)

---

## 1. Ringkasan

Ulasin menjembatani lima tahap berurutan yang selama ini terputus pada perkakas yang tersedia bagi UMKM:

> ulasan mentah → pemahaman aspek & sentimen → penggabungan bukti teks + visual → penentuan prioritas → rekomendasi aksi bisnis dengan bukti yang dapat diverifikasi

**Jembatan lima tahap inilah novelty produk - bukan satu model AI tunggal mana pun.** Dashboard marketplace berhenti di rata-rata rating; sentiment analysis biasa berhenti di label sentimen. Tidak ada yang melanjutkan ke *"jadi minggu ini saya harus mengerjakan apa, dan apa buktinya?"*

Dua sifat yang membentuk hampir semua keputusan teknis di repositori ini:

- **Angka tidak pernah dikarang.** Seluruh frekuensi, persentase, dan skor prioritas dihitung tool deterministic. Foundation model hanya menyusun narasi dari angka yang sudah jadi, dan tidak pernah menghitung sendiri.
- **Sistem tidak boleh gagal total.** Jika model visual gagal, alur turun mulus ke jalur teks-saja. Jika orchestrator gagal dimuat, sistem masuk FALLBACK MODE dan tetap mengeluarkan hasil lengkap dengan narasi template.

## 2. Status pengembangan

Dikerjakan bertahap mengikuti Fase 0–10. Setiap fase punya *acceptance criterion* dan *go/no-go gate* sendiri.

| Fase | Cakupan | Status | Gate |
| --- | --- | --- | --- |
| 0 | Scope freeze - taksonomi aspek, kelas visual, kontrak data | ✅ selesai | **GO** - taksonomi & kelas visual dikunci |
| 1 | Data & baseline - unduh, harmonisasi, split, baseline TF-IDF | ✅ selesai | **GO** - split product-level terverifikasi bersih, baseline tercatat |
| 2 | Model teks - fine-tuning IndoBERT | ✅ selesai | **Sentimen LULUS** (0,730 vs leksikon 0,700 pada label expert); **aspek TIDAK LULUS** - setara leksikon, lihat MODEL_CARD §4.3 |
| 3 | Model visual - zero-shot CLIP, threshold, kalibrasi | ❌ **NO-GO** | argmax 45% kalah dari tebakan sepele 61%; jalur linear probe sudah ditulis dan siap dijalankan, menunggu foto tersedia kembali |
| 4 | Retrieval & action engine (RET-01, ACT-01) | ✅ selesai | Action Card lolos spot-check anti-generik; RET-01 menolak menjawab saat bukti tak memadai |
| 5 | Backend FastAPI - 11 endpoint, 16 tool contract | 🔄 berjalan | 11 endpoint jalan (termasuk OCR tangkapan layar, draf balasan, jejak perhitungan, arsip, dan perbandingan antar-periode); orchestrator belum, sistem berjalan di FALLBACK MODE |
| 6 | Frontend React - halaman pemasaran + layar kerja analisis | 🔄 berjalan | Dua permukaan terpisah; alur unggah → proses → hasil (4 tab) terverifikasi di browser pada data contoh. Kotak FAQ non-AI di halaman pemasaran, 6 uji hijau ([bagian 7.1](#71-kotak-faq-di-halaman-pemasaran)) |
| 7 | Integrasi - termasuk jalur kegagalan & fallback | ✅ selesai | 16 integration test hijau, mencakup enam jalur wajib bagian 32 |
| 8 | Evaluasi penuh + error analysis | ⬜ belum | metrik tercatat apa adanya |
| 9 | Docker & reproducibility | ✅ selesai | **gate kritis LULUS** - `docker compose up --build` berjalan dari fresh clone, dan susunan yang sama melayani demo publik di [34.41.49.44](http://34.41.49.44) lewat pipeline auto-deploy build-dulu-baru-tukar ([DEPLOYMENT.md](docs/DEPLOYMENT.md)) |
| 10 | Dokumentasi akhir | 🔄 berjalan | MODEL_CARD, DATASET_CARD, ARCHITECTURE, LIMITATIONS, RESPONSIBLE_AI, BUSINESS_VALUE sudah terisi; proposal PDF belum |

> ### Yang perlu diketahui pembaca sekarang
>
> **Aplikasi sudah dapat dijalankan, dan sedang berjalan.** API, antarmuka web, dan pipeline `ml/` berfungsi penuh - lihat [bagian 9](#9-menjalankan-yang-sudah-ada). `docker compose up --build` sudah terverifikasi dari fresh clone, dan susunan container yang sama melayani demo publik di **<http://34.41.49.44>**.
>
> **Lapisan orchestrator (LLM) belum dibangun, jadi sistem berjalan permanen di FALLBACK MODE.** Ini disebut di muka karena konsekuensinya nyata: narasinya disusun template, bukan model bahasa. Yang TIDAK berubah adalah seluruh angka, prioritas, dan kutipan bukti - semuanya dihasilkan tool deterministic. Lihat [bagian 5.5](#55-mode-full-vs-fallback).
>
> **Tidak ada angka performa yang dikutip sebagai capaian di README ini.** Metrik yang sudah terukur beserta batas penafsirannya ada di [docs/MODEL_CARD.md](docs/MODEL_CARD.md) - termasuk dua gate yang **tidak lulus**.

## 3. Masalah dan mengapa AI diperlukan

Pemilik UMKM mikro-kecil menerima ulasan dalam volume yang tidak sebanding dengan waktu dan literasi digital yang mereka punya. Pola masalah nyata - ukuran salah, kemasan rusak, respons lambat - terkubur di antara ratusan baris teks yang tidak pernah dibaca sistematis. Foto bukti yang dilampirkan pembeli nyaris tidak pernah ditinjau secara agregat sama sekali.

### 3.1 Besarannya

| Angka | Nilai | Sumber |
| --- | --- | --- |
| Unit usaha e-commerce di Indonesia (2024) | **4,40 juta**, naik 15,3% setahun dan 86% dalam empat tahun, **mayoritas usaha mikro** | BPS, Statistik E-Commerce 2024 |
| Populasi UMKM (2025) | ~66 juta unit · >60% PDB · ~97% penyerapan tenaga kerja | Kementerian Koperasi dan UKM |
| Biaya platform yang sudah ditanggung penjual | **15-20% dari harga jual** (komisi 2,5-10% · gratis ongkir 4-4,5% · promosi 1-2% · iklan 3-5%) | Laporan industri, 2026 |
| Pengaduan konsumen BPKN (2024) | 1.733, **naik 200%** dari 926 pada 2023; e-commerce sektor teratas setelah jasa keuangan | BPKN |

Dua baris terakhir yang membuat masalah ini mendesak, bukan sekadar besar: margin penjual sudah
tergerus 15-20% sebelum satu rupiah masuk kantong, **dan** keluhan konsumen sedang naik tajam.
Setiap keluhan berulang yang tak terdeteksi adalah dua kerugian sekaligus - penjualan yang
hilang, dan biaya iklan yang dibakar untuk mendatangkan pembeli ke masalah yang belum
diperbaiki.

Sisi ongkos waktunya disajikan sebagai aritmetika terbuka, bukan sebagai temuan:

| | Nilai | Status |
| --- | --- | --- |
| Analisis 300 ulasan oleh sistem | **6,7 menit** (dari 66 ulasan / 88 detik pada CPU dua inti) | **terukur** |
| Membaca dan merekap 300 ulasan secara manual | ~2,7 jam (20 detik/ulasan + 1 jam rekap) | **asumsi, belum divalidasi** |

Sisi mesinnya terukur; sisi manusianya belum. Perbandingan itu ditulis begini - bukan sebagai
klaim "hemat 2,7 jam" - karena validasi waktu baca manual memang belum dikerjakan, dan itu
tercatat sebagai riset terbuka di [BUSINESS_VALUE.md](docs/BUSINESS_VALUE.md) §9.

### 3.2 Solusi yang sudah ada, dan di mana persisnya mereka berhenti

| Solusi existing | Yang dilakukannya | Di mana ia berhenti | Harga masuk |
| --- | --- | --- | --- |
| **Shopee Seller Centre** · **Tokopedia Seller Dashboard** · **TikTok Shop Seller Center** | Rating rata-rata, daftar ulasan, saring per bintang, statistik performa produk | Tidak mengelompokkan keluhan per aspek, tidak mengurutkan mana yang mendesak, tidak memberi rekomendasi tindakan. Dan tiap panel penjual hanya melihat kanalnya sendiri | Gratis |
| **Yotpo** | Mengumpulkan dan menampilkan ulasan, widget rating | Alat pengumpulan ulasan, bukan alat analisis keluhan; tidak ada prioritisasi tindakan; dioptimalkan untuk Bahasa Inggris | dari **USD 79/bln** |
| **Birdeye** | Manajemen reputasi multi-lokasi, ringkasan ulasan | Berharga per lokasi dengan kontrak 12 bulan dan onboarding terpisah; dirancang untuk bisnis multi-cabang berbahasa Inggris, bukan penjual marketplace Indonesia | **USD 299-449/bln** per lokasi + onboarding USD 500-1.500 |
| **Thematic** | Analitik umpan balik bertema, benar-benar melakukan ekstraksi tema | Kelas perusahaan - harga masuknya saja ~Rp32 juta/bulan; model temanya tidak dilatih untuk ragam informal Bahasa Indonesia | dari **USD 2.000/bln** untuk 3 pengguna |
| **Jubelio** · **Ginee** (multichannel Indonesia) | Sinkronisasi stok dan pesanan lintas marketplace | Fokus operasional, bukan insight ulasan; tidak mengekstrak aspek maupun memprioritaskan perbaikan | Berlangganan |
| Baca manual | Akurat dan penuh konteks | Tidak proporsional di atas 50-100 ulasan/bulan - waktu pemilik UMKM adalah kendala utamanya | Waktu |
| Keyword / rule-based sendiri | Murah, dapat diaudit | Bahasa ulasan informal penuh slang, typo, singkatan, campuran bahasa daerah; runtuh pada negasi, sarkasme, dan sentimen campuran | Gratis |
| Zero-shot LLM API murni | Cepat dibangun | Gagal syarat kustomisasi rulebook, sulit direproduksi tanpa API key, ongkos naik bersama volume, tidak konsisten antar run | Per token |

**Celahnya, dinyatakan tegas:**

```
Yang gratis  → berhenti di rating rata-rata, tanpa aspek dan tanpa prioritas
Yang mampu   → Rp1,26-32 juta/bulan, dan dirancang untuk ulasan berbahasa Inggris

Di antara keduanya, untuk "bahannya oke sih cuma kekecilan bgt, sizechartnya ngaco",
pada anggaran penjual mikro - tidak ada apa pun.
```

Ke situlah Ulasin masuk. Ongkos marginal melayani satu penjual terukur **~Rp1.330/bulan**,
diturunkan dari benchmark 66 ulasan/88 detik - hitungannya terbuka di
[BUSINESS_VALUE.md](docs/BUSINESS_VALUE.md) §6, dan angka itu konsekuensi langsung dari
ADR-001 (local-first, bukan API komersial).

Bukti empiris dari data kami sendiri mendukung ini: pada 96.300 klausa ulasan nyata, **baseline berbasis kecocokan permukaan runtuh pada fenomena komposisional** - sentimen campuran, negasi, dan sarkasme - meski menangani typo dan slang dengan baik. Rinciannya di [docs/MODEL_CARD.md](docs/MODEL_CARD.md) §3.1. Inilah celah yang harus ditutup model kontekstual, dan menjadi pembanding yang bermakna, bukan klaim kosong.

### 3.3 Pernyataan kebaruan - apa persisnya yang belum ada

Riset ABSA berbahasa Indonesia dengan IndoBERT sudah cukup banyak - ulasan hotel, aplikasi transportasi, produk kecantikan, konten perjalanan (lihat rujukan di [DATASET_CARD.md](docs/DATASET_CARD.md) §6 dan MODEL_CARD §6). **Semuanya berhenti pada label**: klausa ini aspek X bersentimen Y, lalu angka F1. Tidak satu pun melanjutkan ke pertanyaan yang sebenarnya diajukan pemilik toko. Kebaruan Ulasin bukan di salah satu komponennya, melainkan pada rantai yang dibuat utuh dan **dapat diperiksa di setiap matanya**:

| Mata rantai | Yang sudah ada di tempat lain | Yang baru di sini |
| --- | --- | --- |
| Klasifikasi aspek + sentimen | Ya - banyak paper ABSA IndoBERT | Bahasa marketplace informal, per **klausa** (bukan per ulasan), dengan dua gerbang evaluasi yang salah satunya dinyatakan tidak lulus |
| Dari label ke prioritas | Tidak ada untuk konteks UMKM ID | Skor deterministik frekuensi × keparahan × modifier, dengan **jejak perhitungan** yang dapat dihitung ulang pembacanya |
| Dari prioritas ke bukti | Dashboard marketplace: tidak ada; alat berbayar: ringkasan tanpa kutipan per klaim | Setiap angka membawa kutipan ulasan aslinya (retrieval + MMR), dan sistem **menolak menjawab** bila buktinya tidak ada |
| Dari bukti ke tindakan | Tidak ada | Kartu aksi berbahasa pemilik toko + draf balasan yang menyisakan keputusan uang di tangan manusia |
| Dari tindakan ke pengukuran ulang | Butuh database pengguna | Arsip agregat milik pengguna + perbandingan antar-periode yang menolak menyebut "membaik" bila selisihnya di bawah margin kesalahan |

Tiga sifat yang mengikat seluruh rantai - dan yang menurut kami lebih langka daripada fitur mana pun: **angka tidak pernah dikarang** (tool deterministik, LLM tidak menghitung), **sistem gagal dengan anggun dan mengaku** (`/readiness` menyebut apa yang mati), dan **keputusan selalu milik manusia** (tidak ada nilai `executed` di sistem ini).

### 3.4 Bukti dampak dari literatur dan data resmi

Klaim dampak dibatasi pada yang punya sumber. Tiga yang menopang desain produk:

| Klaim | Bukti | Dipakai untuk |
| --- | --- | --- |
| Membalas ulasan menaikkan rating dan volume ulasan | Proserpio & Zervas, *Marketing Science* 36(5), 2017, puluhan ribu ulasan TripAdvisor: hotel yang mulai membalas menerima **+12% ulasan** dan rating naik rata-rata **+0,12 bintang**; diringkas *Harvard Business Review*, Feb 2018 | Dasar fitur **Draf Balasan** - bukan hiasan, melainkan tindakan yang efeknya terukur di literatur |
| Populasi yang terdampak sangat besar | Kemenkop UKM 2025: **65,5 juta** unit UMKM, **61,9% PDB**, ~97% tenaga kerja; **25 juta** di antaranya sudah onboarding di platform digital dari target 30 juta | Sizing pasar di BUSINESS_VALUE §2 - yang dilayani adalah segmen yang sudah online, bukan seluruh populasi |
| Unit usaha e-commerce mayoritas mikro dan tumbuh cepat | BPS Statistik E-Commerce 2024: **4,40 juta** unit, +15,3% setahun, +86% dalam empat tahun | Target pengguna utama, dan alasan harga harus mendekati nol |

Yang **belum** punya bukti dan karena itu tidak diklaim: bahwa prioritas yang dihasilkan benar-benar diikuti pemilik toko, dan berapa waktu yang ia hemat. Keduanya tercatat sebagai riset terbuka di [BUSINESS_VALUE.md](docs/BUSINESS_VALUE.md) §9, dengan protokol pengukurannya.

**Yang produk ini sengaja BUKAN:** chatbot generik tanpa cakupan · dashboard sentiment analysis biasa · wrapper tipis di atas LLM API · sistem otonom yang mengeksekusi keputusan bisnis · generator materi iklan otomatis.

## 4. Alur kerja sistem end-to-end

### 4.1 Alur utama (satu input → satu output terpadu)

```mermaid
flowchart TD
    U[Pengguna UMKM] -->|unggah CSV/JSON/paste<br/>+ foto opsional| ING[ING-01 Ingestion<br/>validasi skema]
    ING --> GOV[GOV-01 Redaksi PII<br/>wajib, sebelum model apa pun]
    GOV --> SEG[Segmentasi klausa<br/>+ normalisasi slang]

    SEG --> TXT[NLP-01 Text Intelligence<br/>aspek multi-label + sentimen]
    SEG -->|hanya entri berfoto| VIS[VIS-01 Visual Intelligence<br/>4 kelas + abstention wajib]

    TXT --> FUS[FUS-01 Fusion<br/>rule-guided, confidence-aware]
    VIS --> FUS

    FUS --> RET[RET-01 Retrieval<br/>kutipan asli sebagai bukti]
    FUS --> STAT[calculate_aspect_statistics<br/>frekuensi, persentase, tren]
    STAT --> BEN[BEN-01 Benchmark kategori<br/>baseline precomputed]
    STAT --> PRI[calculate_priority_score<br/>deterministic]
    BEN --> PRI

    RET --> ACT[ACT-01 Action Card]
    PRI --> ACT
    ACT --> LLM{Orchestrator<br/>tersedia?}
    LLM -->|ya| NAR[Narasi disusun LLM<br/>dari angka yang sudah jadi]
    LLM -->|tidak| FB[FALLBACK MODE<br/>narasi template deterministic]
    NAR --> OUT[AnalysisResult]
    FB --> OUT
    OUT --> UI[Satu halaman hasil terpadu]
    UI -->|terima / tolak / simpan| U
```

Garis penting pada diagram di atas: **angka dihasilkan `calculate_*`, bukan oleh LLM.** LLM berada di hilir dan hanya menerima angka yang sudah dihitung. Cabang `FALLBACK MODE` bukan jalur error - ia menghasilkan hasil yang datanya identik, hanya bahasanya lebih sederhana.

### 4.2 Delapan kasus fusion teks + visual

Fusion memakai aturan eksplisit yang dapat diaudit baris per baris, bukan neural fusion yang tidak dapat dijelaskan:

| Kasus | Perlakuan |
| --- | --- |
| Teks negatif, foto sejalan | Confidence gabungan tinggi, badge "didukung bukti visual" |
| Teks negatif, foto abstain | Confidence murni dari teks; visual **tidak** menurunkan angka |
| Teks positif, foto menunjukkan masalah | **Contradiction flag** - ditampilkan apa adanya untuk ditinjau manusia |
| Teks & foto bertentangan arah | Sama - sistem tidak pernah memutuskan siapa yang benar |
| Hanya teks | Jalur visual dilewati sepenuhnya, bukan error |
| Hanya foto, teks sangat pendek | Visual diproses; keterbatasan konteks disebut eksplisit di narasi |
| Confidence teks tinggi, visual rendah | Bobot condong ke teks |
| Visual tinggi, teks ambigu | Bobot condong ke visual **hanya untuk kondisi fisik produk** |

`contradiction_flag = true` **selalu** memicu `requires_human_review = true`.

### 4.3 Jalur kegagalan

```mermaid
flowchart LR
    A[Analisis dimulai] --> B[Tool deterministic<br/>teks / visual / retrieval / skoring]
    B -->|tidak bergantung LLM| C{Orchestrator}
    C -->|berhasil| D[Narasi LLM]
    C -->|gagal dimuat / timeout /<br/>JSON tidak valid| E[Template deterministic]
    D --> F[AnalysisResult selalu terisi]
    E --> F
    G[Model visual gagal] -.->|graceful degradation| B
    H[Foto rusak] -.->|entri jadi teks-saja| B
    I[Evidence tidak ditemukan] -.->|'Data belum cukup',<br/>BUKAN jawaban karangan| F
```

## 5. Arsitektur

### 5.1 Diagram kontainer

```mermaid
flowchart TB
    subgraph Client
        WEB[frontend<br/>React + Vite<br/>:3000]
    end
    subgraph Backend["api - FastAPI, satu service :8000"]
        R[Router + Validator]
        SVC[Service Layer<br/>AnalyzeService, QnaService]
        TOOLS[Tool Registry<br/>10 tool contract]
        AD[Model Adapters]
        ERR[Error Handler<br/>+ Fallback Trigger]
    end
    subgraph Storage["Penyimpanan lokal"]
        VS[(Vector store<br/>Chroma embedded)]
        MS[(Model artifacts)]
        BD[(Baseline kategori<br/>precomputed)]
        TS[(Temp sesi<br/>dihapus tiap sesi)]
    end
    WEB -->|HTTP/JSON sinkron| R
    R --> SVC --> TOOLS --> AD
    SVC --> ERR
    AD --> MS
    TOOLS --> VS
    TOOLS --> BD
    TOOLS --> TS
```

**Maksimal 3 service** (`frontend`, `api`, `vector-store` opsional) - dapat disederhanakan jadi 2 dengan Chroma embedded di proses `api`. Service layer dipecah modular **secara kode**, bukan dipecah jadi kontainer terpisah, supaya reproduksi lokal tetap sederhana.

### 5.2 Lima lapisan AI

| # | Lapisan | Model utama | Fallback | Target |
| --- | --- | --- | --- | --- |
| 1 | Text Intelligence | IndoBERT-base (fine-tuned) | TF-IDF + Logistic Regression | CPU, ~500MB, <2s/100 ulasan |
| 2 | Visual Intelligence | CLIP ViT-B/32 zero-shot (frozen) | SigLIP | CPU, ~600MB, <1s/foto |
| 3 | Retrieval & Evidence | BGE-M3 + Chroma | Multilingual E5-base | CPU, ~1,1GB, <500ms/query |
| 4 | Action Engine | deterministic, **non-AI** | - | <2s |
| 5 | Foundation Orchestrator | SEA-LION (quantized) | Sailor2 / FALLBACK MODE | **belum dibangun** |

> ### Lapisan 5 belum ada, dan itu disebut di muka
>
> Adapter orchestrator belum ditulis; `ml/orchestrator/` masih kosong. Sistem karena itu berjalan **permanen di FALLBACK MODE**, dan seluruh demo yang Anda lihat adalah demo tanpa model bahasa sama sekali.
>
> **Yang hilang:** narasi Action Card disusun template, bukan LLM. Bahasanya lebih kaku.
>
> **Yang tidak hilang:** seluruh angka, urutan prioritas, kutipan bukti, benchmark kategori, dan jawaban tanya jawab. Semuanya dihasilkan tool deterministic yang tidak pernah membutuhkan LLM.
>
> Itu bukan kebetulan yang beruntung - itu ADR-011 dan ADR-014 bekerja persis seperti rancangannya. Sistem dirancang supaya LLM-nya **opsional**, dan versi yang dikumpulkan ini membuktikannya dengan cara yang paling meyakinkan: dengan menjalankannya tanpa LLM sama sekali.

**Bentuk kustomisasi yang benar-benar berjalan hari ini - dua dari tiga jalur:**

| Jalur | Status | Buktinya |
| --- | --- | --- |
| **Fine-tuning model pendukung** | ✅ berjalan | IndoBERT dua head, dilatih sendiri. Sentimen 0,730 vs leksikon 0,700 dan TF-IDF 0,627 pada label manusia ([MODEL_CARD](docs/MODEL_CARD.md) §4.3) |
| **RAG / evidence grounding** | ✅ berjalan | RET-01 mengambil kutipan asli sebagai bukti tiap rekomendasi, dan menolak menjawab saat buktinya tidak memadai |
| **Tool calling** | ❌ belum | Sepuluh tool contract-nya sudah terdefinisi dan berjalan, tetapi dipanggil service layer secara langsung - **bukan** oleh LLM yang memilih tool |

Klaim kustomisasi proyek ini karena itu bertumpu pada **fine-tuning dan RAG**, bukan pada tool calling. Sepuluh tool di bagian 5.3 nyata dan berjalan; yang belum ada adalah pemanggilnya yang berupa model bahasa.

Model teks dilatih dengan **satu encoder IndoBERT dan dua head terpisah** - head aspek multi-label dan head sentimen 3 kelas. Encoder dibagi karena dua model IndoBERT terpisah akan menghabiskan hampir dua kali anggaran RAM lapisan teks.

### 5.3 Sepuluh tool contract

Satu-satunya sumber angka di seluruh sistem. Orchestrator memanggil tool ini dan menyusun narasi dari hasilnya.

| Tool | Fungsi | Timeout | Wajib? |
| --- | --- | --- | --- |
| `preprocess_reviews()` | Validasi + normalisasi batch mentah | 10s | ya |
| `redact_personal_data()` | Masking PII sebelum model apa pun melihat teks | 5s | ya |
| `classify_text_aspects()` | Aspek + sentimen per klausa | 15s/100 | ya |
| `classify_review_image()` | Klasifikasi visual + abstention | 5s/foto | hanya jika ada foto |
| `retrieve_evidence()` | Kutipan relevan (RAG) | 3s | ya |
| `calculate_aspect_statistics()` | Frekuensi, persentase, tren | 2s | ya |
| `calculate_priority_score()` | Skor prioritas deterministic | 2s | ya |
| `compare_category_baseline()` | Perbandingan ke baseline kategori | 2s | ya |
| `generate_action_recommendations()` | Narasi Action Card | 8s | ya / fallback template |
| `answer_review_question()` | Jawaban Q&A ter-ground | 8s | ya / fallback pesan |

Kegagalan `classify_review_image()` **tidak** menghentikan analisis. Kegagalan dua tool terakhir memicu FALLBACK MODE. Kegagalan tool wajib lainnya menghentikan analisis dengan pesan error yang jelas.

### 5.4 Formula skor prioritas

Bukan perkalian mentah enam faktor - versi final setelah kajian ulang:

```
score = frequency_norm × severity_norm
        × (1 + 0.3 × recency_norm + 0.2 × benchmark_gap_norm)
```

Seluruh faktor dinormalisasi ke 0–1 sebelum dikalikan, hasil di-scale ke 0–100, lalu dipetakan ke tiga label urgensi. `confidence_norm` (rata-rata probabilitas softmax klausa) pernah menjadi pengali inti ketiga dan **dikeluarkan** karena belum terkalibrasi: angka yang sengaja tidak ditampilkan di layar tidak boleh diam-diam mengatur urutan kartu. Ia tetap dilaporkan di jejak perhitungan beserta statusnya, dan akan kembali masuk rumus hanya setelah `confidence_calibrated` bernilai benar (metode di `docs/MODEL_CARD.md`). `Business Relevance` sengaja **dihapus** sebagai faktor terpisah karena tumpang tindih dengan Severity. Bobot 0,3 dan 0,2 berstatus **belum divalidasi** - wajib diuji sensitivity ±50% pada Fase 8 sebelum dianggap final.

Jika total ulasan sesi < 15, seluruh Action Card diberi badge "confidence rendah - data terbatas" dan urgensinya dibatasi maksimal "Sedang", supaya sistem tidak terdengar pasti pada data yang terlalu sedikit.

### 5.5 Mode FULL vs FALLBACK

| | FULL | FALLBACK **← yang berjalan hari ini** |
| --- | --- | --- |
| Kapan aktif | Orchestrator berhasil dimuat - **belum pernah, adapternya belum dibangun** | Otomatis saat orchestrator tidak ada, gagal, timeout, atau outputnya tidak valid |
| Narasi Action Card | Disusun LLM | Template deterministic dari **data yang sama** |
| Q&A | Aktif | Nonaktif sementara dengan pesan jelas |
| Skor, statistik, evidence | - | **identik**, tidak ada yang hilang |
| Indikasi ke pengguna | - | Banner "Mode sederhana aktif" |

## 6. Kontrak data dan API

Seluruh pertukaran antar komponen memakai JSON dengan field wajib/opsional/enum yang didefinisikan eksplisit. Tiga belas skema dikunci sejak Fase 0 supaya frontend dapat mulai dengan mock data sebelum backend selesai.

**Skema inti:** `RawReview` · `ProcessedReview` · `ReviewImage` · `TextPrediction` · `VisualPrediction` · `MultimodalEvidence` · `AspectAggregate` · `BenchmarkRecord` · `ActionCard` · `EvidenceCitation` · `AnalysisResult` · `QnARequest/Response` · `ReplyDraft` · `ActionTrace` · `ErrorResponse`

**Endpoint Tier 1:**

| Endpoint | Method | Fungsi | Timeout |
| --- | --- | --- | --- |
| `/api/v1/analyze` | POST | Analisis penuh dari batch ulasan (`?trace=1` menyertakan jejak perhitungan) | 30s |
| `/api/v1/questions` | POST | Q&A ter-ground pada hasil analisis | 8s |
| `/api/v1/reply-drafts` | POST | Draf balasan penjual untuk ulasan pendukung satu Action Card | 1s |
| `/api/v1/trace` | POST | Rantai klausa → agregat → skor untuk satu Action Card | 1s |
| `/api/v1/archive` | POST | Ringkasan agregat yang aman dibawa keluar sesi (.json) | 1s |
| `/api/v1/compare` | POST | Selisih antar-periode terhadap arsip milik pengguna sendiri | 1s |
| `/api/v1/ocr` | POST | Baca teks ulasan dari tangkapan layar → **draf** untuk disunting | 60s |
| `/api/v1/health` | GET | Proses backend hidup | 1s |
| `/api/v1/readiness` | GET | Seluruh model selesai dimuat | 1s |
| `/api/v1/models` | GET | Versi model aktif (reproducibility) | 1s |
| `/api/v1/demo/sample` | GET | Dataset contoh untuk demo | 1s |

`/api/v1/ocr` sengaja tidak menganalisis apa pun. Ia mengembalikan teks yang terbaca sebagai draf; analisis baru berjalan setelah pengguna memeriksanya dan menekan tombolnya sendiri. Pembacaan teks dari gambar tidak pernah sempurna, dan satu huruf yang salah baca merambat ke seluruh hasil - pemilik toko adalah satu-satunya yang tahu bunyi ulasan aslinya. Endpoint ini juga **tidak** menyimpulkan apa pun dari isi gambar; menilai kondisi barang dari foto masih NO-GO (bagian keterbatasan).

`/api/v1/reply-drafts` menyusun balasan dari template berisi slot yang diisi data ulasan itu sendiri - deterministik, tanpa panggilan keluar. Dua permintaan atas kartu yang sama menghasilkan teks yang identik, dan variasinya dipilih lewat hash `review_id` alih-alih `random` supaya sifat itu tetap berlaku antar-run. Kalimat yang menuntut keputusan bisnis (ganti barang, refund, kompensasi) **tidak pernah diisi sistem**; ia terbit sebagai `[keputusan Anda: ...]` yang mengganggu untuk dibaca, dan tombol salin di antarmuka baru aktif setelah penggunanya menyunting teksnya sendiri.

`/api/v1/trace` membuka isi perhitungan satu kartu: klausa apa yang terbaca model, prediksi aspek dan sentimen tiap klausa, bagaimana keduanya menjadi agregat, dan bagaimana agregat menjadi skor prioritas - lengkap dengan aritmetika tiap komponennya. Tidak ada satu pun angka baru di sana; yang ditunjukkan adalah perhitungan **yang sama** dengan yang menghasilkan kartunya, dibuka isinya. Klaim "angka kami tidak dikarang" karenanya berhenti menjadi klaim yang harus dipercaya.

Keduanya membaca artefak sesi yang sama dengan Q&A - kartu, jejak, dan klausa negatifnya hidup di memori proses dengan satu masa kedaluwarsa (1 jam, maksimal 50 analisis). Setelah itu keduanya menolak dengan jujur alih-alih menghitung ulang, karena prediksi per klausa memang sudah tidak ada.

`/api/v1/archive` dan `/api/v1/compare` memenuhi baris Roadmap "riwayat antar-sesi" **tanpa database**, dengan membalik siapa yang menyimpan. Pengguna mengunduh sekeping JSON berisi agregat saja - tidak ada teks ulasan, kutipan, id ulasan, maupun nama produk di dalamnya - lalu mengunggahnya kembali bulan depan sebagai pembanding. Arsipnya datang di badan permintaan; server tidak punya tempat mengambilnya dan tidak akan pernah punya. Kalimat "kami tidak menyimpan apa pun" karenanya berhenti menjadi keterbatasan yang harus dimaklumi dan menjadi bentuk kepemilikan.

Selisih antar-periode **tidak pernah ditampilkan begitu saja**. Dua proporsi yang masing-masing bermargin kesalahan menghasilkan selisih yang marginnya lebih lebar dari keduanya, jadi "keluhan pengiriman turun 19% ke 8%" pada dua batch tiga puluhan ulasan bisa seluruhnya derau. Setiap baris membawa `significant`, dan yang tidak lolos ditandai "belum berarti" alih-alih dibaca sebagai keberhasilan.

Tidak ada autentikasi pada Tier 1 - sesi tunggal, data tidak disimpan permanen.

Contoh `ActionCard` yang dihasilkan (struktur, bukan hasil pengukuran):

```json
{
  "action_id": "ACT-2026-0142",
  "title": "Revisi size chart pada varian M dan L",
  "one_line_summary": "18 dari 52 keluhan ukuran menyebut produk lebih kecil dari ekspektasi",
  "aspect": "ukuran_varian",
  "frequency": 18, "frequency_total": 52,
  "severity": "sedang-tinggi", "confidence": 0.86,
  "evidence_quotes": ["review_id: 482", "review_id: 510"],
  "priority_reasoning": "Frekuensi tinggi (35% dari keluhan ukuran) + tren meningkat",
  "recommended_action": "Periksa kembali size chart varian M dan L ...",
  "risk_if_recommendation_wrong": "Jika size chart sudah akurat, revisi tidak menurunkan keluhan - cross-check manual disarankan",
  "user_action": null
}
```

Field `risk_if_recommendation_wrong` dan `user_action: null` bukan hiasan - keduanya menegaskan rekomendasi adalah saran yang menunggu keputusan manusia.

## 7. Antarmuka pengguna

Dua permukaan yang terpisah: halaman pemasaran di `#/` dan layar kerja analisis di `#/analisis`. Halaman pemasaran perlu panjang dan bersuara, layar kerja perlu pendek dan diam - menyatukannya memaksa kompromi yang merugikan keduanya, dan membuat pengguna yang kembali harus menggulir melewati materi promosi setiap kali ingin bekerja.

Di dalam layar kerja alurnya tetap linear - satu unggahan masuk, satu hasil keluar. Navigasi tab baru muncul setelah ada hasil; sebelum itu tidak ada apa pun untuk dijelajahi.

```mermaid
flowchart LR
    L[Halaman pemasaran<br/>hero, cara kerja, fitur] -->|Mulai Analisis| S1
    S1[Unggah<br/>tempel · berkas · tangkapan layar] --> S2[Memproses<br/>checklist bertahap]
    S2 --> S3[Hasil<br/>ringkasan, Action Card,<br/>skor data, benchmark]
    S3 --> D[Detail<br/>peluang, temuan foto,<br/>sebaran aspek]
    S3 --> Q[Tanya Jawab<br/>percakapan ber-sitasi]
    S3 --> R[Roadmap<br/>yang belum ada + alasannya]
    S3 <--> E[Panel Bukti<br/>kutipan asli + metadata]
    S3 -->|Analisis baru| S1
```

Aturan antarmuka yang mengikat: setiap Action Card wajib tombol **Terima / Tolak / Simpan Nanti** · warna urgensi selalu didampingi label teks (aksesibilitas buta warna) · confidence rendah dan abstain memakai **abu-abu, bukan merah** - abstain adalah keputusan jujur model, bukan error.

### 7.1 Kotak FAQ di halaman pemasaran

Halaman pemasaran memuat kotak tanya-jawab mengambang yang menjelaskan **produknya** - ini aplikasi apa, cara pakainya bagaimana, data saya disimpan atau tidak. Ia menjawab kebingungan yang muncul sebelum orang mau menekan "Mulai Analisis", dan tidak ada hubungannya dengan analisis ulasan.

**Ia bukan lapisan AI keenam, dan tidak menyamar jadi satu.** Pencocokannya leksikal murni di sisi browser: pencocokan kata berbobot IDF atas basis pengetahuan tertulis di [`src/content/faq.js`](apps/web/src/content/faq.js), tanpa satu pun panggilan model. Kotaknya menyebut dirinya "Kotak FAQ · jawaban dari daftar tertulis, bukan model AI" di kepala panel, sejak sebelum pertanyaan pertama diketik.

Tiga alasan pilihan itu:

| Alasan | Konsekuensinya |
| --- | --- |
| **Kejujuran** | Bagian 3 menyatakan produk ini sengaja BUKAN chatbot generik. Memasang chatbot LLM di halaman depan akan membantah kalimat itu sendiri |
| **Ketersediaan** | Halaman pemasaran tetap menjawab meski backend mati - justru saat itulah orang paling butuh tahu ini aplikasi apa |
| **Proporsi** | Anggaran RAM lapisan AI sudah dialokasikan penuh untuk membaca ulasan pengguna, bukan untuk menjawab "ini gratis?" |

Perilaku saat tidak tahu mengikuti aturan yang sama dengan RET-01 di backend: pertanyaan di luar cakupan dijawab **"belum ada jawaban tertulis untuk itu"** beserta tiga topik terdekat - tidak pernah ditebak. Ambang lolosnya diukur, bukan dikira-kira; [`faq-search.test.js`](apps/web/src/lib/faq-search.test.js) menahan 27 pertanyaan yang harus terjawab (semuanya >= 0,46) dan 6 yang harus ditolak (semuanya <= 0,25).

```bash
npm test --prefix apps/web
```

## 8. Alur kerja pengembangan

```mermaid
flowchart LR
    F0[Fase 0<br/>Scope freeze] --> F1[Fase 1<br/>Data & baseline]
    F1 --> F2[Fase 2<br/>Model teks]
    F2 --> F3[Fase 3<br/>Model visual]
    F3 -->|GO / CONDITIONAL / NO-GO| F4[Fase 4<br/>Retrieval & Action]
    F4 --> F5[Fase 5<br/>Backend]
    F5 --> F6[Fase 6<br/>Frontend]
    F6 --> F7[Fase 7<br/>Integrasi]
    F7 --> F8[Fase 8<br/>Evaluasi]
    F8 --> F9[Fase 9<br/>Docker & repro]
    F9 --> F10[Fase 10<br/>Dokumentasi]

    style F3 fill:#fff3cd,stroke:#d39e00
    style F9 fill:#fff3cd,stroke:#d39e00
```

Dua kotak bertanda adalah **gate kritis**. Fase 3 menentukan seberapa kuat klaim visual boleh ditulis - hasilnya dilaporkan apa adanya, dan keputusan NO-GO adalah hasil yang sah, bukan kegagalan. Fase 9 adalah prioritas mutlak di atas fitur apa pun: lebih baik fitur sedikit tetapi benar-benar dapat dijalankan orang lain.

**Prinsip kerja:** baseline dulu sebelum model kompleks · tidak ada klaim sebelum evaluasi dijalankan · penyimpangan dari desain awal dicatat sebagai ADR beserta alasannya, bukan diam-diam.

## 9. Menjalankan yang sudah ada

Bagian ini menjelaskan apa yang **sudah berfungsi hari ini**.

### 9.0 Cara tercepat - docker compose

```bash
docker compose up --build
```

Antarmuka di <http://localhost:3000>, API di <http://localhost:8000>. Container frontend menunggu API melewati healthcheck `/api/v1/readiness`, sehingga halaman tidak pernah tampil sebelum modelnya siap.

Bobot IndoBERT (499 MB) tidak masuk git dan dipasang dari `./models` sebagai volume read-only. **Kalau folder itu kosong, sistem tetap berjalan** memakai jalur leksikon dan menyatakan keterbatasannya di `/api/v1/readiness` - seluruh alur tetap dapat didemonstrasikan, hasilnya saja lebih lemah.

> Konfigurasi ini belum pernah dijalankan sampai selesai karena Docker tidak terpasang di mesin pengembangan. Apa yang sudah diverifikasi secara statis, dan apa yang belum, dicatat di [docker/README.md](docker/README.md).

### 9.0.1 Mengunduh checkpoint model

Bobot IndoBERT (499 MB) tidak masuk git. Unduh sekali:

```bash
python scripts/download_checkpoint.py
```

Sumbernya: <https://huggingface.co/MikaelAdi/insightulasan-nlp01>

Tanpa berkas ini sistem **tetap berjalan** memakai jalur leksikon dan menyatakan keterbatasannya di `/api/v1/readiness` - tetapi yang berjalan bukan sistem yang dijelaskan proposal.

### 9.0.2 Memeriksa apakah modelnya bekerja benar

```bash
python scripts/cek_model.py
```

Empat lapis dalam satu perintah: kesiapan berkas, perilaku pada ulasan yang jawabannya jelas bagi manusia, ketahanan terhadap masukan aneh, lalu metrik yang sudah diukur pada label manusia.

Lapis kedua sengaja memuat kasus yang **modelnya memang salah**. Pemeriksaan yang hanya berisi contoh berhasil tidak memeriksa apa pun — ia hanya membuktikan kita pandai memilih contoh.

### 9.0.3 Menjalankan tanpa Docker

```bash
python -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

```bash
npm run dev --prefix apps/web
```

Jalur ini **sudah terverifikasi berjalan**: API siap dalam ~53 detik pada CPU, dan antarmuka menghasilkan analisis penuh atas 120 ulasan contoh.

### 9.1 Prasyarat

- Python 3.11 atau lebih baru
- ~3 GB ruang disk (dataset + model artifacts)
- GPU **opsional** - hanya mempercepat fine-tuning. Target deployment tetap CPU-only.

### 9.2 Instalasi

```bash
git clone https://github.com/MikaelAdikara/BPS_AIC.git
cd BPS_AIC
python -m venv .venv
source .venv/Scripts/activate      # Linux/macOS: source .venv/bin/activate
pip install -r ml/requirements.txt
```

Untuk fine-tuning dengan GPU, pasang torch varian CUDA:

```bash
pip install "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124
```

> `torch>=2.6` bukan preferensi versi. IndoBERT hanya mendistribusikan `pytorch_model.bin` tanpa safetensors, dan `torch.load` di bawah 2.6 terkena CVE-2025-32434 sehingga ditolak transformers 5.x.

### 9.3 Pipeline langkah demi langkah

```bash
# 1. Unduh tiga dataset publik ke data/raw/ (tidak di-commit)
python scripts/download_datasets.py
python scripts/download_datasets.py --list      # lihat sumber + lisensi tanpa mengunduh

# 2. Harmonisasi + pelabelan + split product-level
python ml/text/build_dataset.py

# 3. Baseline TF-IDF + Logistic Regression (wajib sebelum fine-tuning)
python ml/text/baseline.py

# 4. Fine-tuning IndoBERT (dua head)
python ml/text/finetune.py --epochs 3 --batch-size 32

# 5. Susun berkas tugas anotasi gold test set
python ml/text/make_gold_task.py --n 500

# (diagnostik) Pemeriksaan kontaminasi label pada dataset stress test
python ml/text/validate_lf.py
```

### 9.4 Apa yang dihasilkan tiap langkah

| Script | Keluaran | Isi |
| --- | --- | --- |
| `download_datasets.py` | `data/raw/*/` + `SOURCE.json` | Dataset mentah + catatan sumber, lisensi, sitasi |
| `build_dataset.py` | `data/processed/clauses_{train,val,test_silver}.csv` | Klausa berlabel, split di tingkat produk |
| | `data/processed/build_report.json` | Statistik pembersihan, distribusi label, **hasil verifikasi kebocoran** |
| `baseline.py` | `ml/evaluation/baseline_results.json` | Metrik baseline pada beberapa irisan data |
| `finetune.py` | `models/indobert-nlp01/` (tidak di-commit) | Checkpoint + ambang aspek terpilih |
| | `ml/evaluation/finetune_results.json` | Metrik, riwayat per epoch, hyperparameter, seed |
| `make_gold_task.py` | `data/annotation/gold_annotation_task.csv` | 500 klausa untuk dilabeli manusia + panduan anotasi |

Seluruh script memakai **seed tetap 42** dan mencatat hyperparameter ke berkas hasil, supaya angka mana pun dapat ditelusuri balik ke run yang menghasilkannya. Ringkasan tiap eksperimen dicatat di [ml/evaluation/experiment_log.md](ml/evaluation/experiment_log.md).

### 9.5 Reproducibility

- Dataset **tidak di-commit** - diunduh ulang dari sumber resmi, sehingga tidak ada masalah lisensi maupun ukuran repositori.
- Model artifacts **tidak di-commit** - dihasilkan ulang oleh script, atau diunduh pada tahap build (mekanisme distribusi checkpoint hasil fine-tuning ditetapkan pada Fase 9).
- Split dilakukan **di tingkat produk**, bukan per baris, dan hasilnya diverifikasi eksplisit - laporan kebocoran ikut ditulis ke `build_report.json` supaya dapat diperiksa siapa pun, bukan sekadar diklaim.
- Data pengguna saat runtime bersifat **session-only** dan tidak pernah ditulis ke repositori.

## 10. Dataset dan lisensi

| Dataset | Sumber | Lisensi | Peran |
| --- | --- | --- | --- |
| PRDECT-ID | `ZakyF/PRDECT-ID` | **CC-BY-4.0** | Training + gold test |
| Tokopedia Product Reviews 2019 | `farhamu/tokopedia-product-reviews-2019` | **Apache-2.0** | Training + domain testing |
| e-commerce-sentiment-bahasa-indonesia | `AIbnuHibban/e-commerce-sentiment-bahasa-indonesia` | **MIT** | Stress test saja - **tidak** dipakai melatih |

**Atribusi wajib (CC-BY-4.0):** Sutoyo, R. dkk. *PRDECT-ID: Indonesian product reviews dataset for emotions classification tasks*. Data in Brief (2022). arXiv:2406.10118.

Dataset ketiga sengaja tidak dipakai melatih: 87% barisnya duplikat, distribusi kelasnya persis seimbang, dan label sentimennya ternyata merupakan pemetaan langsung dari kolom rating. Ia tetap bernilai sebagai **stress test** karena setiap barisnya ditandai jenis fenomena linguistik (sarkasme, negasi, typo, slang), sehingga kelemahan model dapat dipetakan per fenomena. Alasan lengkapnya di [docs/DATASET_CARD.md](docs/DATASET_CARD.md).

Foto ulasan untuk validasi model visual diperoleh terpisah pada Fase 3, dalam volume kecil untuk keperluan validasi, dengan anonimisasi wajib. Sumber tersebut **tidak menjadi dependency runtime** - aplikasi demo tidak pernah memanggilnya.

## 11. Evaluasi dan batas klaim

Repositori ini memisahkan tegas tiga jenis angka, dan penamaannya konsisten di seluruh berkas hasil:

| Jenis | Artinya | Boleh dikutip sebagai capaian? |
| --- | --- | --- |
| `silver_*` | Kecocokan terhadap labeling function otomatis | **Tidak** |
| `silver_*_unseen` | Sama, tetapi bebas efek hafalan frasa berulang | **Tidak** |
| `stress_*` | Diukur pada label yang diturunkan dari rating | Hanya sebagai diagnostik |
| gold test set | Diukur pada label manusia | **Ya - satu-satunya** |

Label aspek dihasilkan lewat *weak supervision* karena tidak ada dataset ABSA berbahasa Indonesia domain e-commerce yang tersedia publik. Konsekuensinya diakui terbuka: metrik pada label silver berisiko **sirkular** - model dapat sekadar memulihkan aturan yang membuat labelnya.

Status validasi per kepala model, apa adanya:

| Kepala | Penengah | Hasil | Status |
| --- | --- | --- | --- |
| **Sentimen** | Label manusia independen (NusaX-senti, PRDECT-ID) | IndoBERT **0,730** vs leksikon 0,700 vs TF-IDF 0,627; netral 0,021 → 0,645 | **Tervalidasi** |
| **Aspek** | Gold 500 klausa dari pra-anotasi LLM yang ditinjau tim (ADR-017) | IndoBERT 0,766 **setara** leksikon 0,770 | **Belum tervalidasi manusia independen** - dan selisih arahnya dengan sentimen justru mencurigakan: bisa modelnya, bisa gold-nya |
| Aspek, langkah berikutnya | Dua pelabel manusia independen + adjudikator, Cohen's kappa per aspek | Paket siap: `python scripts/build_aspect_human_pack.py` → label → `python ml/text/evaluate_aspect_human.py` | Berjalan - hasilnya akan ditulis ke MODEL_CARD §3.3b **apa pun arahnya** |

Baris terakhir adalah satu-satunya klaim model yang masih terbuka, dan perangkatnya sudah ada di repositori sehingga siapa pun - termasuk juri - dapat menjalankannya.

Rencana evaluasi penuh mencakup delapan baseline pembanding, ablation per lapisan, metrik retrieval, dan penilaian kualitatif rekomendasi. Rinciannya di [docs/MODEL_CARD.md](docs/MODEL_CARD.md).

## 12. Keputusan arsitektur

Delapan belas ADR terdokumentasi di [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Yang paling menentukan:

| ADR | Keputusan | Alasan singkat |
| --- | --- | --- |
| 001 | Local-first, bukan API komersial | Reproducibility lokal + kustomisasi nyata |
| 004 | Visual frozen zero-shot, bukan classifier terlatih | Data berlabel visual belum cukup volumenya - jujur soal ini lebih baik daripada memaksakan |
| 011 | Skor deterministic, LLM hanya menyusun narasi | Mencegah halusinasi angka, hasil dapat diaudit |
| 013 | Tidak ada eksekusi tindakan bisnis otomatis | Prinsip governance permanen, bukan batasan sementara |
| 014 | FALLBACK MODE wajib | Kegagalan satu komponen tidak boleh menjatuhkan seluruh sistem |
| **015** | **Label aspek lewat weak supervision + gold test set** | Dibuat saat implementasi: rencana awal memetakan label emosi ke aspek, ternyata tidak dapat dijalankan |
| **016** | **Dataset ketiga jadi stress test, bukan data latih** | Duplikasi 87% dan label turunan rating |
| **017** | **Gold test set lewat pra-anotasi LLM + adjudikasi manusia** | Melabeli 500 klausa dari nol menghambat seluruh angka NLP-01; beban manusia turun ke 302 baris tanpa memindahkan keputusan akhir dari manusia |
| **018** | **Q&A dijawab dari statistik terhitung + retrieval, bukan LLM** | Stub yang selalu menolak melanggar ADR-014 - saat fallback, yang boleh berbeda hanya narasi, bukan datanya |

ADR 015-018 lahir **setelah** data dan kode benar-benar dibuka dan asumsi awal terbukti salah - dicatat lengkap dengan konteks, alternatif yang ditolak, konsekuensi, dan syarat peninjauan ulang. Empat ADR itu adalah jejak proses yang paling sulit dikarang belakangan.

## 13. Keterbatasan yang diketahui

Ditulis apa adanya, bukan diperhalus. Daftar lengkap di [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

- **Generalisasi zero-shot pada foto ulasan konsumen Indonesia belum terbukti** - literatur pendukungnya berasal dari domain industri. Baru terjawab pada gate Fase 3.
- **Cakupan kategori F&B sangat tipis** - hanya 196 ulasan dari 39.986, sehingga aspek rasa dan baseline kategori F&B lemah buktinya. Mekanisme adaptasi taksonomi ada, tetapi demonstrasinya paling kuat pada kategori fesyen.
- **Baseline kategori bersifat historis dan statis**, bukan pemantauan kompetitor real-time.
- **Tidak ada riwayat lintas sesi** - setiap sesi dimulai dari awal, konsekuensi dari desain session-only.
- **Rekomendasi adalah saran berbasis pola data, bukan kebenaran mutlak.** Tombol tolak ada justru karena itu.
- **Label aspek belum divalidasi manusia independen** - pada gold ADR-017, model setara leksikon. Perangkat validasinya sudah ada ([bagian 11](#11-evaluasi-dan-batas-klaim)); hasilnya akan ditulis apa pun arahnya.

Rencana pengembangan babak final - dengan spesifikasi, titik sambung di kode, dan ukuran berhasil per item - ada di [docs/ROADMAP_FINAL.md](docs/ROADMAP_FINAL.md).

## 14. Struktur repositori

```
apps/
  web/                 React + Vite - 4 screen                      [Fase 6]
    public/brand/      aset logo hasil build dari Logo.png di akar repositori
    src/content/       basis pengetahuan kotak FAQ + isi roadmap
    src/lib/           rute, tema, pencocokan FAQ (+ ujinya)
  api/                 FastAPI                                      [Fase 5]
    app/routers/       endpoint handlers
    app/services/      AnalyzeService, QnaService
    app/tools/         10 tool contract - satu-satunya sumber angka
    app/adapters/      Text/Vision/Embedding/Orchestrator adapter
    app/schemas/       Pydantic models
ml/
  text/                pipeline data, baseline, fine-tuning          ✅ berfungsi
    lexicon.py         istilah topik dipisah dari istilah polaritas
    preprocess.py      normalisasi slang + segmentasi klausa
    build_dataset.py   harmonisasi + pelabelan + split
    baseline.py        TF-IDF + Logistic Regression
    finetune.py        IndoBERT dua head
    make_gold_task.py  penyusun berkas anotasi
    validate_lf.py     pemeriksaan kontaminasi label
  vision/              validasi zero-shot CLIP                       [Fase 3]
  embeddings/          BGE-M3 + vector store                         [Fase 4]
  orchestrator/        konfigurasi quantization                      [Fase 5]
  evaluation/          hasil evaluasi + experiment_log.md
data/
  raw/ interim/ processed/    tidak di-commit, dihasilkan script
  annotation/          berkas anotasi gold test set                  di-commit
  samples/             dataset demo untuk verifikasi lokal
  schemas/             JSON schema kontrak data
configs/               taksonomi aspek, kelas visual, threshold      FROZEN sejak Fase 0
docs/                  MODEL_CARD, DATASET_CARD, ARCHITECTURE, LIMITATIONS, RESPONSIBLE_AI
docs/design/           rancangan SaaS penuh + prototipe antarmuka 14 layar
docs/reference/        blueprint sistem, dossier riset, ringkasan aturan
scripts/               unduh dataset, precompute baseline, bangun aset logo
tests/                 unit / integration / e2e                      [Fase 5+]
docker/                Dockerfile api & web, nginx.conf, catatan verifikasi
docker-compose.yml     deployment lokal dua service (di root, bukan docker/)
```

## 15. Konvensi pengembangan

- **Conventional Commits**: `feat:` · `fix:` · `refactor:` · `docs:` · `test:`
- Commit dan push setiap ada perubahan berarti - riwayat commit adalah bagian dari bukti proses pengembangan, bukan sekadar administrasi.
- **Konfigurasi tidak di-hardcode.** Threshold, path model, dan batas ukuran dibaca dari `configs/*.yaml` dan `.env` (lihat `.env.example`).
- **Nilai yang harus berasal dari eksperimen sengaja dikosongkan** (`null`) sampai eksperimennya dijalankan - supaya tidak ada angka default yang menyamar sebagai hasil kalibrasi.
- Perubahan keputusan desain diedit di `docs/reference/` **lebih dulu**, baru diikuti kodenya, supaya dokumen tetap satu sumber kebenaran.

## 16. Dokumentasi lengkap

| Dokumen | Isi |
| --- | --- |
| [docs/SCOPE_FREEZE.md](docs/SCOPE_FREEZE.md) | Cakupan yang dikunci: taksonomi, kelas visual, fitur, formula prioritas, dan daftar keputusan yang sengaja ditunda |
| [docs/BRAND_GUIDELINES.md](docs/BRAND_GUIDELINES.md) | Identitas visual, palet semantik, tipografi, anatomi komponen, nada bahasa |
| [docs/design/SAAS_DESIGN.md](docs/design/SAAS_DESIGN.md) | Rancangan produk SaaS penuh: use case, arsitektur informasi, 14 layar, peta fitur, pemisahan Tier 1/2/3 |
| [docs/design/prototype.html](docs/design/prototype.html) | Prototipe antarmuka 14 layar yang dapat diklik - buka di browser |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Diagram arsitektur + 16 Architecture Decision Record |
| [docs/MODEL_CARD.md](docs/MODEL_CARD.md) | Metrik terukur beserta batas penafsirannya, rencana evaluasi |
| [docs/DATASET_CARD.md](docs/DATASET_CARD.md) | Sumber, lisensi, pemrosesan, sumber label, bias yang diketahui |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | Keterbatasan yang diketahui |
| [docs/RESPONSIBLE_AI.md](docs/RESPONSIBLE_AI.md) | Privasi, governance, threat model, pengawasan manusia, kepatuhan UU PDP, batas klaim |
| [docs/BUSINESS_VALUE.md](docs/BUSINESS_VALUE.md) | Target pengguna, lanskap pesaing berikut harganya, model bisnis, struktur biaya, kelayakan adopsi, dan daftar yang belum divalidasi |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Susunan demo publik, pipeline auto-deploy, batas kinerja terukur |
| [ml/evaluation/experiment_log.md](ml/evaluation/experiment_log.md) | Catatan setiap eksperimen yang benar-benar dijalankan |
| [docs/reference/](docs/reference/) | Blueprint sistem, dossier riset, ringkasan aturan - sumber kebenaran desain |

---

## Lisensi

[MIT](LICENSE). Lisensi dataset dan model yang dipakai tercantum pada [bagian 10](#10-dataset-dan-lisensi).
