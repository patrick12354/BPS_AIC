# Peta Jalan Babak Final

Dokumen ini menjawab satu pertanyaan rubrik secara langsung: *"apakah arsitektur yang dibangun
memiliki fleksibilitas untuk dikembangkan tanpa perombakan total, dan apakah tim mengakui area
yang masih dapat ditingkatkan secara signifikan?"* Jawabannya bukan "ya" - jawabannya adalah
daftar di bawah, masing-masing dengan spesifikasi, titik sambung di kode yang sudah ada, dan
cara mengukur apakah ia berhasil.

Urutannya menurut **kenaikan kredibilitas per jam kerja**, bukan menurut kerennya fitur. Semua
item dirancang agar muat dalam batasan yang sama dengan penyisihan: satu alur sinkron, parameter
statis saat demo, tanpa database, tanpa API eksternal.

## L0 - Validasi aspek oleh manusia independen (dapat dimulai hari ini)

**Masalah.** Label aspek lahir dari weak supervision; gold 500 klausa (ADR-017) berasal dari
pra-anotasi LLM yang ditinjau tim. Pada gold itu IndoBERT 0,766 setara leksikon 0,770 - sedangkan
pada data sentimen berlabel manusia independen IndoBERT unggul jelas. Selisih arah ini hanya
dapat dijelaskan oleh anotasi manusia dari nol.

**Yang sudah ada di repo.** `scripts/build_aspect_human_pack.py` menyusun 200 klausa (150
bertingkat dari gold + 50 segar dari ulasan Shopee asli) menjadi dua berkas pelabel identik
berurutan acak, alat pelabelan HTML lokal, dan panduan. `ml/text/evaluate_aspect_human.py`
menghitung Cohen's kappa per aspek, menulis baris yang tidak disepakati untuk adjudikator ketiga,
lalu membandingkan leksikon / TF-IDF / IndoBERT / label gold-LLM pada rujukan manusia.

**Ukuran berhasil.** Kappa gabungan >= 0,6 (kesepakatan "substansial"); F1 aspek per pendekatan
dilaporkan apa adanya di MODEL_CARD §3.3b - termasuk bila IndoBERT tetap tidak unggul.

**Status: SELESAI 22 Agustus 2026** (susunan LLM + manusia, 120 klausa, kappa 0,68). Hasilnya:
IndoBERT 0,579 ≈ leksikon 0,581 - tidak unggul, dan gold ADR-017 bukan penyebabnya (0,704
terhadap manusia). Temuan ini melahirkan L0' di bawah.

## L0' - Latih ulang kepala aspek pada label gold + manusia (distilasi, bukan leksikon)

**Masalah.** L0 membuktikan kepala aspek hanya memulihkan leksikon karena seluruh label latihnya
berasal dari leksikon. Pembacaan semantik (gold-LLM 0,704; LLM zero-shot 0,660) jelas lebih dekat
ke manusia. Memanggil LLM saat inferensi melanggar ADR-001; yang konsisten adalah memindahkan
pengetahuannya ke model lokal lewat label latih.

**Spesifikasi.** (1) Perluas label berkualitas: gold 500 + 120 manusia + pra-anotasi LLM pada
2-3 ribu klausa tambahan yang diadjudikasi manusia pada sampel kontrol (pola ADR-017, dengan
kontrol yang kini terbukti perlu: "yakin" LLM hanya 53% cocok). (2) Latih ulang hanya
`aspect_head` di atas encoder beku (murah, menit di CPU) - lalu, bila membaik, fine-tune penuh.
(3) Ukur pada 120 klausa manusia yang SAMA, yang tidak pernah ikut latih.

**Ukuran berhasil.** Macro F1 aspek pada 120 klausa manusia naik terukur di atas leksikon
(0,581), khususnya ukuran_varian dan kualitas_produk. Bila tidak naik, tulis; itu pun informasi.

**Status tahap 1 - SELESAI 23 Agustus 2026** (MODEL_CARD §3.3c): kepala dilatih ulang dari 411
klausa gold di atas encoder beku → macro 0,585 (lama 0,579; leksikon 0,581) - **tidak berbeda
bermakna secara makro**, tetapi kualitas_produk +0,11 dan kesesuaian_deskripsi +0,13 (micro
+0,022). Dipasang sebagai bawaan dengan jalan kembali `ASPECT_HEAD=v1`. Tahap 2 (label latih
2-3 ribu klausa + kontrol manusia, lalu fine-tune penuh) tetap pekerjaan babak final - 411 label
terbukti tidak cukup untuk melampaui leksikon secara makro.

**Usaha.** 1-2 hari; pelabelan kontrol 1 orang x 2 jam.

## L1 - Kalibrasi keyakinan (temperature scaling)

**Masalah.** Probabilitas softmax klausa (0,96-0,999) tidak terkalibrasi; 88% dari 128 ulasan
negatif PRDECT-ID yang lolos diprediksi dengan p<0,10 - model yakin saat salah. Angka itu sudah
dikeluarkan dari rumus prioritas dan disembunyikan dari antarmuka.

**Spesifikasi.** Temperature scaling (Guo et al., 2017): satu parameter T per head, di-fit
dengan NLL pada `data/processed/clauses_val.csv`; T disimpan di bundle checkpoint; ECE
sebelum/sesudah dilaporkan. Titik sambung: `DualHeadClassifier` (logits/T, satu baris),
`TextModelAdapter.calibrated` sudah dibaca oleh `AnalysisResult.confidence_calibrated`, dan
`priority.py` / `trace.py` sudah menyiapkan jalur "kembali masuk rumus" begitu bendera itu benar.

**Ukuran berhasil.** ECE turun terukur; keyakinan kembali tampil di jejak perhitungan dengan
label "terkalibrasi (ECE x,xx)".

## L2 - Agregasi klausa v2: aturan asimetris untuk keluhan

**Masalah.** Temuan Fase 8: suara mayoritas klausa menelan keluhan pada ulasan campuran
("bagus sih, cuma jahitannya lepas") - 11 keluhan hilang pada set evaluasi.

**Spesifikasi.** Satu klausa negatif ber-aspek = keluhan pada aspek itu tercatat, berapa pun
klausa positifnya; sentimen dokumen boleh tetap campuran. Evaluasi ulang `evaluate_external.py`
+ gold SEBELUM memutuskan ship; hasilnya ditulis apa pun arahnya.

## L3 - Menghidupkan jalur visual: linear probe di atas CLIP

**Masalah.** Gerbang VIS-01 NO-GO (argmax 45% < baseline 61%). `VisionModelAdapter` sudah
menolak aktif tanpa artefak GO, dan `ml/visual/linear_probe.py` sudah ditulis.

**Spesifikasi.** Scrape ulang foto bintang 1-3 dari >=3 produk (audit batch otomatis di
`prepare_apify_photos.py`), target >=150 foto sisi bermasalah; label lewat alat yang ada;
probe BINER "perlu diperiksa" dengan cross-validation berulang; gerbang yang sama dengan
zero-shot. Lolos -> penanda antrean periksa dengan abstention; gagal -> angka baru ke Roadmap.

## L4 - Kontradiksi foto <-> teks (terkunci sampai L3 lolos)

`contradiction_flag` di mesin fusi sudah ada; yang belum adalah sisi foto yang dapat dipercaya.
Setelah L3: kartu "Perlu dicek: foto membantah teksnya" dengan kedua bukti berdampingan.

## L5 - Selesai pada penyisihan: arsip & perbandingan antar-periode tanpa database

Sudah berjalan (`/archive`, `/compare`, ekspor PNG). Pengembangan berikutnya: perbandingan lebih
dari dua arsip (tren multi-bulan), tetap stateless.

## Yang sengaja tidak ada di peta ini

IoT/hardware, autentikasi, database pengguna, background job, LLM API eksternal - masing-masing
melanggar batasan penyisihan atau merusak klaim inti ("lokal, angka tidak dikarang, keputusan
milik manusia"). Lihat `docs/BUSINESS_VALUE.md` §5 "Yang sengaja TIDAK dilakukan".
